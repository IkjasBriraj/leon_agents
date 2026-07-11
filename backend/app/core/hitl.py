"""
HITL Controller — Human-in-the-Loop Pause/Resume

When an agent reaches a HITL gate node (or a high-risk tool requires approval),
execution must pause until a human reviews and decides.

Architecture:
  - The engine calls `pause_for_approval()` which:
      1. Serializes the full AgentState to a RunCheckpoint in the DB
      2. Sets the Run status to 'paused_hitl'
      3. Publishes a 'hitl_required' event to Redis (WebSocket broadcasts it)
      4. Returns an asyncio.Event that the engine waits on

  - A human sees the 'hitl_required' event in the UI, makes a decision

  - The /api/v1/runs/{id}/resume endpoint is called which:
      1. Pushes the decision to a Redis list: agentcraft:hitl_resume:{run_id}
      2. The engine's `wait_for_decision()` polls this list

  - The engine resumes with the human's decision:
      - approve: continue from where we paused (possibly with edited_state)
      - reject:  set error state and terminate (or route to error handler)
"""

import asyncio
import json
import uuid
from typing import Any, Literal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.state import AgentState, serialize_state
from app.models.run import Run, RunCheckpoint

log = structlog.get_logger()


class HITLDecision:
    """Result of a human-in-the-loop decision."""

    def __init__(
        self,
        decision: Literal["approve", "reject"],
        edited_state: dict[str, Any] | None,
        message: str | None,
        approved_by: str | None,
    ) -> None:
        self.decision = decision
        self.edited_state = edited_state
        self.message = message
        self.approved_by = approved_by

    @property
    def is_approved(self) -> bool:
        return self.decision == "approve"


class HITLController:
    """
    Manages pause, broadcast, and resume of HITL-gated agent runs.

    Usage in engine::

        hitl = HITLController(db, redis, run_id)

        # Pause and wait (blocks the engine until human responds or times out)
        decision = await hitl.pause_for_approval(
            state=current_state,
            step_index=step_index,
            node_key="approval_gate",
            message="Agent wants to send an email. Do you approve?",
            approval_roles=["admin", "owner"],
            timeout_seconds=3600,  # 1 hour
        )

        if decision.is_approved:
            # Use possibly-edited state from human
            state = decision.edited_state or current_state
        else:
            state = {**state, "error": {"type": "hitl_rejected", "message": decision.message}}
    """

    def __init__(self, db: AsyncSession, redis: Any, run_id: str) -> None:
        self.db = db
        self.redis = redis
        self.run_id = run_id

    async def pause_for_approval(
        self,
        state: AgentState,
        step_index: int,
        node_key: str,
        message: str,
        approval_roles: list[str] | None = None,
        timeout_seconds: int = 3600,
    ) -> HITLDecision:
        """
        Pause execution and wait for a human decision.

        Steps:
          1. Save checkpoint to DB
          2. Update Run status to paused_hitl
          3. Publish hitl_required event via Redis Pub/Sub
          4. Poll Redis for human decision (with timeout)
          5. Return HITLDecision with the human's choice
        """
        # 1. Save state checkpoint
        checkpoint = RunCheckpoint(
            run_id=uuid.UUID(self.run_id),
            step_index=step_index,
            state_snapshot=dict(state),
            reason="hitl_pause",
        )
        self.db.add(checkpoint)

        # 2. Update Run to paused status
        from sqlalchemy import update
        from app.models.run import Run
        await self.db.execute(
            update(Run)
            .where(Run.id == uuid.UUID(self.run_id))
            .values(status="paused_hitl", checkpoint_state=dict(state))
        )
        await self.db.commit()

        # 3. Publish hitl_required event to WebSocket clients
        hitl_event = {
            "type": "hitl_required",
            "run_id": self.run_id,
            "step_index": step_index,
            "node_key": node_key,
            "message": message,
            "approval_roles": approval_roles or ["member"],
            "state_snapshot": dict(state),
        }
        channel = f"agentcraft:trace:{self.run_id}"
        await self.redis.publish(channel, json.dumps(hitl_event))

        log.info(
            "hitl.paused",
            run_id=self.run_id,
            node_key=node_key,
            step_index=step_index,
            message=message,
        )

        # 4. Poll Redis list for human decision
        resume_key = f"agentcraft:hitl_resume:{self.run_id}"
        decision_data = None

        # Poll with 5-second intervals up to timeout
        elapsed = 0
        poll_interval = 5

        while elapsed < timeout_seconds:
            # Non-blocking pop from list (LPOP)
            raw = await self.redis.lpop(resume_key)
            if raw:
                decision_data = json.loads(raw)
                break

            # Check for cancellation signal
            cancelled = await self.redis.get(f"agentcraft:cancel:{self.run_id}")
            if cancelled:
                return HITLDecision(
                    decision="reject",
                    edited_state=None,
                    message="Run was cancelled",
                    approved_by=None,
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if not decision_data:
            # Timeout — auto-reject
            log.warning("hitl.timeout", run_id=self.run_id, timeout=timeout_seconds)
            return HITLDecision(
                decision="reject",
                edited_state=None,
                message=f"HITL timed out after {timeout_seconds}s",
                approved_by=None,
            )

        log.info(
            "hitl.decision_received",
            run_id=self.run_id,
            decision=decision_data.get("decision"),
            approved_by=decision_data.get("approved_by"),
        )

        return HITLDecision(
            decision=decision_data.get("decision", "reject"),
            edited_state=decision_data.get("edited_state"),
            message=decision_data.get("message"),
            approved_by=decision_data.get("approved_by"),
        )
