"""
Core State Management — AgentState TypedDict and utilities.

The AgentState is the single source of truth for an executing agent run.
Every node in the graph reads from and writes to this dictionary.

Design principles:
  1. Immutability-by-convention — nodes return new state dicts, not mutations
  2. Serializability — all values must be JSON-serializable for checkpointing
  3. Type safety — TypedDict catches errors at static analysis time
  4. Diffability — compute_delta() enables the trace debugger to show changes
"""

import copy
import json
from datetime import datetime, timezone
from typing import Any, TypedDict


class Message(TypedDict):
    """A single message in the agent's conversation history."""
    role: str       # 'system' | 'user' | 'assistant' | 'tool'
    content: str
    tool_call_id: str | None   # Present for 'tool' role messages
    tool_calls: list | None    # Present for 'assistant' tool-calling messages
    name: str | None           # Tool name for 'tool' role messages


class LoopCounter(TypedDict):
    """Tracks iteration count for a loop node to prevent infinite loops."""
    node_key: str
    count: int
    max_count: int


class AgentState(TypedDict, total=False):
    """
    The complete state dictionary passed through the execution graph.

    Each node receives this state and returns an updated version.
    The engine merges updates back into the canonical state.

    Fields:
      messages:       Full conversation history (LLM chat messages)
      context:        Structured key-value store for arbitrary data
      variables:      User-defined workflow variables (set from input_data)
      current_node:   The key of the node currently executing
      step_count:     Total number of steps executed in this run
      loop_counters:  Per-node iteration counts (prevents infinite loops)
      last_tool_result: Output from the most recently executed tool
      pending_hitl:   Non-None when paused for human approval
      error:          Set if the current step encountered an error
      metadata:       Run-level metadata (run_id, workflow_id, org_id, etc.)
      output:         Final output once execution is complete
    """
    messages: list[Message]
    context: dict[str, Any]
    variables: dict[str, Any]
    current_node: str
    step_count: int
    loop_counters: dict[str, LoopCounter]
    last_tool_result: dict[str, Any] | None
    pending_hitl: dict[str, Any] | None
    error: dict[str, Any] | None
    metadata: dict[str, Any]
    output: Any


def create_initial_state(
    run_id: str,
    workflow_id: str,
    org_id: str,
    input_data: dict[str, Any],
    system_prompt: str,
) -> AgentState:
    """
    Construct the initial AgentState for a new run.

    The system prompt is placed as the first 'system' message.
    Input data is unpacked into 'variables' for workflow access.
    """
    initial_message: Message = {
        "role": "system",
        "content": system_prompt,
        "tool_call_id": None,
        "tool_calls": None,
        "name": None,
    }

    # If input_data has a 'message' key, add it as a user message
    messages: list[Message] = [initial_message]
    if user_message := input_data.get("message"):
        messages.append({
            "role": "user",
            "content": str(user_message),
            "tool_call_id": None,
            "tool_calls": None,
            "name": None,
        })

    return AgentState(
        messages=messages,
        context={},
        variables=input_data,
        current_node="start",
        step_count=0,
        loop_counters={},
        last_tool_result=None,
        pending_hitl=None,
        error=None,
        metadata={
            "run_id": run_id,
            "workflow_id": workflow_id,
            "org_id": org_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        output=None,
    )


def merge_state(current: AgentState, updates: dict[str, Any]) -> AgentState:
    """
    Return a new AgentState with updates applied.

    This is a shallow merge for top-level keys.
    For nested dicts like 'context', use explicit dot-path updates.
    """
    return AgentState(**{**current, **updates})  # type: ignore[return-value]


def compute_delta(before: AgentState, after: AgentState) -> dict[str, Any]:
    """
    Compute the diff between two state dicts.

    Returns a dict with only the changed keys/values.
    Used by the Trace Debugger to highlight what changed in each step.

    Example output:
        {
            "step_count": {"before": 2, "after": 3},
            "messages":   {"added": 1, "total": 4},
            "context":    {"changed_keys": ["result", "tool_output"]}
        }
    """
    delta: dict[str, Any] = {}

    all_keys = set(before.keys()) | set(after.keys())

    for key in all_keys:
        before_val = before.get(key)  # type: ignore[attr-defined]
        after_val = after.get(key)    # type: ignore[attr-defined]

        if before_val == after_val:
            continue

        # Special handling for messages list — show count delta
        if key == "messages":
            b_msgs = before_val or []
            a_msgs = after_val or []
            if len(b_msgs) != len(a_msgs):
                delta["messages"] = {
                    "before_count": len(b_msgs),
                    "after_count": len(a_msgs),
                    "added": len(a_msgs) - len(b_msgs),
                }
        # For dicts, show which keys changed
        elif isinstance(before_val, dict) and isinstance(after_val, dict):
            changed_keys = [
                k for k in set(before_val.keys()) | set(after_val.keys())
                if before_val.get(k) != after_val.get(k)
            ]
            if changed_keys:
                delta[key] = {"changed_keys": changed_keys}
        else:
            # Simple scalar change
            delta[key] = {"before": before_val, "after": after_val}

    return delta


def serialize_state(state: AgentState) -> str:
    """Serialize AgentState to a JSON string for checkpoint storage."""
    return json.dumps(dict(state), default=str)


def deserialize_state(raw: str | dict) -> AgentState:
    """Deserialize AgentState from JSON string or dict (from DB JSONB)."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw
    return AgentState(**data)  # type: ignore[return-value]
