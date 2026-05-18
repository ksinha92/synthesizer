"""Workflow validation and execution ordering. No framework dependencies."""

from __future__ import annotations

from collections import defaultdict, deque

VALID_NODE_TYPES = {"discovery", "masking", "synthetic", "subsetting"}

# Aliases from the pre-rename palette (discover/mask/generate/subset). The
# legacy ReactFlow canvas and any DAGs already saved with those types still validate;
# canonicalize_node_type collapses them onto the canonical names below.
#
# Phase 59 F11: ``quality_check`` (and its legacy alias ``export``) have been
# removed. Existing DAGs that reference them will now fail validation on the
# next execute — flagged in release notes.
NODE_TYPE_ALIASES: dict[str, str] = {
    "discover": "discovery",
    "mask": "masking",
    "generate": "synthetic",
    "subset": "subsetting",
}


def canonicalize_node_type(node_type: str) -> str:
    """Map legacy node-type names onto canonical ones; pass canonical through."""
    return NODE_TYPE_ALIASES.get(node_type, node_type)


# Edge compatibility: source_type → allowed target types. Names match the executor
# branches in app/infrastructure/messaging/workflow_tasks.py::_execute_node.
EDGE_RULES: dict[str, set[str]] = {
    "discovery": {"masking", "synthetic", "subsetting"},
    "masking": set(),
    "synthetic": {"masking"},
    "subsetting": {"masking", "synthetic"},
}


class WorkflowValidator:
    """Validates workflow DAG structure."""

    @staticmethod
    def validate_dag(dag: dict) -> list[str]:
        """Validate DAG: cycles, node types, edge compatibility. Returns list of errors."""
        errors = []
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])

        node_map = {n.get("id", ""): n for n in nodes}
        node_ids = set(node_map.keys())

        # Check node types (after canonicalization so legacy names still pass)
        for node in nodes:
            ntype = canonicalize_node_type(node.get("type", ""))
            if ntype not in VALID_NODE_TYPES:
                errors.append(f"Invalid node type '{node.get('type', '')}' on node {node.get('id')}")

        # Check edges reference valid nodes
        for edge in edges:
            src = edge.get("source_node_id", edge.get("source", ""))
            tgt = edge.get("target_node_id", edge.get("target", ""))
            if src not in node_ids:
                errors.append(f"Edge source '{src}' not found in nodes")
            if tgt not in node_ids:
                errors.append(f"Edge target '{tgt}' not found in nodes")

            # Edge compatibility (canonicalize first to handle legacy DAGs)
            if src in node_map and tgt in node_map:
                src_type = canonicalize_node_type(node_map[src].get("type", ""))
                tgt_type = canonicalize_node_type(node_map[tgt].get("type", ""))
                allowed = EDGE_RULES.get(src_type, set())
                if tgt_type not in allowed:
                    errors.append(f"Invalid edge: {src_type} → {tgt_type} (node {src} → {tgt})")

        # Cycle detection
        if WorkflowValidator._has_cycle(node_ids, edges):
            errors.append("DAG contains a cycle")

        return errors

    @staticmethod
    def get_execution_order(dag: dict) -> list[str]:
        """Topological sort of nodes. Returns node IDs in execution order."""
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])

        node_ids = [n.get("id", "") for n in nodes]
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for edge in edges:
            src = edge.get("source_node_id", edge.get("source", ""))
            tgt = edge.get("target_node_id", edge.get("target", ""))
            adjacency[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        queue = deque(nid for nid in node_ids if in_degree.get(nid, 0) == 0)
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    @staticmethod
    def _has_cycle(node_ids: set[str], edges: list[dict]) -> bool:
        visited: set[str] = set()
        rec_stack: set[str] = set()
        adjacency: dict[str, list[str]] = defaultdict(list)

        for edge in edges:
            src = edge.get("source_node_id", edge.get("source", ""))
            tgt = edge.get("target_node_id", edge.get("target", ""))
            adjacency[src].append(tgt)

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for nid in node_ids:
            if nid not in visited:
                if dfs(nid):
                    return True
        return False
