"""
Graph Executor — Workflow graph loading and traversal.

Loads a workflow's nodes/edges from the database into an efficient
in-memory representation, then provides methods to:

  - Find the start node
  - Get candidate next nodes from a given node
  - Evaluate conditional edges against the current state
  - Detect and track cycles (loops)

Key insight: The graph deliberately supports cycles (loops).
An agent can move back to an earlier node based on conditional logic,
creating iterative reasoning loops (Plan → Execute → Reflect → Re-plan).

We prevent infinite loops through per-node loop counters in AgentState.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.state import AgentState
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode

log = structlog.get_logger()


@dataclass
class GraphNode:
    """In-memory representation of a workflow node."""
    id: uuid.UUID
    key: str
    node_type: str
    label: str | None
    config: dict[str, Any]

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class GraphEdge:
    """In-memory representation of a workflow edge."""
    id: uuid.UUID
    source_key: str
    target_key: str
    edge_type: str
    condition: dict[str, Any] | None
    priority: int


@dataclass
class WorkflowGraph:
    """
    In-memory directed graph representation of a workflow.

    Built once per run from the DB models, then used throughout execution.
    Supports both DAG and cyclic (loop) topologies.
    """
    nodes: dict[str, GraphNode] = field(default_factory=dict)     # key → node
    edges: dict[str, list[GraphEdge]] = field(default_factory=dict)  # source_key → edges

    @classmethod
    def from_orm(cls, workflow: Workflow) -> "WorkflowGraph":
        """Build a WorkflowGraph from SQLAlchemy ORM models."""
        graph = cls()

        # Index nodes by their key
        for node in workflow.nodes:
            graph.nodes[node.node_key] = GraphNode(
                id=node.id,
                key=node.node_key,
                node_type=node.node_type,
                label=node.label,
                config=node.config or {},
            )

        # Index edges by source node key
        for edge in workflow.edges:
            # Resolve source/target keys from IDs
            source_node = next(
                (n for n in workflow.nodes if n.id == edge.source_node_id), None
            )
            target_node = next(
                (n for n in workflow.nodes if n.id == edge.target_node_id), None
            )
            if not source_node or not target_node:
                log.warning(
                    "graph.edge_missing_node",
                    edge_id=str(edge.id),
                    source_id=str(edge.source_node_id),
                    target_id=str(edge.target_node_id),
                )
                continue

            graph_edge = GraphEdge(
                id=edge.id,
                source_key=source_node.node_key,
                target_key=target_node.node_key,
                edge_type=edge.edge_type,
                condition=edge.condition,
                priority=edge.priority,
            )

            if source_node.node_key not in graph.edges:
                graph.edges[source_node.node_key] = []
            graph.edges[source_node.node_key].append(graph_edge)

        # Sort edges by priority descending (higher priority checked first)
        for key in graph.edges:
            graph.edges[key].sort(key=lambda e: e.priority, reverse=True)

        return graph

    def get_start_node(self) -> GraphNode | None:
        """Find the entry node (type='start')."""
        for node in self.nodes.values():
            if node.node_type == "start":
                return node
        return None

    def get_next_nodes(
        self,
        current_key: str,
        state: AgentState,
    ) -> list[GraphNode]:
        """
        Determine which node(s) to execute next from the current node.

        Logic:
          1. Get all outgoing edges from current node
          2. For 'default' edges — always include the target
          3. For 'conditional' edges — evaluate condition against state
          4. For 'error' edges — only include if state has an error
          5. Returns sorted by priority (already sorted)

        The engine calls this after each step to advance the graph.
        """
        outgoing = self.edges.get(current_key, [])
        next_nodes: list[GraphNode] = []

        for edge in outgoing:
            target = self.nodes.get(edge.target_key)
            if not target:
                continue

            if edge.edge_type == "default":
                next_nodes.append(target)

            elif edge.edge_type == "conditional":
                if self._evaluate_condition(edge.condition, state):
                    next_nodes.append(target)

            elif edge.edge_type == "error":
                if state.get("error"):
                    next_nodes.append(target)

            elif edge.edge_type == "loop_back":
                # Loop-back edges are treated as conditional —
                # they're traversed unless max iterations reached
                if not self._is_loop_exhausted(edge.source_key, state):
                    next_nodes.append(target)
                else:
                    log.warning(
                        "graph.loop_exhausted",
                        node_key=edge.source_key,
                        max=state.get("loop_counters", {})
                        .get(edge.source_key, {})
                        .get("max_count", "?"),
                    )

        return next_nodes

    def _evaluate_condition(
        self, condition: dict | None, state: AgentState
    ) -> bool:
        """
        Evaluate a condition expression against the current state.

        Condition format (JSON):
          {
            "field": "context.result_status",  # dot-path into state
            "op": "eq",                         # operator
            "value": "needs_retry"              # comparison value
          }

        Supported operators:
          eq, ne, gt, lt, gte, lte, contains, not_contains,
          is_null, is_not_null, truthy, falsy
        """
        if not condition:
            return True

        try:
            field_path = condition.get("field", "")
            op = condition.get("op", "eq")
            expected = condition.get("value")

            # Resolve dot-path (e.g., "context.result_status")
            actual = self._resolve_path(field_path, dict(state))

            match op:
                case "eq":
                    return actual == expected
                case "ne":
                    return actual != expected
                case "gt":
                    return float(actual) > float(expected)
                case "lt":
                    return float(actual) < float(expected)
                case "gte":
                    return float(actual) >= float(expected)
                case "lte":
                    return float(actual) <= float(expected)
                case "contains":
                    return expected in (actual or "")
                case "not_contains":
                    return expected not in (actual or "")
                case "is_null":
                    return actual is None
                case "is_not_null":
                    return actual is not None
                case "truthy":
                    return bool(actual)
                case "falsy":
                    return not bool(actual)
                case _:
                    log.warning("graph.unknown_op", op=op)
                    return False
        except Exception as exc:
            log.error("graph.condition_eval_error", error=str(exc), condition=condition)
            return False

    def _resolve_path(self, path: str, data: dict) -> Any:
        """Resolve a dot-separated path like 'context.result_status' into a value."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _is_loop_exhausted(self, node_key: str, state: AgentState) -> bool:
        """Return True if a loop node has hit its maximum iteration count."""
        counters = state.get("loop_counters", {})
        counter = counters.get(node_key)
        if not counter:
            return False
        return counter.get("count", 0) >= counter.get("max_count", 25)

    def increment_loop_counter(self, node_key: str, state: AgentState, max_count: int = 25) -> AgentState:
        """Increment the iteration counter for a looping node."""
        counters = dict(state.get("loop_counters", {}))
        if node_key not in counters:
            counters[node_key] = {"node_key": node_key, "count": 0, "max_count": max_count}
        counters[node_key]["count"] += 1
        return {**state, "loop_counters": counters}  # type: ignore[return-value]

    def detect_cycles(self) -> list[list[str]]:
        """
        Detect all cycles in the graph using DFS.

        Returns a list of cycles, each as a list of node keys.
        Used for:
          - Workflow validation (warn user about loops)
          - Setting is_cyclic flag on the Workflow model
        """
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node_key: str, path: list[str]) -> None:
            visited.add(node_key)
            rec_stack.add(node_key)
            path.append(node_key)

            for edge in self.edges.get(node_key, []):
                target = edge.target_key
                if target not in visited:
                    dfs(target, path)
                elif target in rec_stack:
                    # Found a cycle — extract it
                    cycle_start = path.index(target)
                    cycles.append(path[cycle_start:] + [target])

            path.pop()
            rec_stack.discard(node_key)

        for key in self.nodes:
            if key not in visited:
                dfs(key, [])

        return cycles

    def validate(self) -> tuple[bool, list[str], list[str]]:
        """
        Validate the graph structure.

        Returns:
            (is_valid, errors, warnings)
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Must have a start node
        if not any(n.node_type == "start" for n in self.nodes.values()):
            errors.append("Workflow must have a 'start' node")

        # Must have at least one end node
        if not any(n.node_type == "end" for n in self.nodes.values()):
            errors.append("Workflow must have at least one 'end' node")

        # Detect unreachable nodes
        start = self.get_start_node()
        if start:
            reachable: set[str] = set()
            def traverse(key: str) -> None:
                if key in reachable:
                    return
                reachable.add(key)
                for edge in self.edges.get(key, []):
                    traverse(edge.target_key)
            traverse(start.key)

            unreachable = set(self.nodes.keys()) - reachable
            for key in unreachable:
                warnings.append(f"Node '{key}' is unreachable from start")

        # Warn about cycles
        cycles = self.detect_cycles()
        for cycle in cycles:
            warnings.append(f"Cycle detected: {' → '.join(cycle)}")

        return len(errors) == 0, errors, warnings
