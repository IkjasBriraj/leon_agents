"""
Tool Dispatcher — Routes tool calls to the right execution backend.

When the LLM returns a tool_call, the engine calls this dispatcher.
The dispatcher:
  1. Looks up the tool in the registry
  2. If requires_approval → triggers HITL interrupt
  3. If sandbox_required → delegates to DockerSandbox
  4. Otherwise → executes the tool's function/API call directly

Built-in tools available out of the box:
  - web_search      — HTTP search (via DuckDuckGo)
  - read_file       — Read a file from the workspace
  - write_file      — Write/append to a file
  - http_request    — Make an arbitrary HTTP request

Custom tools (via API):
  - openapi         — Call any OpenAPI-defined endpoint
  - function_code   — Execute Python/JS code in sandbox
"""

import importlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sandbox import DockerSandbox, SandboxResult
from app.core.state import AgentState

log = structlog.get_logger()


@dataclass
class ToolResult:
    """Structured result from a tool execution."""
    tool_name: str
    success: bool
    output: Any              # The data returned by the tool
    error: str | None        # Error message if success=False
    duration_ms: int
    requires_hitl: bool = False   # Set to True when HITL approval is needed


class ToolDispatcher:
    """
    Routes tool calls from the LLM to the appropriate execution backend.

    Maintains an in-memory registry of tool handlers that maps
    tool names to callable async functions.

    Built-in tools are registered at startup.
    Custom tools are registered dynamically from the database.
    """

    def __init__(self, db: AsyncSession, sandbox: DockerSandbox | None = None) -> None:
        self.db = db
        self.sandbox = sandbox or DockerSandbox()
        # Registry: tool_name → async callable
        self._registry: dict[str, Any] = {}
        # DB tool configs: tool_name → Tool model dict
        self._tool_configs: dict[str, dict[str, Any]] = {}

        # Register built-in tools
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register all built-in tool handlers."""
        self._registry["web_search"] = self._tool_web_search
        self._registry["http_request"] = self._tool_http_request
        self._registry["python_repl"] = self._tool_python_repl
        self._registry["calculator"] = self._tool_calculator
        self._registry["read_context"] = self._tool_read_context
        self._registry["write_context"] = self._tool_write_context

    def register_tool(self, name: str, handler: Any, config: dict[str, Any] | None = None) -> None:
        """Register a custom tool handler."""
        self._registry[name] = handler
        if config:
            self._tool_configs[name] = config

    async def dispatch(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        state: AgentState,
        run_id: str,
    ) -> ToolResult:
        """
        Main dispatch method — routes a tool call to its handler.

        Args:
            tool_name:  Name of the tool to invoke
            tool_args:  Arguments parsed from the LLM's tool call
            state:      Current agent state (passed for context-aware tools)
            run_id:     Current run ID (for logging and HITL signaling)

        Returns:
            ToolResult with output or error

        Note on HITL:
            If the tool is configured with requires_approval=True in the DB,
            this method returns ToolResult(requires_hitl=True) instead of
            executing. The engine then triggers the HITL controller.
        """
        start_time = time.monotonic()
        log.info("tool.dispatch", tool_name=tool_name, run_id=run_id)

        # Check HITL requirement from tool config
        tool_config = self._tool_configs.get(tool_name, {})
        if tool_config.get("requires_approval", False):
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=None,
                duration_ms=0,
                requires_hitl=True,
            )

        # Check if this tool needs sandbox execution
        if tool_config.get("sandbox_required", False) or tool_name == "python_repl":
            return await self._execute_sandboxed(tool_name, tool_args, start_time)

        # Look up and invoke the handler
        handler = self._registry.get(tool_name)
        if not handler:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=f"Tool '{tool_name}' not found in registry",
                duration_ms=duration_ms,
            )

        try:
            result = await handler(tool_args, state)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.info("tool.success", tool_name=tool_name, duration_ms=duration_ms)
            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=result,
                error=None,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("tool.error", tool_name=tool_name, error=str(exc))
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def _execute_sandboxed(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        start_time: float,
    ) -> ToolResult:
        """Execute a sandboxed code tool in Docker."""
        code = tool_args.get("code", "")
        language = tool_args.get("language", "python")
        stdin = tool_args.get("stdin", "")

        if language == "javascript":
            sandbox_result = await self.sandbox.execute_node(code, stdin)
        else:
            sandbox_result = await self.sandbox.execute_python(code, stdin)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        return ToolResult(
            tool_name=tool_name,
            success=sandbox_result.success,
            output={
                "stdout": sandbox_result.stdout,
                "stderr": sandbox_result.stderr,
                "exit_code": sandbox_result.exit_code,
            },
            error=sandbox_result.error,
            duration_ms=duration_ms,
        )

    # ─── Built-in Tool Handlers ────────────────────────────────────────────────

    @staticmethod
    async def _tool_web_search(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
        """
        Web search using DuckDuckGo Instant Answer API.
        No API key required. Returns top results as structured data.
        """
        query = args.get("query", "")
        max_results = min(args.get("max_results", 5), 10)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract results
        results = []
        for r in data.get("RelatedTopics", [])[:max_results]:
            if "Text" in r and "FirstURL" in r:
                results.append({"title": r.get("Text", "")[:200], "url": r.get("FirstURL", "")})

        return {"query": query, "results": results, "abstract": data.get("Abstract", "")}

    @staticmethod
    async def _tool_http_request(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
        """Make an arbitrary HTTP request and return the response."""
        url = args.get("url", "")
        method = args.get("method", "GET").upper()
        headers = args.get("headers", {})
        body = args.get("body")
        timeout = min(args.get("timeout", 30), 60)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=headers, content=body)
            return {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:10_000],  # Cap response at 10KB
            }

    async def _tool_python_repl(self, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
        """Execute Python code in a Docker sandbox."""
        code = args.get("code", "print('No code provided')")
        result = await self.sandbox.execute_python(code)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "success": result.success,
        }

    @staticmethod
    async def _tool_calculator(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
        """Safe math expression evaluator."""
        import ast
        import operator

        expr = args.get("expression", "0")

        # Whitelist-based safe eval
        SAFE_OPS = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.Mod: operator.mod,
        }

        def safe_eval(node: ast.AST) -> float | int:
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.BinOp):
                op_func = SAFE_OPS.get(type(node.op))
                if not op_func:
                    raise ValueError(f"Unsupported operator: {type(node.op)}")
                return op_func(safe_eval(node.left), safe_eval(node.right))
            elif isinstance(node, ast.UnaryOp):
                op_func = SAFE_OPS.get(type(node.op))
                if not op_func:
                    raise ValueError(f"Unsupported unary operator: {type(node.op)}")
                return op_func(safe_eval(node.operand))
            else:
                raise ValueError(f"Unsupported expression type: {type(node)}")

        tree = ast.parse(expr, mode="eval")
        result = safe_eval(tree.body)
        return {"expression": expr, "result": result}

    @staticmethod
    async def _tool_read_context(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
        """Read a value from the agent's context store."""
        key = args.get("key", "")
        return {"key": key, "value": state.get("context", {}).get(key)}

    @staticmethod
    async def _tool_write_context(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
        """Write a value to the agent's context store."""
        key = args.get("key", "")
        value = args.get("value")
        # Note: The engine will apply this update to state after receiving the result
        return {"key": key, "value": value, "_context_update": {key: value}}
