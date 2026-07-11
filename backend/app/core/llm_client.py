"""
LLM Client — Ollama Integration via LiteLLM

Provides a unified interface for:
  - Sending chat completion requests to Ollama (local LLMs)
  - Streaming tokens back to the caller in real-time
  - Token counting and cost estimation
  - Retry logic with exponential backoff on transient errors
  - Building tool schemas for function calling

LiteLLM is used as the routing layer — it provides a uniform
OpenAI-compatible interface to Ollama and other providers,
meaning we can switch providers without changing this client.

Ollama model naming convention for LiteLLM:
  ollama/llama3.2, ollama/mistral, ollama/codellama, etc.
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

import litellm

from app.config import settings
from app.core.state import AgentState, Message

log = structlog.get_logger()

# Disable LiteLLM's verbose logging unless we're in debug mode
litellm.set_verbose = settings.debug


@staticmethod
def _format_model_name(provider: str, model: str) -> str:
    """
    Format model name for LiteLLM routing.

    LiteLLM expects: 'ollama/llama3.2', 'openai/gpt-4o', etc.
    """
    if provider == "ollama":
        return f"ollama/{model}"
    return f"{provider}/{model}"


def build_tools_schema(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert AgentCraft tool definitions to OpenAI function-calling format.

    Each tool must have: name, description, parameters_schema (JSON Schema).
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters_schema", {"type": "object", "properties": {}}),
            },
        }
        for tool in tools
    ]


class LLMResponse:
    """Structured response from the LLM client."""

    def __init__(
        self,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
        finish_reason: str,
        raw_response: Any,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls
        self.model = model
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.duration_ms = duration_ms
        self.finish_reason = finish_reason
        self.raw_response = raw_response

    @property
    def cost_usd(self) -> float:
        """
        Estimate cost. For Ollama (local), cost is always $0.
        For cloud providers, LiteLLM calculates this automatically.
        """
        try:
            return litellm.completion_cost(self.raw_response)
        except Exception:
            return 0.0

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    @property
    def is_finished(self) -> bool:
        return self.finish_reason in ("stop", "end_turn", "tool_use")


class LLMClient:
    """
    Async LLM client wrapping LiteLLM for Ollama support.

    Usage::

        client = LLMClient(provider="ollama", model="llama3.2")
        response = await client.complete(messages, tools=tools_schema)
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
    ) -> None:
        self.provider = provider
        self.model = model or settings.default_llm_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self._model_id = _format_model_name(provider, self.model)

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        system_prompt_override: str | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request and return the full response.

        Retries up to 3 times on network/server errors with exponential backoff.

        Args:
            messages:              Chat message history
            tools:                 Tool schemas for function calling (optional)
            system_prompt_override: Replace the system message with this text

        Returns:
            LLMResponse with content or tool_calls
        """
        # Prepare message list (potentially override system prompt)
        prepared = list(messages)
        if system_prompt_override and prepared and prepared[0]["role"] == "system":
            prepared[0] = {**prepared[0], "content": system_prompt_override}

        # Convert TypedDict messages to plain dicts for LiteLLM
        raw_messages = [dict(m) for m in prepared]
        # Remove None values that LiteLLM doesn't accept
        for msg in raw_messages:
            for k in list(msg.keys()):
                if msg[k] is None:
                    del msg[k]

        kwargs: dict[str, Any] = {
            "model": self._model_id,
            "messages": raw_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Ollama API endpoint override
        if self.provider == "ollama":
            kwargs["api_base"] = settings.ollama_base_url

        start_time = time.monotonic()

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            ):
                with attempt:
                    response = await litellm.acompletion(**kwargs)

        except RetryError as exc:
            raise RuntimeError(
                f"LLM call failed after 3 attempts: {exc}"
            ) from exc

        duration_ms = int((time.monotonic() - start_time) * 1000)

        choice = response.choices[0]
        message = choice.message

        # Parse tool calls if present
        tool_calls_out: list[dict[str, Any]] | None = None
        if message.tool_calls:
            tool_calls_out = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        usage = response.usage or {}
        tokens_in = getattr(usage, "prompt_tokens", 0)
        tokens_out = getattr(usage, "completion_tokens", 0)

        log.info(
            "llm.complete",
            model=self._model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            finish_reason=choice.finish_reason,
        )

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls_out,
            model=self._model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            finish_reason=choice.finish_reason or "stop",
            raw_response=response,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream token chunks from the LLM.

        Yields each text chunk as it arrives. The caller is responsible
        for accumulating chunks and broadcasting via WebSocket.
        """
        raw_messages = [
            {k: v for k, v in dict(m).items() if v is not None}
            for m in messages
        ]

        kwargs: dict[str, Any] = {
            "model": self._model_id,
            "messages": raw_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if self.provider == "ollama":
            kwargs["api_base"] = settings.ollama_base_url
        if tools:
            kwargs["tools"] = tools

        response = await litellm.acompletion(**kwargs)

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    @classmethod
    def from_agent(cls, agent_config: dict[str, Any]) -> "LLMClient":
        """Build an LLMClient from an Agent's configuration dict."""
        return cls(
            provider=agent_config.get("model_provider", settings.default_llm_provider),
            model=agent_config.get("model_name", settings.default_llm_model),
            temperature=agent_config.get("temperature", 0.7),
            max_tokens=agent_config.get("max_tokens", 4096),
            top_p=agent_config.get("top_p", 1.0),
        )


async def get_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding for text using Ollama's embedding model.

    Uses nomic-embed-text by default (768 dimensions).
    Returns a list of floats for pgvector storage.
    """
    try:
        response = await litellm.aembedding(
            model=f"ollama/{settings.embedding_model}",
            input=[text],
            api_base=settings.ollama_base_url,
        )
        return response.data[0]["embedding"]
    except Exception as exc:
        log.error("llm.embedding_failed", error=str(exc), text_preview=text[:100])
        # Return zero vector as fallback
        return [0.0] * settings.embedding_dimensions
