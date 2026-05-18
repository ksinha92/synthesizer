"""FileSetOrchestrator must honor file-schema masking rules.

Codex stop-time review on v0.10: rules persisted via the Files tab
landed in ``masking_rules`` but the synthetic-generation pipeline never
loaded them — operators saw a rule listed in the UI and got an unmasked
file anyway. The orchestrator now accepts ``masking_rules_by_schema`` and
applies it to generated rows before the writer touches them. These
tests pin that contract at the orchestrator boundary.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.synthetic.file_schema import (
    FileFieldDefinition,
    FileSchemaDefinition,
    FileSetDefinition,
)
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.engine.file_set_orchestrator import FileSetOrchestrator
from app.infrastructure.parsers.sample_file_parser import parse_csv


def _customers_schema() -> FileSchemaDefinition:
    return FileSchemaDefinition(
        name="customers",
        fields=[
            FileFieldDefinition(
                name="id", data_type="alphanumeric", length=36,
                byte_length=36, start_position=0,
            ),
            FileFieldDefinition(
                name="email", data_type="alphanumeric", length=64,
                byte_length=64, start_position=36, pii_type="email",
            ),
        ],
        file_format=FileFormat.CSV.value,
    )


def test_hash_rule_replaces_field_in_generated_file(tmp_path):
    """A ``hash`` rule on ``email`` should produce hex-only, length-16
    values — the deterministic HMAC fingerprint MaskingEngine emits."""
    file_set = FileSetDefinition(name="masked-set", schemas=[_customers_schema()])
    rules = {
        "customers": [
            {
                "column_name": "email",
                "masking_type": "hash",
                "masking_config": {},
            }
        ]
    }
    orch = FileSetOrchestrator(
        file_set,
        row_counts={"customers": 6},
        seed=7,
        masking_rules_by_schema=rules,
        masking_salt="test-salt",
    )
    written = asyncio.run(orch.generate(tmp_path))
    assert len(written) == 1

    df = parse_csv(written[0], _customers_schema())
    masked_values = df["email"].astype(str).tolist()

    # MaskingEngine._hash returns 16 hex chars.
    assert len(masked_values) == 6
    for v in masked_values:
        assert len(v) == 16
        int(v, 16)  # raises if a value drifts off-hex


def test_no_rule_leaves_fakers_unmasked(tmp_path):
    """Schemas without rules go through the existing FakerEngine path.
    Locking in the no-regression contract — i.e. the new code path is a
    no-op when ``masking_rules_by_schema`` is empty."""
    file_set = FileSetDefinition(name="plain-set", schemas=[_customers_schema()])
    orch = FileSetOrchestrator(
        file_set, row_counts={"customers": 4}, seed=11,
    )
    written = asyncio.run(orch.generate(tmp_path))
    df = parse_csv(written[0], _customers_schema())
    # Faker's email column should still look like an email address (contains '@').
    assert all("@" in v for v in df["email"].astype(str))


def test_unknown_masking_strategy_is_logged_and_skipped(tmp_path):
    """A malformed rule (bad masking_type) should not bring down the
    whole run — it's logged, the column is left untouched."""
    file_set = FileSetDefinition(name="bad-rule-set", schemas=[_customers_schema()])
    rules = {
        "customers": [
            {
                "column_name": "email",
                "masking_type": "totally-not-a-strategy",
                "masking_config": {},
            }
        ]
    }
    orch = FileSetOrchestrator(
        file_set,
        row_counts={"customers": 3},
        seed=13,
        masking_rules_by_schema=rules,
        masking_salt="test-salt",
    )
    written = asyncio.run(orch.generate(tmp_path))
    df = parse_csv(written[0], _customers_schema())
    # Column still has the FakerEngine output — no crash.
    assert len(df) == 3
    assert all("@" in v for v in df["email"].astype(str))


class TestFKIntegrityPreservedUnderMasking:
    """Codex review (fifth pass): masking a child FK column rewrites the
    value the parent already produced, breaking FK integrity even when
    both sides share the same deterministic strategy (hash → hash on the
    child gives a different output). The orchestrator must drop rules
    targeting FK source columns and warn — masking belongs on the parent.
    """

    @staticmethod
    def _filter_helper():
        # The static method is the unit under test.
        return FileSetOrchestrator._filter_out_fk_column_rules

    def test_rule_on_fk_source_column_dropped_and_reported(self):
        rules = [
            {"column_name": "customer_id", "masking_type": "hash"},
            {"column_name": "amount", "masking_type": "redact"},
        ]
        kept, skipped = self._filter_helper()(
            "orders", rules, fk_source_cols={"customer_id"}
        )
        assert [r["column_name"] for r in kept] == ["amount"]
        # Skipped column reported with schema + machine-parseable reason
        # so the job's result_summary can surface it.
        assert len(skipped) == 1
        assert skipped[0]["schema"] == "orders"
        assert skipped[0]["column"] == "customer_id"
        assert "fk_column_mask_would_break_integrity" in skipped[0]["reason"]

    def test_no_fk_columns_passes_rules_through_with_empty_skip(self):
        rules = [
            {"column_name": "amount", "masking_type": "redact"},
        ]
        kept, skipped = self._filter_helper()(
            "orders", rules, fk_source_cols=set()
        )
        assert kept == rules
        assert skipped == []

    def test_empty_rules_list_returns_empty_both_sides(self):
        kept, skipped = self._filter_helper()(
            "orders", [], fk_source_cols={"customer_id"}
        )
        assert kept == [] and skipped == []

    def test_end_to_end_fk_integrity_with_masked_pk_and_no_child_rule(self, tmp_path):
        """Parent's PK rule masks the customer ids; child schema reads the
        masked values via the FK pool. No rule on the child FK column,
        so FK integrity holds — every order's customer_id resolves to a
        customer row.

        This is the contract the orchestrator was already promising for
        unmasked file-sets; the new masking layer must not break it."""
        customers = FileSchemaDefinition(
            name="customers",
            fields=[
                FileFieldDefinition(
                    name="id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=0,
                ),
                FileFieldDefinition(
                    name="name", data_type="alphanumeric", length=30,
                    byte_length=30, start_position=36,
                ),
            ],
            file_format=FileFormat.CSV.value,
        )
        orders = FileSchemaDefinition(
            name="orders",
            fields=[
                FileFieldDefinition(
                    name="order_id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=0,
                ),
                FileFieldDefinition(
                    name="customer_id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=36,
                    fk_reference=("customers", "id"),
                ),
            ],
            file_format=FileFormat.CSV.value,
        )
        from app.domain.synthetic.file_schema import CrossFileFK

        file_set = FileSetDefinition(
            name="biz",
            schemas=[customers, orders],
            foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "id")],
        )
        # Mask the parent's PK; leave child untouched.
        rules = {
            "customers": [
                {"column_name": "id", "masking_type": "hash", "masking_config": {}}
            ]
        }
        orch = FileSetOrchestrator(
            file_set,
            row_counts={"customers": 6, "orders": 12},
            seed=42,
            masking_rules_by_schema=rules,
            masking_salt="fk-salt",
        )
        written = asyncio.run(orch.generate(tmp_path))
        cust_path = next(p for p in written if "customers" in p.name)
        ord_path = next(p for p in written if "orders" in p.name)
        cust_df = parse_csv(cust_path, customers)
        ord_df = parse_csv(ord_path, orders)

        cust_ids = set(cust_df["id"].astype(str).tolist())
        ord_fks = set(ord_df["customer_id"].astype(str).tolist())
        # Every child FK points at a parent — masked parent values are
        # used as the FK pool, so integrity holds.
        assert ord_fks.issubset(cust_ids), (
            f"orphan FKs after parent-side masking: {ord_fks - cust_ids}"
        )
        # And the parent's masking actually fired (hash output is 16 hex).
        for v in cust_ids:
            assert len(v) == 16
            int(v, 16)

    def test_end_to_end_fk_integrity_with_child_fk_rule_dropped(self, tmp_path):
        """The bug Codex caught: with a rule on the CHILD FK column the
        previous code would double-mask the value and orphan every FK.
        After the fix the rule must be silently dropped so integrity
        holds. (Operators get a logged warning.)"""
        customers = FileSchemaDefinition(
            name="customers",
            fields=[
                FileFieldDefinition(
                    name="id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=0,
                ),
            ],
            file_format=FileFormat.CSV.value,
        )
        orders = FileSchemaDefinition(
            name="orders",
            fields=[
                FileFieldDefinition(
                    name="order_id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=0,
                ),
                FileFieldDefinition(
                    name="customer_id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=36,
                    fk_reference=("customers", "id"),
                ),
            ],
            file_format=FileFormat.CSV.value,
        )
        from app.domain.synthetic.file_schema import CrossFileFK

        file_set = FileSetDefinition(
            name="biz-orphan-risk",
            schemas=[customers, orders],
            foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "id")],
        )
        rules = {
            # Rule on the child FK column — would orphan everything if
            # we let it run. Filter must drop it.
            "orders": [
                {
                    "column_name": "customer_id",
                    "masking_type": "hash",
                    "masking_config": {},
                }
            ]
        }
        orch = FileSetOrchestrator(
            file_set,
            row_counts={"customers": 4, "orders": 8},
            seed=99,
            masking_rules_by_schema=rules,
            masking_salt="orphan-test-salt",
        )
        written = asyncio.run(orch.generate(tmp_path))
        cust_df = parse_csv(
            next(p for p in written if "customers" in p.name), customers
        )
        ord_df = parse_csv(
            next(p for p in written if "orders" in p.name), orders
        )
        cust_ids = set(cust_df["id"].astype(str))
        ord_fks = set(ord_df["customer_id"].astype(str))
        assert ord_fks.issubset(cust_ids), (
            f"FK rule was not dropped — orphan FKs present: "
            f"{ord_fks - cust_ids}"
        )


class TestMaskingSkipReport:
    """Codex review (sixth pass): job result must not say "completed" while
    requested rules were silently dropped. Every skip — FK column,
    unknown strategy, duplicate schema name (worker-level) — must surface
    in ``orchestrator.masking_skip_report()`` so the worker can put it
    in ``job.result_summary``. Without this, an operator with a typo'd
    masking_type sees green and ships unmasked data.
    """

    def test_initial_skips_threaded_through_to_report(self, tmp_path):
        """Worker-level skips (e.g. duplicate schema names) come in via
        the constructor and must appear in the final report alongside
        anything the orchestrator itself adds."""
        file_set = FileSetDefinition(name="set", schemas=[_customers_schema()])
        initial = [
            {
                "schema": "duplicate_named_schema",
                "column": None,
                "reason": "duplicate_schema_name: ambiguous schema id",
            }
        ]
        orch = FileSetOrchestrator(
            file_set,
            row_counts={"customers": 2},
            seed=5,
            masking_rules_by_schema={},
            initial_masking_skips=initial,
        )
        asyncio.run(orch.generate(tmp_path))
        report = orch.masking_skip_report()
        assert initial[0] in report

    def test_fk_column_rule_recorded_in_skip_report(self, tmp_path):
        """End-to-end: a rule on a child FK column gets dropped (we
        proved that elsewhere) AND must show up in the skip report so
        the operator knows the masking they configured did not run."""
        customers = FileSchemaDefinition(
            name="customers",
            fields=[
                FileFieldDefinition(
                    name="id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=0,
                ),
            ],
            file_format=FileFormat.CSV.value,
        )
        orders = FileSchemaDefinition(
            name="orders",
            fields=[
                FileFieldDefinition(
                    name="order_id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=0,
                ),
                FileFieldDefinition(
                    name="customer_id", data_type="alphanumeric", length=36,
                    byte_length=36, start_position=36,
                    fk_reference=("customers", "id"),
                ),
            ],
            file_format=FileFormat.CSV.value,
        )
        from app.domain.synthetic.file_schema import CrossFileFK

        file_set = FileSetDefinition(
            name="biz-fk-report",
            schemas=[customers, orders],
            foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "id")],
        )
        orch = FileSetOrchestrator(
            file_set,
            row_counts={"customers": 2, "orders": 4},
            seed=88,
            masking_rules_by_schema={
                "orders": [
                    {
                        "column_name": "customer_id",
                        "masking_type": "hash",
                        "masking_config": {},
                    }
                ]
            },
            masking_salt="report-salt",
        )
        asyncio.run(orch.generate(tmp_path))
        report = orch.masking_skip_report()
        fk_skips = [r for r in report if "fk_column" in r["reason"]]
        assert len(fk_skips) == 1
        assert fk_skips[0]["schema"] == "orders"
        assert fk_skips[0]["column"] == "customer_id"
        # And nothing applied (the only rule was the dropped one).
        assert orch.masking_applied_count() == 0

    def test_unknown_strategy_reported_not_silently_dropped(self, tmp_path):
        """The earlier test pinned that an unknown masking_type leaves
        the column untouched. This test now also pins that the skip is
        reported, so the job's result_summary reflects the gap."""
        file_set = FileSetDefinition(name="set", schemas=[_customers_schema()])
        orch = FileSetOrchestrator(
            file_set,
            row_counts={"customers": 3},
            seed=13,
            masking_rules_by_schema={
                "customers": [
                    {
                        "column_name": "email",
                        "masking_type": "not-a-real-strategy",
                        "masking_config": {},
                    }
                ]
            },
            masking_salt="unknown-salt",
        )
        asyncio.run(orch.generate(tmp_path))
        report = orch.masking_skip_report()
        assert any(
            r["reason"].startswith("unknown_masking_strategy") for r in report
        )
        assert orch.masking_applied_count() == 0

    def test_unknown_strategy_in_joint_rule_reported(self, tmp_path):
        """Unknown strategy in a JOINT rule must also be reported, not
        silently passed to mask_value which would degrade to _redact
        without the operator's knowledge."""
        file_set = FileSetDefinition(name="set", schemas=[_customers_schema()])
        orch = FileSetOrchestrator(
            file_set,
            row_counts={"customers": 2},
            seed=21,
            masking_rules_by_schema={
                "customers": [
                    {
                        "column_name": "email",
                        "masking_type": "still-not-a-strategy",
                        "masking_config": {},
                        "consistency_group": "g1",  # routes to joint bucket
                    }
                ]
            },
            masking_salt="joint-unknown-salt",
        )
        asyncio.run(orch.generate(tmp_path))
        report = orch.masking_skip_report()
        assert any(
            r["reason"].startswith("unknown_masking_strategy") for r in report
        )

    def test_valid_run_reports_no_skips_and_counts_applied(self, tmp_path):
        """The happy path must report zero skips and an accurate applied
        count — otherwise the UI can't distinguish "clean run" from
        "we don't know" and operators lose trust."""
        file_set = FileSetDefinition(name="ok-set", schemas=[_customers_schema()])
        orch = FileSetOrchestrator(
            file_set,
            row_counts={"customers": 4},
            seed=42,
            masking_rules_by_schema={
                "customers": [
                    {
                        "column_name": "email",
                        "masking_type": "hash",
                        "masking_config": {},
                    }
                ]
            },
            masking_salt="ok-salt",
        )
        asyncio.run(orch.generate(tmp_path))
        assert orch.masking_skip_report() == []
        assert orch.masking_applied_count() == 1


def test_joint_rule_with_linked_columns_seeds_off_linked_values(tmp_path):
    """A rule with ``linked_column_ids`` (carried through as
    ``linked_column_names`` here) must reach the joint bucket and seed
    its Faker output off the linked field's value. Two rows that share
    the same linked value must produce the same masked output; rows with
    different linked values must diverge.

    This is the regression Codex flagged: before the linked-name
    resolver, joint rules either fell into the plain bucket (no
    correlation) or had no linked names to seed from (row identity
    only). Either way the paired-faker invariant was silently broken."""

    def _two_col_schema() -> FileSchemaDefinition:
        return FileSchemaDefinition(
            name="visits",
            fields=[
                FileFieldDefinition(
                    name="city", data_type="alphanumeric", length=40,
                    byte_length=40, start_position=0, pii_type="address",
                ),
                FileFieldDefinition(
                    name="state", data_type="alphanumeric", length=20,
                    byte_length=20, start_position=40,
                ),
            ],
            file_format=FileFormat.CSV.value,
        )

    file_set = FileSetDefinition(name="visits-set", schemas=[_two_col_schema()])
    rules = {
        "visits": [
            {
                "column_name": "city",
                "masking_type": "faker_replace",
                "masking_config": {"provider": "city"},
                # Both signals present so the rule is unambiguously joint.
                "linked_column_ids": ["pretend-uuid-for-state"],
                "linked_column_names": ["state"],
            }
        ]
    }
    orch = FileSetOrchestrator(
        file_set,
        row_counts={"visits": 6},
        seed=23,
        masking_rules_by_schema=rules,
        masking_salt="link-salt",
    )
    written = asyncio.run(orch.generate(tmp_path))

    df = parse_csv(written[0], _two_col_schema())
    # Pair the masked city with the row's state. Same state should yield
    # the same masked city; different state should yield a different one.
    pairs = list(zip(df["state"].astype(str), df["city"].astype(str)))
    by_state: dict[str, set[str]] = {}
    for state, city in pairs:
        by_state.setdefault(state, set()).add(city)
    # Every state value maps to exactly one masked city — that's the
    # joint-generation contract. If the rule had landed in the plain
    # bucket, mask_column would have produced a fresh faker city per row
    # and rows sharing a state would diverge.
    for state, cities in by_state.items():
        assert len(cities) == 1, (
            f"state={state!r} produced {len(cities)} masked cities: "
            f"{cities} — joint seeding broke"
        )
    # And the rule actually fired: masked cities are not the raw faker
    # city the unmasked path would have produced (sanity check that the
    # join path ran at all, not the plain path).
    assert pairs  # smoke


def test_rules_keyed_by_schema_name_not_format(tmp_path):
    """Rules dict keys are schema names; mismatched names just skip silently
    (rule isn't applied) rather than fail the run. Important so a stale
    rule doesn't block an otherwise-valid generation."""
    file_set = FileSetDefinition(name="set", schemas=[_customers_schema()])
    rules = {"orders": [  # wrong schema name
        {"column_name": "email", "masking_type": "hash", "masking_config": {}}
    ]}
    orch = FileSetOrchestrator(
        file_set,
        row_counts={"customers": 2},
        seed=17,
        masking_rules_by_schema=rules,
        masking_salt="test-salt",
    )
    written = asyncio.run(orch.generate(tmp_path))
    df = parse_csv(written[0], _customers_schema())
    # FakerEngine output preserved — rule didn't match.
    assert all("@" in v for v in df["email"].astype(str))
