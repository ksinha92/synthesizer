"""Multi-file generation orchestrator.

Topologically sorts schemas by cross-file FK declarations, runs FakerEngine
once per schema, propagates parent rows so child files can reference parent
PKs via the same FK plumbing FakerEngine already supports for single-table
runs.
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import structlog

from app.domain.synthetic.entities import SyntheticConfig
from app.domain.synthetic.file_schema import FileSchemaDefinition, FileSetDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.engine.faker_engine import FakerEngine
from app.infrastructure.writers.registry import get_writer

logger = structlog.get_logger()


class FileSetOrchestrator:
    """Generate every file in a FileSetDefinition with FK integrity."""

    def __init__(
        self,
        file_set: FileSetDefinition,
        row_counts: dict[str, int] | None = None,
        seed: int | None = None,
        masking_rules_by_schema: dict[str, list[dict]] | None = None,
        masking_salt: str | None = None,
        initial_masking_skips: list[dict] | None = None,
    ) -> None:
        self._file_set = file_set
        self._row_counts = row_counts or {}
        self._seed = seed
        # Map schema_name → list of rule dicts (column_name, masking_type,
        # masking_config, optional consistency_group / linked_column_names).
        # The worker resolves persisted file_schemas → these rules so the
        # orchestrator stays free of DB access.
        self._masking_rules_by_schema = masking_rules_by_schema or {}
        self._masking_salt = masking_salt or "file-set-default-salt"
        # Skip report — every requested rule the orchestrator (or its
        # caller) refused to apply, with reason. Surfaced via
        # ``masking_skip_report()`` so the worker can put it in the job's
        # result_summary; otherwise "completed" jobs would silently mean
        # "some masking didn't happen" and operators would never know.
        self._masking_skips: list[dict] = list(initial_masking_skips or [])
        # Count of rules that actually fired against rows, so the job can
        # show "applied N, skipped M" rather than just the skip list.
        self._masking_applied_count: int = 0

    # ── Planning ───────────────────────────────────────────────────────

    def plan(self) -> list[str]:
        """Topo-sort schema names so parents come before children."""
        schema_names = [s.name for s in self._file_set.schemas]
        # Edge: source depends on target (FK direction).
        deps: dict[str, set[str]] = defaultdict(set)
        for fk in self._file_set.foreign_keys:
            if fk.source_file in schema_names and fk.target_file in schema_names:
                deps[fk.source_file].add(fk.target_file)

        in_degree = {name: len(deps[name]) for name in schema_names}
        queue = deque(n for n in schema_names if in_degree[n] == 0)
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for name in schema_names:
                if node in deps[name]:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        if len(order) != len(schema_names):
            raise ValueError(
                f"FileSet {self._file_set.name!r} has a cross-file FK cycle: "
                f"could only order {order} out of {schema_names}"
            )
        return order

    # ── Skip reporting ─────────────────────────────────────────────────

    def masking_skip_report(self) -> list[dict]:
        """Return every requested rule the run refused to apply.

        Each entry: ``{"schema": str, "column": str, "reason": str}``.
        The worker surfaces this in the job's ``result_summary`` so the
        UI can distinguish "completed and fully masked" from "completed
        with some rules skipped" — which is a compliance-relevant
        distinction we owe the operator.
        """
        return list(self._masking_skips)

    def masking_applied_count(self) -> int:
        """Number of rules that actually executed against rows."""
        return self._masking_applied_count

    # ── Generation ─────────────────────────────────────────────────────

    async def generate(self, output_dir: Path) -> list[Path]:
        """Generate every file in topo order. Returns the list of written paths."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        engine = FakerEngine(seed=self._seed)
        order = self.plan()
        schema_by_name = {s.name: s for s in self._file_set.schemas}

        # Track previously-generated rows so child schemas can pull FK pools.
        generated_rows: dict[str, list[dict]] = {}
        written: list[Path] = []

        # Cross-file FK lookup: source_file → list of {column: ..., references: {file, field}}
        fks_by_source: dict[str, list] = defaultdict(list)
        for fk in self._file_set.foreign_keys:
            fks_by_source[fk.source_file].append(fk)

        # Source-side FK columns per schema: any rule on these columns would
        # break the FK-integrity contract because the value was already
        # picked from the parent's pool. We mask the PARENT once, child
        # reads the masked value via the FK pool, and we must NOT mask the
        # FK column on the child again (otherwise hash → hash → orphan).
        fk_source_cols_by_schema: dict[str, set[str]] = {
            schema_name: {fk.source_field for fk in fks}
            for schema_name, fks in fks_by_source.items()
        }

        for schema_name in order:
            schema = schema_by_name[schema_name]
            rows, table_cfg = await self._generate_schema_rows(
                schema, engine, generated_rows, fks_by_source.get(schema_name, [])
            )

            # Apply masking rules wired through the Files tab. Without this
            # the rule was metadata-only: the engine generated fresh fake
            # data, and the user's masking choice never reached the writer.
            #
            # FK-column guard: child rows already contain values pulled
            # from the masked parent pool. Reapplying a rule on the FK
            # column would produce a value that no longer points at any
            # parent row, breaking the FK-integrity invariant the
            # orchestrator promises elsewhere. We strip those rules out
            # here and log the skip — masking an FK column needs to be
            # set up on the parent side instead.
            rules_for_schema, fk_skipped = self._filter_out_fk_column_rules(
                schema_name,
                self._masking_rules_by_schema.get(schema_name) or [],
                fk_source_cols_by_schema.get(schema_name) or set(),
            )
            self._masking_skips.extend(fk_skipped)
            if rules_for_schema:
                self._apply_masking_rules(schema_name, rows, rules_for_schema)

            generated_rows[schema_name] = rows

            writer = get_writer(FileFormat(schema.file_format))
            ext = writer.get_extension()
            output_name = schema.output_filename or f"{schema_name}.{ext}"
            output_path = output_dir / output_name

            writer.write(schema, rows, output_path)
            written.append(output_path)

            logger.info(
                "file_set_orchestrator_wrote_file",
                schema=schema_name,
                format=schema.file_format,
                rows=len(rows),
                path=str(output_path),
            )

        return written

    async def _generate_schema_rows(
        self,
        schema: FileSchemaDefinition,
        engine: FakerEngine,
        generated_rows: dict[str, list[dict]],
        fks: list,
    ) -> tuple[list[dict], dict]:
        """Generate rows for one schema, wiring cross-file FKs into the column dicts."""
        row_count = self._row_counts.get(schema.name, 100)

        # Translate FileFieldDefinition → FakerEngine column dict.
        columns: list[dict] = []
        fk_lookup = {fk.source_field: fk for fk in fks}

        for f in schema.fields:
            col_dict = {
                "column_name": f.name,
                "data_type": self._faker_data_type(f),
                "pii_type": f.pii_type or "none",
                "is_nullable": f.nullable,
                "is_primary_key": False,
                "is_foreign_key": False,
            }
            fk = fk_lookup.get(f.name)
            if fk is not None:
                col_dict["is_foreign_key"] = True
                col_dict["fk_references"] = {
                    "table": fk.target_file,
                    "column": fk.target_field,
                }
            columns.append(col_dict)

        config = SyntheticConfig(
            name=schema.name,
            tables=[{"table_name": schema.name, "columns": columns, "row_count": row_count}],
            row_count=row_count,
        )
        # Pass the already-generated rows as "tables" for FakerEngine's FK pool lookup.
        # FakerEngine reads pools from `generated[parent_table]` — we satisfy that
        # by handing it `generated` directly via the schema_metadata trick is unnecessary;
        # we instead seed `generated_rows` keys to match the table name and call generate
        # on a config that only contains the current schema's table. FK pool resolution
        # happens inside FakerEngine via `generated.get(parent_table, [])`.
        # Build a transient `generated` dict to seed FakerEngine's internal state.
        seeded_metadata = {"_seeded_generated": generated_rows}
        # FakerEngine doesn't read _seeded_generated; we instead inject parents as
        # config "tables" so engine has access via the cyclic-FK pool lookup. Simpler
        # to just call engine._generate_table directly with the parents in scope.
        rows = engine._generate_table(
            columns=columns,
            row_count=row_count,
            generated=generated_rows,
            has_cycle=False,
            column_profiles=None,
        )
        return rows, columns

    @staticmethod
    def _filter_out_fk_column_rules(
        schema_name: str, rules: list[dict], fk_source_cols: set[str]
    ) -> tuple[list[dict], list[dict]]:
        """Drop rules that target FK source columns; preserve everything else.

        Pure function (static) so the FK-skip behavior can be tested
        without spinning up a generation run. The orchestrator's existing
        FK-integrity contract — every child FK resolves to a parent PK —
        depends on this: the child column already holds a value picked
        (and possibly masked) on the parent side. Masking the child
        version again rewrites it independently, producing orphans even
        when both sides share the same deterministic strategy (hash →
        hash gives a different output).

        Returns ``(kept, skipped)``. ``skipped`` is a list of
        ``{schema, column, reason}`` dicts the caller appends to its
        run-wide skip report so the job's result_summary stays honest.
        """
        if not fk_source_cols:
            return rules, []
        kept: list[dict] = []
        skipped: list[dict] = []
        for r in rules:
            col = r.get("column_name")
            if col in fk_source_cols:
                reason = (
                    "fk_column_mask_would_break_integrity: masking an FK "
                    "column rewrites it independently of the parent PK; "
                    "mask the parent column instead"
                )
                skipped.append(
                    {"schema": schema_name, "column": col, "reason": reason}
                )
                logger.warning(
                    "file_set_skipping_fk_column_mask",
                    schema=schema_name,
                    column=col,
                    reason=reason,
                )
                continue
            kept.append(r)
        return kept, skipped

    def _apply_masking_rules(
        self, schema_name: str, rows: list[dict], rules: list[dict]
    ) -> None:
        """Mutate ``rows`` in place using each rule's strategy.

        Mirrors the DB masking task's dispatch so column-only (SHUFFLE),
        plain, and joint (consistency_group / linked_column_names) rules
        all execute through the right MaskingEngine path. The orchestrator
        intentionally does not touch the database — the worker is
        responsible for translating persisted rules into this dict shape.

        Each rule that the engine refuses to execute (unknown strategy,
        for example) is appended to ``self._masking_skips`` with a
        machine-parseable reason so the job's result_summary reflects
        which masking actually happened. The previous behavior was to
        warn-and-drop silently, which let the job report success while
        a column went unmasked.
        """
        if not rows or not rules:
            return

        from app.domain.masking.value_objects import MaskingStrategy
        from app.infrastructure.engine.masking_engine import MaskingEngine
        from app.infrastructure.messaging.masking_tasks import (
            partition_masking_rules,
        )

        engine = MaskingEngine(salt=self._masking_salt)
        column_only, plain, joint = partition_masking_rules(rules)

        def _apply_column_wise(rule_cfg: dict) -> None:
            col_name = rule_cfg["column_name"]
            try:
                strategy = MaskingStrategy(rule_cfg["masking_type"])
            except ValueError:
                reason = (
                    f"unknown_masking_strategy:{rule_cfg.get('masking_type')!r}"
                )
                self._masking_skips.append(
                    {"schema": schema_name, "column": col_name, "reason": reason}
                )
                logger.warning(
                    "file_set_unknown_masking_strategy",
                    schema=schema_name,
                    column=col_name,
                    strategy=rule_cfg.get("masking_type"),
                )
                return
            col_values = [row.get(col_name) for row in rows]
            masked_values = engine.mask_column(
                col_values, strategy, rule_cfg.get("masking_config")
            )
            for i, row in enumerate(rows):
                if col_name in row:
                    row[col_name] = masked_values[i]
            self._masking_applied_count += 1

        for r in column_only:
            _apply_column_wise(r)
        for r in plain:
            _apply_column_wise(r)

        if joint:
            # Pre-validate the joint rules — any with unknown strategies
            # get reported as skipped before mask_row runs, since
            # MaskingEngine.mask_value would otherwise quietly fall back
            # to ``_redact`` for an unrecognized strategy and the
            # operator wouldn't see that their choice was overridden.
            valid_joint: list[dict] = []
            for r in joint:
                try:
                    MaskingStrategy(r["masking_type"])
                except ValueError:
                    self._masking_skips.append(
                        {
                            "schema": schema_name,
                            "column": r.get("column_name"),
                            "reason": (
                                f"unknown_masking_strategy:"
                                f"{r.get('masking_type')!r}"
                            ),
                        }
                    )
                    logger.warning(
                        "file_set_unknown_masking_strategy",
                        schema=schema_name,
                        column=r.get("column_name"),
                        strategy=r.get("masking_type"),
                    )
                    continue
                valid_joint.append(r)

            if valid_joint:
                row_rules = [
                    {
                        "column_name": r["column_name"],
                        "masking_type": r["masking_type"],
                        "masking_config": r.get("masking_config", {}),
                        "consistency_group": r.get("consistency_group"),
                        "linked_column_names": r.get("linked_column_names") or [],
                    }
                    for r in valid_joint
                ]
                for i, row in enumerate(rows):
                    rows[i] = engine.mask_row(row, row_rules)
                self._masking_applied_count += len(valid_joint)

    def _faker_data_type(self, f) -> str:
        """Map a FileFieldDefinition data_type onto what FakerEngine expects."""
        mapping = {
            "alphanumeric": "varchar",
            "numeric": "integer",
            "decimal": "numeric",
            "binary": "integer",
            "packed_decimal": "numeric",
        }
        return mapping.get(f.data_type, "varchar")
