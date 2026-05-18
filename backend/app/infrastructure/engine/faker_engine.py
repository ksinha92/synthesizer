"""Faker synthetic data engine — PII-aware with FK topological ordering."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import structlog
from faker import Faker

from app.domain.discovery.value_objects import PIIType
from app.domain.synthetic.entities import SyntheticConfig
from app.domain.synthetic.services import BaseSyntheticEngine

logger = structlog.get_logger()

# PII type → Faker method mapping
_PROFILE_PASSTHROUGH = object()  # Sentinel: profile can't constrain this value


def _weighted_choice(faker, choices: list, weights: list):
    """Sample one element from `choices` proportional to `weights`."""
    total = sum(weights) or 1
    r = faker.random_int(min=1, max=total)
    cum = 0
    for c, w in zip(choices, weights):
        cum += w
        if r <= cum:
            return c
    return choices[-1]


_PII_FAKER_MAP: dict[PIIType, str] = {
    PIIType.EMAIL: "email",
    PIIType.PHONE: "phone_number",
    PIIType.SSN: "ssn",
    PIIType.PERSON_NAME: "name",
    PIIType.ADDRESS: "address",
    PIIType.CREDIT_CARD: "credit_card_number",
    PIIType.IP_ADDRESS: "ipv4",
    PIIType.DATE_OF_BIRTH: "date_of_birth",
    PIIType.FINANCIAL_ACCOUNT: "iban",
    PIIType.MEDICAL_RECORD: "bothify",  # fallback pattern: "MRN-####"
}

# SQL type → Faker method mapping
_TYPE_FAKER_MAP: dict[str, str] = {
    "integer": "random_int",
    "int": "random_int",
    "bigint": "random_int",
    "smallint": "random_int",
    "boolean": "boolean",
    "date": "date_this_decade",
    "timestamp": "date_time_this_year",
    "timestamp with time zone": "date_time_this_year",
    "timestamp without time zone": "date_time_this_year",
    "numeric": "pyfloat",
    "decimal": "pyfloat",
    "double precision": "pyfloat",
    "float": "pyfloat",
    "real": "pyfloat",
    "uuid": "uuid4",
    "jsonb": "pydict",
    "json": "pydict",
}


class FakerEngine(BaseSyntheticEngine):
    """Fast synthetic data via Faker — PII-type-aware with FK ordering."""

    def __init__(self, seed: int | None = None, locale: str = "en_US") -> None:
        self._faker = Faker(locale)
        if seed is not None:
            Faker.seed(seed)
        self._seed = seed

    async def generate(
        self, config: SyntheticConfig, schema_metadata: dict
    ) -> dict[str, list[dict]]:
        tables_config = config.tables or []
        relationships = schema_metadata.get("relationships", [])
        column_profiles = schema_metadata.get("column_profiles") or {}

        # Topological sort with cycle detection
        order, cycles = _build_generation_order(tables_config, relationships)

        generated: dict[str, list[dict]] = {}

        for table_name in order:
            table_cfg = next((t for t in tables_config if t.get("table_name") == table_name), None)
            if not table_cfg:
                continue

            row_count = table_cfg.get("row_count", config.row_count)
            columns = table_cfg.get("columns", [])

            rows = self._generate_table(
                columns, row_count, generated, table_name in cycles,
                column_profiles=column_profiles,
            )
            generated[table_name] = rows

        # Second pass: fix cyclic FK columns
        for table_name in cycles:
            if table_name in generated:
                self._fix_cyclic_fks(table_name, generated, tables_config)

        logger.info(
            "faker_generation_complete",
            tables=len(generated),
            total_rows=sum(len(rows) for rows in generated.values()),
            seed=self._seed,
        )

        return generated

    async def preview(
        self, config: SyntheticConfig, schema_metadata: dict, limit: int = 10
    ) -> dict[str, list[dict]]:
        # Override row counts for preview
        preview_config = SyntheticConfig(
            **{**config.__dict__, "row_count": limit, "_events": []}
        )
        for table in (preview_config.tables or []):
            table["row_count"] = limit
        return await self.generate(preview_config, schema_metadata)

    def _generate_table(
        self,
        columns: list[dict],
        row_count: int,
        generated: dict[str, list[dict]],
        has_cycle: bool,
        column_profiles: dict | None = None,
    ) -> list[dict]:
        column_profiles = column_profiles or {}
        rows = []
        for _ in range(row_count):
            row: dict[str, Any] = {}
            for col in columns:
                col_name = col.get("column_name", col.get("name", ""))
                pii_type = col.get("pii_type", "none")
                data_type = col.get("data_type", "varchar").lower()
                is_pk = col.get("is_primary_key", False)
                is_fk = col.get("is_foreign_key", False)
                fk_ref = col.get("fk_references")
                nullable = col.get("is_nullable", False)
                profile = column_profiles.get(col_name)

                # Primary key
                if is_pk:
                    row[col_name] = self._faker.uuid4()
                    continue

                # FK column — reference parent data
                if is_fk and fk_ref and not has_cycle:
                    parent_table = fk_ref.get("table", "")
                    parent_col = fk_ref.get("column", "id")
                    parent_rows = generated.get(parent_table, [])
                    if parent_rows:
                        row[col_name] = self._faker.random_element(
                            [r.get(parent_col) for r in parent_rows if parent_col in r]
                        ) if parent_rows else None
                        continue

                # Null-rate: honor profile's null_rate when present, else 10% default.
                null_chance = int((profile.null_rate * 100) if profile else 10)
                if nullable and self._faker.boolean(chance_of_getting_true=null_chance):
                    row[col_name] = None
                    continue

                # PII-aware generation wins over profile (PII flag prevents leakage).
                if pii_type and pii_type != "none":
                    row[col_name] = self._generate_pii(PIIType(pii_type))
                    continue

                # Profile-guided generation
                if profile is not None:
                    sampled = self._sample_from_profile(profile, data_type)
                    if sampled is not _PROFILE_PASSTHROUGH:
                        row[col_name] = sampled
                        continue

                # Type-based generation (fallback)
                row[col_name] = self._generate_by_type(data_type, col)

            rows.append(row)
        return rows

    def _sample_from_profile(self, profile, data_type: str):
        """Draw a value guided by a ColumnProfile.

        Returns _PROFILE_PASSTHROUGH if the profile can't constrain this column
        (caller falls back to type-based generation).
        """
        ptype = getattr(profile, "dtype", None)
        if ptype == "numeric":
            lo = getattr(profile, "minimum", None)
            hi = getattr(profile, "maximum", None)
            if lo is None or hi is None or lo == hi:
                return lo if lo is not None else _PROFILE_PASSTHROUGH
            # Integers if the underlying SQL/file type is integer-like.
            if any(token in data_type for token in ("int", "numeric_int", "integer")):
                return int(self._faker.random_int(min=int(lo), max=int(hi)))
            return self._faker.pyfloat(min_value=lo, max_value=hi)
        if ptype == "categorical":
            freqs = getattr(profile, "frequencies", None) or {}
            if not freqs:
                return _PROFILE_PASSTHROUGH
            choices = list(freqs.keys())
            weights = list(freqs.values())
            return self._faker.random_elements(elements=choices, length=1)[0] if len(choices) == 1 else self._faker.random_choices(elements=choices, length=1)[0] if False else _weighted_choice(self._faker, choices, weights)
        if ptype == "string":
            hint = getattr(profile, "pattern_hint", None)
            samples = getattr(profile, "sample_values", None) or []
            if samples:
                return self._faker.random_element(samples)
            if hint:
                # Fall back to type-based generation; pattern_hint is informative only.
                return _PROFILE_PASSTHROUGH
        return _PROFILE_PASSTHROUGH

    def _generate_pii(self, pii_type: PIIType) -> Any:
        method_name = _PII_FAKER_MAP.get(pii_type)
        if method_name and hasattr(self._faker, method_name):
            return getattr(self._faker, method_name)()
        return self._faker.text(max_nb_chars=50)

    def _generate_by_type(self, data_type: str, col: dict) -> Any:
        # Check exact match first, then prefix match
        method_name = _TYPE_FAKER_MAP.get(data_type)
        if not method_name:
            for type_key, method in _TYPE_FAKER_MAP.items():
                if data_type.startswith(type_key):
                    method_name = method
                    break

        if method_name and hasattr(self._faker, method_name):
            return getattr(self._faker, method_name)()

        # Default: varchar/text
        max_len = col.get("character_maximum_length", 100) or 100
        return self._faker.text(max_nb_chars=min(max_len, 200))

    def _fix_cyclic_fks(
        self,
        table_name: str,
        generated: dict[str, list[dict]],
        tables_config: list[dict],
    ) -> None:
        """Second pass: fill in cyclic FK columns that were set to NULL."""
        table_cfg = next((t for t in tables_config if t.get("table_name") == table_name), None)
        if not table_cfg:
            return
        for col in table_cfg.get("columns", []):
            if col.get("is_foreign_key") and col.get("fk_references"):
                fk_ref = col["fk_references"]
                parent_table = fk_ref.get("table", "")
                parent_col = fk_ref.get("column", "id")
                parent_rows = generated.get(parent_table, [])
                if parent_rows:
                    col_name = col.get("column_name", col.get("name", ""))
                    valid_ids = [r.get(parent_col) for r in parent_rows if parent_col in r]
                    if valid_ids:
                        for row in generated[table_name]:
                            if row.get(col_name) is None:
                                row[col_name] = self._faker.random_element(valid_ids)


def _build_generation_order(
    tables: list[dict], relationships: list[dict]
) -> tuple[list[str], set[str]]:
    """Topological sort with cycle detection. Returns (ordered_names, cycle_tables)."""
    table_names = [t.get("table_name", "") for t in tables]
    if not table_names:
        return [], set()

    # Build adjacency: child → parents
    deps: dict[str, set[str]] = defaultdict(set)
    for rel in relationships:
        source = rel.get("source_table", "")
        target = rel.get("target_table", "")
        if source in table_names and target in table_names and source != target:
            deps[source].add(target)  # source depends on target (FK)

    # Kahn's algorithm with cycle detection
    in_degree: dict[str, int] = {name: 0 for name in table_names}
    for table, parents in deps.items():
        in_degree[table] = len(parents)

    queue = [t for t in table_names if in_degree.get(t, 0) == 0]
    order = []
    visited = set()

    while queue:
        node = queue.pop(0)
        order.append(node)
        visited.add(node)
        for table in table_names:
            if node in deps.get(table, set()):
                in_degree[table] -= 1
                if in_degree[table] == 0:
                    queue.append(table)

    # Tables not in order have cycles
    cycles = set(table_names) - visited
    if cycles:
        logger.warning("faker_circular_fk_detected", tables=list(cycles))
        order.extend(cycles)  # Add cyclic tables at end (generate with NULL FKs)

    return order, cycles
