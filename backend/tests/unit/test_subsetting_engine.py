"""Unit tests for subsetting engine."""

import pytest
from app.domain.subsetting.entities import SubsetConfig
from app.infrastructure.engine.subsetting_engine import SubsettingEngine


class TestGraphBuilding:
    def setup_method(self):
        self.engine = SubsettingEngine()

    def test_build_graph_creates_edges(self):
        rels = [{"source_table": "orders", "target_table": "users"}]
        graph = self.engine.build_graph(rels)
        assert "orders" in graph.nodes
        assert "users" in graph.nodes
        assert "users" in graph.edges["orders"]

    def test_build_graph_empty(self):
        graph = self.engine.build_graph([])
        assert len(graph.nodes) == 0

    def test_cycle_detection(self):
        rels = [
            {"source_table": "a", "target_table": "b"},
            {"source_table": "b", "target_table": "a"},
        ]
        graph = self.engine.build_graph(rels)
        assert len(graph.cycle_tables) > 0


class TestTraversal:
    def setup_method(self):
        self.engine = SubsettingEngine()

    def test_upstream_returns_parents(self):
        rels = [{"source_table": "orders", "target_table": "users"}]
        graph = self.engine.build_graph(rels)
        tables = self.engine.get_traversal_tables(graph, ["orders"], "upstream")
        assert "users" in tables

    def test_downstream_returns_children(self):
        rels = [{"source_table": "orders", "target_table": "users"}]
        graph = self.engine.build_graph(rels)
        tables = self.engine.get_traversal_tables(graph, ["users"], "downstream")
        assert "orders" in tables


class TestWhereValidation:
    def test_valid_where(self):
        result = SubsettingEngine._validate_where("status = 'active' AND created_at > '2024-01-01'")
        assert "status" in result

    def test_rejects_semicolon(self):
        with pytest.raises(ValueError, match="semicolons"):
            SubsettingEngine._validate_where("1=1; DROP TABLE users")

    def test_rejects_ddl(self):
        with pytest.raises(ValueError, match="forbidden"):
            SubsettingEngine._validate_where("1=1 UNION SELECT DROP TABLE users")

    def test_empty_where(self):
        result = SubsettingEngine._validate_where("")
        assert result == ""


class _FakeConnector:
    def __init__(self, row_counts: dict[str, int]):
        self._row_counts = row_counts

    async def get_tables(self, schema):
        return [{"name": name, "row_count": count} for name, count in self._row_counts.items()]

    async def close(self):
        pass


class TestAnalyzeDryRun:
    @pytest.mark.asyncio
    async def test_estimates_subset_counts_for_root_and_related(self):
        engine = SubsettingEngine()
        rels = [
            {"source_table": "orders", "target_table": "users"},
            {"source_table": "order_items", "target_table": "orders"},
        ]
        graph = engine.build_graph(rels)
        config = SubsetConfig(
            name="10pct",
            root_tables=[{"table_name": "orders", "schema": "public"}],
            traversal_strategy="upstream",
            target_percentage=10.0,
        )
        connector = _FakeConnector({"orders": 1000, "users": 500, "order_items": 5000})

        analysis = await engine.analyze_dry_run(connector, graph, config)

        by_name = {row["table_name"]: row for row in analysis}
        assert by_name["orders"]["subset_count"] == 100
        assert by_name["users"]["subset_count"] == 50
        assert all(row["full_count"] >= row["subset_count"] for row in analysis)

    @pytest.mark.asyncio
    async def test_row_count_cap_for_root_table(self):
        engine = SubsettingEngine()
        graph = engine.build_graph([])
        config = SubsetConfig(
            name="cap-test",
            root_tables=[{"table_name": "users", "schema": "public"}],
            target_row_count=50,
        )
        connector = _FakeConnector({"users": 10})

        analysis = await engine.analyze_dry_run(connector, graph, config)

        # Cannot exceed the full count even when target_row_count is larger.
        assert analysis[0]["subset_count"] == 10
