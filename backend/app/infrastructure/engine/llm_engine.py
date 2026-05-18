"""LLM synthetic engine — NLP prompt to structured generation plan to execution."""

from __future__ import annotations

from typing import Any

import structlog

from app.domain.synthetic.entities import SyntheticConfig
from app.domain.synthetic.services import BaseSyntheticEngine
from app.infrastructure.ai.llm_provider import LLMProvider
from app.infrastructure.engine.faker_engine import FakerEngine

logger = structlog.get_logger()

# Allowlist of valid column strategies — prevents code injection via LLM plans
VALID_STRATEGIES = {"categorical", "range", "boolean", "fk", "text", "faker", "null", "uuid", "timestamp", "integer"}

PLAN_PROMPT_TEMPLATE = """You are a data generation planner. Given a database schema and a user request, create a structured generation plan.

Available tables and columns:
{schema_context}

User request: {prompt}

Respond with ONLY valid JSON matching this structure:
{{
  "tables": [{{
    "table_name": "table_name",
    "row_count": 1000,
    "columns": [
      {{"name": "col_name", "strategy": "categorical", "distribution": {{"value1": 0.6, "value2": 0.4}}}},
      {{"name": "col_name", "strategy": "range", "min": 0, "max": 100, "distribution": "uniform"}},
      {{"name": "col_name", "strategy": "boolean", "true_pct": 0.15}},
      {{"name": "col_name", "strategy": "fk", "ref_table": "parent_table", "ref_column": "id"}},
      {{"name": "col_name", "strategy": "text", "max_length": 100}},
      {{"name": "col_name", "strategy": "faker", "provider": "email"}}
    ]
  }}]
}}

Valid strategies: categorical, range, boolean, fk, text, faker, null, uuid, timestamp, integer.
Only use tables and columns that exist in the schema above."""


class LLMEngine(BaseSyntheticEngine):
    """NLP prompt → structured plan → Faker/Statistical execution."""

    def __init__(self, llm_provider: LLMProvider, faker_engine: FakerEngine | None = None) -> None:
        self._llm = llm_provider
        self._faker = faker_engine or FakerEngine()

    async def create_plan(self, prompt: str, schema_metadata: dict) -> dict:
        """Convert NLP prompt to structured generation plan via LLM."""
        # Build schema context
        schema_context = self._build_schema_context(schema_metadata)

        full_prompt = PLAN_PROMPT_TEMPLATE.format(
            schema_context=schema_context,
            prompt=prompt,
        )

        # Call LLM for structured plan
        plan_json = await self._llm.generate_structured(full_prompt, {
            "type": "object",
            "properties": {
                "tables": {"type": "array", "items": {"type": "object"}}
            }
        })

        # Get token usage for cost visibility
        token_info = {
            "call_count": getattr(self._llm, "_call_count", 0),
        }

        # Validate plan
        validated = self._validate_plan(plan_json, schema_metadata)
        validated["_meta"] = {
            "prompt": prompt,
            "tokens": token_info,
            "estimated_time_seconds": self._estimate_time(validated),
        }

        await logger.ainfo("nlp_plan_created", tables=len(validated.get("tables", [])))
        return validated

    async def generate(
        self, config: SyntheticConfig, schema_metadata: dict
    ) -> dict[str, list[dict]]:
        """Execute a generation plan by converting to Faker configs."""
        plan = config.config.get("plan", {})
        if not plan or "tables" not in plan:
            raise ValueError("No generation plan in config. Run create_plan first.")

        # Convert LLM plan columns to Faker-compatible config
        faker_tables = []
        for table in plan["tables"]:
            faker_columns = []
            for col in table.get("columns", []):
                faker_col = self._plan_column_to_faker(col)
                faker_columns.append(faker_col)

            faker_tables.append({
                "table_name": table["table_name"],
                "row_count": table.get("row_count", config.row_count),
                "columns": faker_columns,
            })

        # Create a Faker config and delegate
        faker_config = SyntheticConfig(
            project_id=config.project_id,
            source_connection_id=config.source_connection_id,
            tables=faker_tables,
            row_count=config.row_count,
            config=config.config,
        )

        return await self._faker.generate(faker_config, schema_metadata)

    async def preview(
        self, config: SyntheticConfig, schema_metadata: dict, limit: int = 10
    ) -> dict[str, list[dict]]:
        preview_config = SyntheticConfig(
            **{k: v for k, v in config.__dict__.items() if k != "_events"},
            _events=[],
        )
        preview_config.row_count = limit
        return await self.generate(preview_config, schema_metadata)

    def _build_schema_context(self, schema_metadata: dict) -> str:
        """Build human-readable schema context for the LLM prompt."""
        tables = schema_metadata.get("tables", [])
        if not tables:
            return "No tables discovered yet."

        lines = []
        for table in tables:
            cols = ", ".join(
                f"{c.get('name', c.get('column_name', '?'))} ({c.get('data_type', '?')})"
                for c in table.get("columns", [])
            )
            lines.append(f"- {table.get('table_name', '?')}: {cols}")
        return "\n".join(lines)

    def _validate_plan(self, plan: dict, schema_metadata: dict) -> dict:
        """Validate plan structure and strategies against allowlist."""
        if not isinstance(plan, dict) or "tables" not in plan:
            return {"tables": []}

        valid_tables = []
        for table in plan.get("tables", []):
            if not isinstance(table, dict) or "table_name" not in table:
                continue

            valid_columns = []
            for col in table.get("columns", []):
                if not isinstance(col, dict):
                    continue

                strategy = col.get("strategy", "text")
                if strategy not in VALID_STRATEGIES:
                    logger.warning("nlp_invalid_strategy", strategy=strategy, column=col.get("name"))
                    col["strategy"] = "text"  # Fallback to safe default

                valid_columns.append(col)

            table["columns"] = valid_columns
            valid_tables.append(table)

        return {"tables": valid_tables}

    def _plan_column_to_faker(self, col: dict) -> dict:
        """Convert LLM plan column config to Faker-compatible config."""
        strategy = col.get("strategy", "text")
        result: dict[str, Any] = {
            "column_name": col.get("name", "unknown"),
            "data_type": "varchar",
            "pii_type": "none",
        }

        if strategy == "categorical":
            result["_categorical"] = col.get("distribution", {})
        elif strategy == "range":
            result["data_type"] = "numeric"
            result["_range"] = {"min": col.get("min", 0), "max": col.get("max", 100)}
        elif strategy == "boolean":
            result["data_type"] = "boolean"
            result["_true_pct"] = col.get("true_pct", 0.5)
        elif strategy == "fk":
            result["is_foreign_key"] = True
            result["fk_references"] = {"table": col.get("ref_table"), "column": col.get("ref_column", "id")}
        elif strategy == "faker":
            result["pii_type"] = col.get("provider", "text")
        elif strategy == "uuid":
            result["data_type"] = "uuid"
            result["is_primary_key"] = True
        elif strategy == "integer":
            result["data_type"] = "integer"
        elif strategy == "timestamp":
            result["data_type"] = "timestamp"
        # Default: text/varchar

        return result

    @staticmethod
    def _estimate_time(plan: dict) -> float:
        """Estimate generation time in seconds based on plan."""
        total_rows = sum(t.get("row_count", 0) for t in plan.get("tables", []))
        return max(1.0, total_rows / 1000)  # ~1K rows/sec for Faker
