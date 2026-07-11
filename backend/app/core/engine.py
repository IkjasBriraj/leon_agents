"""
AgentCraft Orchestration Engine — The Core State Machine

This is the heart of AgentCraft. The engine executes a workflow by:

  1. Loading the workflow graph (nodes + edges) into memory
  2. Initializing AgentState from run input_data
  3. Loading memory context (profile + relevant episodic/semantic)
  4. Executing a node-by-node decision loop:
       - For each node, execute the appropriate handler
       - Evaluate conditional edges to determine next node(s)
       - Handle cycles via loop counters
       - Broadcast trace events via Redis Pub/Sub for real-time UI
  5. On HITL gate: checkpoint state, pause, wait for human, resume
  6. On tool call: dispatch to ToolDispatcher (HITL check → sandbox → direct)
  7. Store episodic memories and audit logs after each step
  8. Persist final state and metrics to the Run record

Node execution handlers:
  - 'start':        No-op (advance to next node)
  - 'end':          Terminate run, set output
  - 'agent':        LLM call → parse response → update messages
  - 'tool':         Invoke specific tool directly
  - 'condition':    Evaluate expression, route via conditional edges
  - 'hitl_gate':    Pause for human approval
  - 'memory_read':  Retrieve relevant memories, inject into context
  - 'memory_write': Store content as episodic/semantic memory
  - 'code':         Execute code in Docker sandbox
  - 'parallel_fork':Fork to multiple branches (simplified: sequential)

Agentic Loop Pattern (React/Plan-Execute-Reflect):
  start → agent → (tool_call → tool → agent)* → end
  OR with loop:
  start → agent → reflect → [loop back to agent OR end]

The engine tracks all state transitions in RunStep records for
full reproducibility and educational trace visualization.
"""

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.graph import GraphNode, WorkflowGraph
from app.core.hitl import HITLController
from app.core.llm_client import LLMClient, build_tools_schema, get_embedding
from app.core.memory_manager import MemoryManager
from app.core.sandbox import DockerSandbox
from app.core.state import (
    AgentState,
    Message,
    compute_delta,
    create_initial_state,
    deserialize_state,
    merge_state,
    serialize_state,
)
from app.core.tool_dispatcher import ToolDispatcher, ToolResult
from app.models.agent import Agent
from app.models.run import Run, RunCheckpoint, RunStep
from app.models.workflow import Workflow

log = structlog.get_logger()


class EngineError(Exception):
    """Raised when the engine encounters an unrecoverable error."""


class AgentCraftEngine:
    """
    Async state-machine engine that executes an AgentCraft workflow run.

    One instance is created per run invocation. The engine is designed to be
    run as a background task (via Redis Streams worker) rather than in
    the HTTP request lifecycle.

    Example usage (in a worker)::

        engine = AgentCraftEngine(db=db, redis=redis)
        await engine.execute_run(run_id=run_id)
    """

    def __init__(self, db: AsyncSession, redis: Any) -> None:
        self.db = db
        self.redis = redis
        self._sandbox = DockerSandbox()

    async def execute_run(self, run_id: uuid.UUID) -> None:
        """
        Main entry point — executes a complete workflow run.

        Loads the run from DB, initializes all subsystems, and enters the
        execution loop. Updates the Run record with final status and metrics.
        """
        run_id_str = str(run_id)
        log.info("engine.run_start", run_id=run_id_str)

        # ─── Load Run + Workflow ──────────────────────────────────────────────
        run = await self._load_run(run_id)
        if not run:
            log.error("engine.run_not_found", run_id=run_id_str)
            return

        workflow = await self._load_workflow(run.workflow_id)
        if not workflow:
            await self._fail_run(run, "Workflow not found")
            return

        # ─── Initialize subsystems ────────────────────────────────────────────
        graph = WorkflowGraph.from_orm(workflow)
        start_node = graph.get_start_node()
        if not start_node:
            await self._fail_run(run, "Workflow has no start node")
            return

        # Find the primary agent config (first 'agent' node)
        agent_config = await self._get_primary_agent(graph, workflow.org_id)
        system_prompt = agent_config.get("system_prompt", "You are a helpful AI assistant.")

        # Load tools for this agent
        tool_schemas = await self._load_tool_schemas(agent_config)

        # Initialize memory manager
        memory_mgr = MemoryManager(
            db=self.db,
            org_id=workflow.org_id,
            agent_id=agent_config.get("id"),
        )

        # Initialize LLM client from agent config
        llm = LLMClient.from_agent(agent_config)

        # Initialize tool dispatcher
        dispatcher = ToolDispatcher(db=self.db, sandbox=self._sandbox)

        # Initialize HITL controller
        hitl = HITLController(db=self.db, redis=self.redis, run_id=run_id_str)

        # ─── Mark run as started ──────────────────────────────────────────────
        await self.db.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(status="running", started_at=datetime.now(UTC))
        )
        await self.db.commit()

        # ─── Initialize state ─────────────────────────────────────────────────
        state = create_initial_state(
            run_id=run_id_str,
            workflow_id=str(run.workflow_id),
            org_id=str(workflow.org_id),
            input_data=run.input_data or {},
            system_prompt=system_prompt,
        )

        # Load profile memory into context
        profile_memories = await memory_mgr.get_profile()
        if profile_memories:
            profile_text = "\n".join(m.content for m in profile_memories)
            state = merge_state(state, {
                "context": {**state.get("context", {}), "agent_profile": profile_text}
            })

        # ─── Execute the graph ────────────────────────────────────────────────
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0
        current_node = start_node

        try:
            while True:
                # Check for cancellation signal
                cancelled = await self.redis.get(f"agentcraft:cancel:{run_id_str}")
                if cancelled:
                    await self._update_run_status(run_id, "cancelled")
                    await self._emit_event(run_id_str, {"type": "run_error", "error": {"message": "Cancelled"}, "step_index": state.get("step_count", 0)})
                    return

                step_index = state.get("step_count", 0)
                state_before = dict(state)

                # ─── Emit step_start event ────────────────────────────────────
                await self._emit_event(run_id_str, {
                    "type": "step_start",
                    "run_id": run_id_str,
                    "step_index": step_index,
                    "node_key": current_node.key,
                    "node_type": current_node.node_type,
                    "timestamp": datetime.now(UTC).isoformat(),
                })

                step_start = time.monotonic()
                step_type, step_result = await self._execute_node(
                    node=current_node,
                    state=state,
                    llm=llm,
                    dispatcher=dispatcher,
                    memory_mgr=memory_mgr,
                    hitl=hitl,
                    graph=graph,
                    tool_schemas=tool_schemas,
                    run_id_str=run_id_str,
                    step_index=step_index,
                )
                duration_ms = int((time.monotonic() - step_start) * 1000)

                # ─── Apply state updates ──────────────────────────────────────
                if isinstance(step_result, dict) and "_state_update" in step_result:
                    state = merge_state(state, step_result["_state_update"])
                elif isinstance(step_result, dict) and step_result.get("new_state"):
                    state = step_result["new_state"]

                # Always increment step count
                state = merge_state(state, {"step_count": step_index + 1})

                # Track token usage
                tokens_in = step_result.get("tokens_in", 0) if isinstance(step_result, dict) else 0
                tokens_out = step_result.get("tokens_out", 0) if isinstance(step_result, dict) else 0
                total_tokens_in += tokens_in
                total_tokens_out += tokens_out
                cost = step_result.get("cost_usd", 0.0) if isinstance(step_result, dict) else 0.0
                total_cost += cost

                # Compute delta for trace UI
                state_delta = compute_delta(state_before, dict(state))

                # ─── Persist RunStep ──────────────────────────────────────────
                run_step = RunStep(
                    run_id=run_id,
                    step_index=step_index,
                    node_id=current_node.id,
                    node_key=current_node.key,
                    step_type=step_type,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost,
                    state_before=state_before,
                    state_after=dict(state),
                    state_delta=state_delta,
                    llm_request=step_result.get("llm_request") if isinstance(step_result, dict) else None,
                    llm_response=step_result.get("llm_response") if isinstance(step_result, dict) else None,
                    model_used=step_result.get("model_used") if isinstance(step_result, dict) else None,
                    tool_name=step_result.get("tool_name") if isinstance(step_result, dict) else None,
                    tool_input=step_result.get("tool_input") if isinstance(step_result, dict) else None,
                    tool_output=step_result.get("tool_output") if isinstance(step_result, dict) else None,
                    memories_retrieved=step_result.get("memories_retrieved") if isinstance(step_result, dict) else None,
                    completed_at=datetime.now(UTC),
                    duration_ms=duration_ms,
                )
                self.db.add(run_step)
                await self.db.flush()

                # ─── Store episodic memory for this step ──────────────────────
                if step_type == "llm_call" and step_result.get("llm_response"):
                    content_preview = str(step_result.get("llm_response", ""))[:500]
                    await memory_mgr.store_episodic(
                        content=f"Step {step_index} [{current_node.key}]: {content_preview}",
                        metadata={"run_id": run_id_str, "step_index": step_index, "node_key": current_node.key},
                        importance=0.4,
                    )

                # ─── Emit step_end event ──────────────────────────────────────
                await self._emit_event(run_id_str, {
                    "type": "step_end",
                    "run_id": run_id_str,
                    "step_index": step_index,
                    "state_delta": state_delta,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.now(UTC).isoformat(),
                })

                # ─── Check terminal conditions ────────────────────────────────
                if current_node.node_type == "end":
                    break

                if state.get("error"):
                    await self._fail_run_from_state(run_id, run_id_str, state, total_tokens_in, total_tokens_out, total_cost)
                    return

                # Max iteration guard (global)
                agent_max_iter = agent_config.get("max_iterations", 25)
                if step_index >= agent_max_iter * 2:
                    await self._fail_run(run, f"Max iterations ({agent_max_iter}) exceeded")
                    return

                # ─── Advance graph ────────────────────────────────────────────
                next_nodes = graph.get_next_nodes(current_node.key, state)
                if not next_nodes:
                    # Dead end (no outgoing edges and not an 'end' node)
                    log.warning("engine.dead_end", node_key=current_node.key)
                    break

                # In parallel_fork, we'd launch all next_nodes concurrently.
                # For now we execute the first valid successor (simplified).
                current_node = next_nodes[0]

                # If this node is a loop_back, increment counter
                if current_node.node_type in ("agent", "tool", "condition"):
                    state = graph.increment_loop_counter(
                        current_node.key, state, agent_max_iter
                    )

            # ─── Run complete ─────────────────────────────────────────────────
            output = state.get("output") or state.get("context", {}).get("final_answer")
            await self.db.execute(
                update(Run)
                .where(Run.id == run_id)
                .values(
                    status="completed",
                    output_data={"result": output},
                    completed_at=datetime.now(UTC),
                    total_steps=state.get("step_count", 0),
                    total_tokens_in=total_tokens_in,
                    total_tokens_out=total_tokens_out,
                    total_cost_usd=total_cost,
                )
            )
            await self.db.commit()

            await self._emit_event(run_id_str, {
                "type": "run_complete",
                "run_id": run_id_str,
                "status": "completed",
                "output": output,
                "total_cost_usd": total_cost,
                "total_tokens": total_tokens_in + total_tokens_out,
                "duration_ms": 0,
            })
            log.info("engine.run_complete", run_id=run_id_str, steps=state.get("step_count"))

        except asyncio.CancelledError:
            await self._update_run_status(run_id, "cancelled")
        except Exception as exc:
            log.error("engine.fatal_error", run_id=run_id_str, error=str(exc), exc_info=True)
            await self._fail_run(run, str(exc))
            await self._emit_event(run_id_str, {
                "type": "run_error",
                "run_id": run_id_str,
                "error": {"message": str(exc)},
                "step_index": state.get("step_count", 0) if "state" in dir() else 0,
            })

    # ─── Node Execution Handlers ───────────────────────────────────────────────

    async def _execute_node(
        self,
        node: GraphNode,
        state: AgentState,
        llm: LLMClient,
        dispatcher: ToolDispatcher,
        memory_mgr: MemoryManager,
        hitl: HITLController,
        graph: WorkflowGraph,
        tool_schemas: list[dict],
        run_id_str: str,
        step_index: int,
    ) -> tuple[str, dict[str, Any]]:
        """
        Dispatch execution to the correct node handler.

        Returns:
            (step_type, result_dict) — step_type for RunStep, result contains
            state updates, token counts, tool output, etc.
        """
        node_type = node.node_type
        config = node.config

        match node_type:
            case "start":
                return "state_update", {}

            case "end":
                return "state_update", {"_state_update": {"output": state.get("context", {}).get("final_answer")}}

            case "agent":
                return await self._handle_agent_node(
                    node, state, llm, dispatcher, memory_mgr, graph, tool_schemas, run_id_str, step_index
                )

            case "tool":
                return await self._handle_tool_node(node, state, dispatcher, run_id_str)

            case "condition":
                return await self._handle_condition_node(node, state)

            case "hitl_gate":
                return await self._handle_hitl_node(node, state, hitl, step_index)

            case "memory_read":
                return await self._handle_memory_read_node(node, state, memory_mgr, run_id_str)

            case "memory_write":
                return await self._handle_memory_write_node(node, state, memory_mgr)

            case "code":
                return await self._handle_code_node(node, state)

            case _:
                log.warning("engine.unknown_node_type", node_type=node_type, node_key=node.key)
                return "state_update", {}

    async def _handle_agent_node(
        self,
        node: GraphNode,
        state: AgentState,
        llm: LLMClient,
        dispatcher: ToolDispatcher,
        memory_mgr: MemoryManager,
        graph: WorkflowGraph,
        tool_schemas: list[dict],
        run_id_str: str,
        step_index: int,
    ) -> tuple[str, dict[str, Any]]:
        """
        Execute an LLM agent node.

        The agent loop within a node:
          1. Retrieve relevant memories based on last user message
          2. Inject memories into context
          3. Call LLM with messages + tools
          4. If LLM returns tool_call → dispatch tool → append result → call LLM again
          5. If LLM returns text → update messages, done
          6. Return all token/cost metrics
        """
        messages = list(state.get("messages", []))
        memories_retrieved_log = []
        total_tokens_in = 0
        total_tokens_out = 0
        total_cost = 0.0

        # Retrieve relevant memories from the last user message
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        if last_user_msg:
            memories = await memory_mgr.retrieve_relevant(last_user_msg, k=5)
            memories_retrieved_log = [m.to_dict() for m in memories]

            if memories:
                # Inject memories as a system context injection
                memory_context = "\n\n".join(
                    f"[Memory {i+1} (score={m.score:.2f})]: {m.memory.content}"
                    for i, m in enumerate(memories)
                )
                memory_msg: Message = {
                    "role": "system",
                    "content": f"Relevant context from memory:\n{memory_context}",
                    "tool_call_id": None,
                    "tool_calls": None,
                    "name": None,
                }
                messages = [messages[0], memory_msg] + messages[1:]  # Insert after system prompt

                await self._emit_event(run_id_str, {
                    "type": "memory_retrieved",
                    "run_id": run_id_str,
                    "step_index": step_index,
                    "memories": memories_retrieved_log,
                    "scores": [m.score for m in memories],
                })

        # Inner tool-call loop (agent can call multiple tools before responding)
        max_tool_rounds = 10
        for _round in range(max_tool_rounds):
            response = await llm.complete(messages, tools=tool_schemas if tool_schemas else None)
            total_tokens_in += response.tokens_in
            total_tokens_out += response.tokens_out
            total_cost += response.cost_usd

            if not response.has_tool_calls:
                # Final text response — add to conversation
                assistant_msg: Message = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_call_id": None,
                    "tool_calls": None,
                    "name": None,
                }
                messages.append(assistant_msg)
                state = merge_state(state, {"messages": messages})
                break

            # Process tool calls
            # Add assistant's tool_call message to history
            tool_calls_msg: Message = {
                "role": "assistant",
                "content": response.content,
                "tool_call_id": None,
                "tool_calls": response.tool_calls,
                "name": None,
            }
            messages.append(tool_calls_msg)

            # Execute each tool call
            for tc in (response.tool_calls or []):
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                await self._emit_event(run_id_str, {
                    "type": "tool_called",
                    "run_id": run_id_str,
                    "step_index": step_index,
                    "tool_name": tool_name,
                    "tool_input": tool_args,
                })

                tool_result = await dispatcher.dispatch(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    state=state,
                    run_id=run_id_str,
                )

                # Handle HITL requirement
                if tool_result.requires_hitl:
                    decision = await self._handle_tool_hitl(
                        tool_name, tool_args, state, hitl, step_index
                    )
                    if not decision.is_approved:
                        tool_result = ToolResult(
                            tool_name=tool_name,
                            success=False,
                            output=None,
                            error=f"Tool execution rejected by human: {decision.message}",
                            duration_ms=0,
                        )
                    else:
                        # Re-execute after approval
                        tool_result = await dispatcher.dispatch(tool_name, tool_args, state, run_id_str)

                # Apply any context updates from tool
                if tool_result.success and isinstance(tool_result.output, dict):
                    if ctx_update := tool_result.output.get("_context_update"):
                        state = merge_state(state, {"context": {**state.get("context", {}), **ctx_update}})

                # Append tool result to messages
                tool_result_content = json.dumps(tool_result.output) if tool_result.output else tool_result.error or ""
                tool_msg: Message = {
                    "role": "tool",
                    "content": tool_result_content[:8000],  # Cap at 8KB
                    "tool_call_id": tc.get("id"),
                    "tool_calls": None,
                    "name": tool_name,
                }
                messages.append(tool_msg)

            # Update state with new messages after tool round
            state = merge_state(state, {"messages": messages, "last_tool_result": tool_result.output if tool_result.success else None})

        return "llm_call", {
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "cost_usd": total_cost,
            "model_used": llm._model_id,
            "llm_response": messages[-1].get("content", "") if messages else "",
            "memories_retrieved": memories_retrieved_log,
            "_state_update": {"messages": messages},
        }

    async def _handle_tool_node(
        self, node: GraphNode, state: AgentState, dispatcher: ToolDispatcher, run_id_str: str
    ) -> tuple[str, dict[str, Any]]:
        """Execute a dedicated tool node (tool is specified in node config)."""
        tool_name = node.config.get("tool_name", "")
        tool_args = node.config.get("fixed_args", {})

        # Allow dynamic args from state variables
        for k, v in tool_args.items():
            if isinstance(v, str) and v.startswith("$"):
                var_name = v[1:]
                tool_args[k] = state.get("variables", {}).get(var_name, v)

        result = await dispatcher.dispatch(tool_name, tool_args, state, run_id_str)
        return "tool_call", {
            "tool_name": tool_name,
            "tool_input": tool_args,
            "tool_output": result.output,
            "_state_update": {"last_tool_result": result.output},
        }

    async def _handle_condition_node(
        self, node: GraphNode, state: AgentState
    ) -> tuple[str, dict[str, Any]]:
        """Evaluate a condition and log the result (routing handled by graph.get_next_nodes)."""
        expression = node.config.get("expression", {})
        return "condition_eval", {"condition": expression, "state": dict(state)}

    async def _handle_hitl_node(
        self, node: GraphNode, state: AgentState, hitl: HITLController, step_index: int
    ) -> tuple[str, dict[str, Any]]:
        """Pause execution at a HITL gate node."""
        config = node.config
        decision = await hitl.pause_for_approval(
            state=state,
            step_index=step_index,
            node_key=node.key,
            message=config.get("message", "Human approval required"),
            approval_roles=config.get("approval_roles", ["member"]),
            timeout_seconds=config.get("timeout_seconds", 3600),
        )

        if not decision.is_approved:
            return "hitl_pause", {
                "_state_update": {
                    "error": {"type": "hitl_rejected", "message": decision.message}
                }
            }

        # Apply human's edited state if provided
        if decision.edited_state:
            return "hitl_resume", {"_state_update": decision.edited_state}

        return "hitl_resume", {}

    async def _handle_memory_read_node(
        self, node: GraphNode, state: AgentState, memory_mgr: MemoryManager, run_id_str: str
    ) -> tuple[str, dict[str, Any]]:
        """Query memory and inject results into state context."""
        query = node.config.get("query", "")
        k = node.config.get("k", 5)
        context_key = node.config.get("context_key", "memory_results")

        # Allow query from state variable
        if query.startswith("$"):
            query = state.get("variables", {}).get(query[1:], query)

        results = await memory_mgr.retrieve_relevant(query, k=k)
        context_data = [r.to_dict() for r in results]

        return "memory_read", {
            "memories_retrieved": context_data,
            "_state_update": {"context": {**state.get("context", {}), context_key: context_data}},
        }

    async def _handle_memory_write_node(
        self, node: GraphNode, state: AgentState, memory_mgr: MemoryManager
    ) -> tuple[str, dict[str, Any]]:
        """Store content from state into memory."""
        content_path = node.config.get("content_path", "context.final_answer")
        memory_type = node.config.get("memory_type", "episodic")
        importance = node.config.get("importance", 0.5)

        # Resolve content from state
        content = self._resolve_path(content_path, dict(state)) or ""

        if memory_type == "semantic":
            await memory_mgr.store_semantic(str(content))
        else:
            await memory_mgr.store_episodic(str(content), importance=importance)

        return "memory_write", {"content_preview": str(content)[:100]}

    async def _handle_code_node(
        self, node: GraphNode, state: AgentState
    ) -> tuple[str, dict[str, Any]]:
        """Execute code in a Docker sandbox."""
        code = node.config.get("source_code", "")
        language = node.config.get("language", "python")

        result = await self._sandbox.execute_python(code) if language == "python" else await self._sandbox.execute_node(code)

        return "tool_call", {
            "tool_name": "code_executor",
            "tool_output": {"stdout": result.stdout, "stderr": result.stderr},
            "_state_update": {"last_tool_result": {"stdout": result.stdout, "exit_code": result.exit_code}},
        }

    async def _handle_tool_hitl(
        self, tool_name: str, tool_args: dict, state: AgentState, hitl: HITLController, step_index: int
    ) -> Any:
        """Trigger HITL approval for a specific tool call."""
        message = f"Agent wants to call tool '{tool_name}' with args: {json.dumps(tool_args, default=str)[:500]}"
        return await hitl.pause_for_approval(
            state=state,
            step_index=step_index,
            node_key=f"tool_approval_{tool_name}",
            message=message,
            approval_roles=["admin", "owner"],
            timeout_seconds=600,
        )

    # ─── Utility Methods ───────────────────────────────────────────────────────

    async def _emit_event(self, run_id: str, event: dict) -> None:
        """Publish a trace event to the Redis Pub/Sub channel."""
        channel = f"agentcraft:trace:{run_id}"
        try:
            await self.redis.publish(channel, json.dumps(event, default=str))
        except Exception as exc:
            log.warning("engine.emit_error", error=str(exc))

    async def _load_run(self, run_id: uuid.UUID) -> Run | None:
        result = await self.db.execute(select(Run).where(Run.id == run_id))
        return result.scalar_one_or_none()

    async def _load_workflow(self, workflow_id: uuid.UUID) -> Workflow | None:
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(selectinload(Workflow.nodes), selectinload(Workflow.edges))
        )
        return result.scalar_one_or_none()

    async def _get_primary_agent(self, graph: WorkflowGraph, org_id: uuid.UUID) -> dict[str, Any]:
        """Find the first 'agent' node config and load the Agent record."""
        for node in graph.nodes.values():
            if node.node_type == "agent" and node.config.get("agent_id"):
                agent_id = uuid.UUID(node.config["agent_id"])
                result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
                agent = result.scalar_one_or_none()
                if agent:
                    return {
                        "id": agent.id,
                        "model_provider": agent.model_provider,
                        "model_name": agent.model_name,
                        "temperature": agent.temperature,
                        "max_tokens": agent.max_tokens,
                        "top_p": agent.top_p,
                        "system_prompt": agent.system_prompt,
                        "max_iterations": agent.max_iterations,
                    }

        # Default fallback config using Ollama
        return {
            "id": None,
            "model_provider": settings.default_llm_provider,
            "model_name": settings.default_llm_model,
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 1.0,
            "system_prompt": "You are a helpful AI assistant.",
            "max_iterations": settings.default_llm_model and 25,
        }

    async def _load_tool_schemas(self, agent_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Load tool schemas for this agent (for LLM function calling)."""
        # Built-in tools always available
        return build_tools_schema([
            {
                "name": "web_search",
                "description": "Search the web for current information",
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "python_repl",
                "description": "Execute Python code and return stdout/stderr",
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "calculator",
                "description": "Evaluate a mathematical expression",
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression, e.g. '2 * (3 + 4)'"},
                    },
                    "required": ["expression"],
                },
            },
            {
                "name": "http_request",
                "description": "Make an HTTP request to an external API",
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                        "headers": {"type": "object"},
                        "body": {"type": "string"},
                    },
                    "required": ["url"],
                },
            },
        ])

    async def _fail_run(self, run: Run, reason: str) -> None:
        await self.db.execute(
            update(Run)
            .where(Run.id == run.id)
            .values(status="failed", error={"message": reason}, completed_at=datetime.now(UTC))
        )
        await self.db.commit()
        log.error("engine.run_failed", run_id=str(run.id), reason=reason)

    async def _fail_run_from_state(
        self, run_id: uuid.UUID, run_id_str: str, state: AgentState,
        total_tokens_in: int, total_tokens_out: int, total_cost: float
    ) -> None:
        error = state.get("error", {})
        await self.db.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status="failed",
                error=error,
                completed_at=datetime.now(UTC),
                total_tokens_in=total_tokens_in,
                total_tokens_out=total_tokens_out,
                total_cost_usd=total_cost,
            )
        )
        await self.db.commit()
        await self._emit_event(run_id_str, {
            "type": "run_error",
            "run_id": run_id_str,
            "error": error,
            "step_index": state.get("step_count", 0),
        })

    async def _update_run_status(self, run_id: uuid.UUID, status: str) -> None:
        await self.db.execute(
            update(Run).where(Run.id == run_id).values(status=status, completed_at=datetime.now(UTC))
        )
        await self.db.commit()

    @staticmethod
    def _resolve_path(path: str, data: dict) -> Any:
        """Resolve a dot-separated path into a value."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
