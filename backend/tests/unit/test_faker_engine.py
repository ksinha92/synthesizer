"""Unit tests for Faker synthetic engine."""

import pytest

from app.infrastructure.engine.faker_engine import FakerEngine, _build_generation_order
from app.domain.synthetic.entities import SyntheticConfig
from app.domain.synthetic.value_objects import GenerationMethod


class TestFakerPIIMapping:
    @pytest.mark.asyncio
    async def test_pii_aware_email(self):
        engine = FakerEngine(seed=42)
        config = SyntheticConfig(
            generation_method=GenerationMethod.FAKER,
            row_count=5,
            tables=[{
                "table_name": "users",
                "row_count": 5,
                "columns": [
                    {"column_name": "id", "data_type": "uuid", "is_primary_key": True},
                    {"column_name": "email", "data_type": "varchar", "pii_type": "email"},
                ],
            }],
        )
        result = await engine.generate(config, {"relationships": []})
        assert "users" in result
        assert len(result["users"]) == 5
        for row in result["users"]:
            assert "@" in str(row["email"])

    @pytest.mark.asyncio
    async def test_pii_aware_ssn(self):
        engine = FakerEngine(seed=42)
        config = SyntheticConfig(
            generation_method=GenerationMethod.FAKER,
            row_count=3,
            tables=[{
                "table_name": "people",
                "row_count": 3,
                "columns": [
                    {"column_name": "id", "data_type": "uuid", "is_primary_key": True},
                    {"column_name": "ssn", "data_type": "varchar", "pii_type": "ssn"},
                ],
            }],
        )
        result = await engine.generate(config, {"relationships": []})
        for row in result["people"]:
            assert "-" in str(row["ssn"])  # SSN format has dashes

    @pytest.mark.asyncio
    async def test_type_mapping_integer(self):
        engine = FakerEngine(seed=42)
        config = SyntheticConfig(
            generation_method=GenerationMethod.FAKER,
            row_count=3,
            tables=[{
                "table_name": "items",
                "row_count": 3,
                "columns": [
                    {"column_name": "id", "data_type": "uuid", "is_primary_key": True},
                    {"column_name": "count", "data_type": "integer", "pii_type": "none"},
                ],
            }],
        )
        result = await engine.generate(config, {"relationships": []})
        for row in result["items"]:
            assert isinstance(row["count"], int)


class TestSeedReproducibility:
    @pytest.mark.asyncio
    async def test_same_seed_same_output(self):
        config = SyntheticConfig(
            generation_method=GenerationMethod.FAKER,
            row_count=5,
            tables=[{
                "table_name": "t",
                "row_count": 5,
                "columns": [
                    {"column_name": "id", "data_type": "uuid", "is_primary_key": True},
                    {"column_name": "name", "data_type": "varchar", "pii_type": "person_name"},
                ],
            }],
        )
        engine1 = FakerEngine(seed=123)
        result1 = await engine1.generate(config, {"relationships": []})

        engine2 = FakerEngine(seed=123)
        result2 = await engine2.generate(config, {"relationships": []})

        assert result1["t"] == result2["t"]


class TestTopologicalSort:
    def test_parents_first(self):
        tables = [
            {"table_name": "orders"},
            {"table_name": "users"},
        ]
        relationships = [
            {"source_table": "orders", "target_table": "users"},  # orders depends on users
        ]
        order, cycles = _build_generation_order(tables, relationships)
        assert order.index("users") < order.index("orders")

    def test_cycle_detection(self):
        tables = [
            {"table_name": "employees"},
        ]
        relationships = [
            {"source_table": "employees", "target_table": "employees"},  # self-ref
        ]
        order, cycles = _build_generation_order(tables, relationships)
        # Self-ref shouldn't cause issues (same source and target filtered)
        assert "employees" in order

    def test_no_relationships(self):
        tables = [{"table_name": "a"}, {"table_name": "b"}]
        order, cycles = _build_generation_order(tables, [])
        assert len(order) == 2
        assert len(cycles) == 0
