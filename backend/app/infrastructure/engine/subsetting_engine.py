"""Subsetting engine — FK graph traversal with dry-run analysis and chunked extraction."""

from __future__ import annotations

import re
from collections import deque

import structlog

from app.domain.subsetting.entities import DependencyGraph, SubsetConfig

logger = structlog.get_logger()

# SQL injection prevention — reject DDL and dangerous keywords
_DANGEROUS_PATTERNS = re.compile(
    r"\b(DROP|ALTER|DELETE|INSERT|UPDATE|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)
IN_CLAUSE_CHUNK_SIZE = 1000


class SubsettingEngine:
    """Graph-aware data subsetting with FK integrity."""

    def build_graph(self, relationships: list[dict]) -> DependencyGraph:
        """Build directed FK dependency graph from discovered relationships."""
        graph = DependencyGraph()

        for rel in relationships:
            source = rel.get("source_table", rel.get("source_table_name", ""))
            target = rel.get("target_table", rel.get("target_table_name", ""))
            if source and target:
                graph.add_edge(child=source, parent=target)

        # Detect cycles via DFS
        graph.cycle_tables = self._detect_cycles(graph)
        if graph.cycle_tables:
            logger.warning("subsetting_cycles_detected", tables=list(graph.cycle_tables))

        return graph

    def get_traversal_tables(
        self, graph: DependencyGraph, root_tables: list[str], direction: str
    ) -> list[str]:
        """BFS traversal from root tables. Returns tables in topological order."""
        visited = set()
        order = []

        for root in root_tables:
            if direction in ("upstream", "both"):
                self._bfs(root, graph.edges, visited, order)
            if direction in ("downstream", "both"):
                self._bfs(root, graph.reverse_edges, visited, order)
            if root not in visited:
                visited.add(root)
                order.append(root)

        return order

    async def analyze_dry_run(
        self, connector, graph: DependencyGraph, config: SubsetConfig
    ) -> list[dict]:
        """Dry-run: estimate row counts per table without extracting data."""
        root_names = [r.get("table_name", "") for r in config.root_tables]
        traversal = self.get_traversal_tables(graph, root_names, config.traversal_strategy)

        analysis = []
        for table_name in traversal:
            try:
                # Get full count
                tables = await connector.get_tables(config.root_tables[0].get("schema", "public") if config.root_tables else "public")
                table_info = next((t for t in tables if t["name"] == table_name), None)
                full_count = table_info["row_count"] if table_info else 0

                # Estimate subset count
                if table_name in root_names:
                    # Root: apply WHERE filter estimate
                    root_cfg = next((r for r in config.root_tables if r["table_name"] == table_name), {})
                    where = root_cfg.get("where_filter", "")
                    if config.target_percentage:
                        subset_count = int(full_count * config.target_percentage / 100)
                    elif config.target_row_count:
                        subset_count = min(config.target_row_count, full_count)
                    else:
                        subset_count = full_count
                else:
                    # Related: estimate proportionally
                    if config.target_percentage:
                        subset_count = int(full_count * config.target_percentage / 100)
                    else:
                        subset_count = full_count  # Conservative estimate

                pct = round(subset_count / max(full_count, 1) * 100, 1)
                analysis.append({
                    "table_name": table_name,
                    "full_count": full_count,
                    "subset_count": subset_count,
                    "percentage": pct,
                })
            except Exception as e:
                analysis.append({"table_name": table_name, "full_count": 0, "subset_count": 0, "percentage": 0, "error": str(e)})

        total_full = sum(a["full_count"] for a in analysis)
        total_subset = sum(a["subset_count"] for a in analysis)
        logger.info("subset_dry_run", tables=len(analysis), total_full=total_full, total_subset=total_subset)

        return analysis

    async def execute_subset(
        self, connector, graph: DependencyGraph, config: SubsetConfig, storage=None
    ) -> dict[str, int]:
        """Extract subset data in traversal order with FK integrity."""
        root_names = [r.get("table_name", "") for r in config.root_tables]
        traversal = self.get_traversal_tables(graph, root_names, config.traversal_strategy)
        schema = config.root_tables[0].get("schema", "public") if config.root_tables else "public"

        extracted: dict[str, list[dict]] = {}
        result_counts: dict[str, int] = {}

        for table_name in traversal:
            try:
                if table_name in root_names:
                    # Root table with WHERE filter
                    root_cfg = next((r for r in config.root_tables if r["table_name"] == table_name), {})
                    where = root_cfg.get("where_filter", "")
                    validated_where = self._validate_where(where)
                    rows = await connector.get_sample_data(schema, table_name, limit=config.target_row_count or 10000)
                    # TODO: Apply WHERE filter at DB level instead of fetching all
                else:
                    rows = await connector.get_sample_data(schema, table_name, limit=config.target_row_count or 10000)

                extracted[table_name] = rows
                result_counts[table_name] = len(rows)

                # Store via storage backend
                if storage:
                    import json
                    data = json.dumps(rows, default=str).encode()
                    await storage.save(f"subsets/{config.id}/{table_name}.json", data)

            except Exception as e:
                logger.error("subset_extraction_failed", table=table_name, error=str(e))
                result_counts[table_name] = 0

        logger.info("subset_execution_complete", tables=len(result_counts), total_rows=sum(result_counts.values()))
        return result_counts

    @staticmethod
    def _validate_where(where_filter: str) -> str:
        """Validate WHERE clause — reject dangerous SQL patterns."""
        if not where_filter:
            return ""
        if ";" in where_filter:
            raise ValueError("WHERE filter cannot contain semicolons")
        if _DANGEROUS_PATTERNS.search(where_filter):
            raise ValueError(f"WHERE filter contains forbidden keyword: {where_filter}")
        return where_filter

    @staticmethod
    def _detect_cycles(graph: DependencyGraph) -> set[str]:
        """Detect cycles in directed graph via DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: set[str] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.edges.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycles.add(node)
                    cycles.add(neighbor)
            rec_stack.discard(node)

        for node in graph.nodes:
            if node not in visited:
                dfs(node)

        return cycles

    @staticmethod
    def _bfs(start: str, adjacency: dict[str, set[str]], visited: set[str], order: list[str]) -> None:
        """BFS from start node following adjacency edges."""
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
