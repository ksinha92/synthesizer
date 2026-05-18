"""Linked-column resolution for file-schema joint masking rules.

Codex stop-time review (third pass): the first fix-pass wired file-field
rules into the orchestrator but stubbed ``linked_column_names`` to an
empty list, which meant a rule with non-empty ``linked_column_ids``
either (a) never reached the joint bucket in
``partition_masking_rules`` (because ``linked_column_ids`` was also
unset on the orchestrator dict) or (b) reached the joint bucket via
``consistency_group`` but then had no linked names to seed off of,
losing paired-faker correlation in the generated file.

Codex stop-time review (fourth pass) caught that the orchestrator-level
test bypassed the worker by hand-crafting the rule dict — so the
worker's per-rule transformation went untested. This file now contains:

1. Resolver tests (pure ``resolve_linked_field_names_in_schema``) that
   pin the within-schema / cross-schema / unknown-id behavior.
2. Worker transformation tests (pure ``build_file_rule_payload``) that
   exercise the exact code path ``_load_file_masking_rules`` uses to
   convert a persisted MaskingRuleModel into the orchestrator dict —
   including the ``masking_type`` string handling (was ``.value`` on a
   plain str column), the joint routing fields, and preset overrides.
"""

from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace

from app.domain.synthetic.file_schema import file_field_column_id
from app.infrastructure.messaging.synthetic_tasks import (
    build_file_rule_payload,
    determine_file_set_job_status,
    index_persisted_schemas,
    resolve_linked_field_names_in_schema,
)


def _make_lookup(*pairs: tuple[str, str]) -> dict[str, tuple[str, str]]:
    """Helper: turn (schema_id, field_name) pairs into a forward+reverse map."""
    out: dict[str, tuple[str, str]] = {}
    for sid, fname in pairs:
        out[str(file_field_column_id(sid, fname))] = (sid, fname)
    return out


def test_resolves_linked_ids_within_same_schema():
    sid = "11111111-1111-1111-1111-111111111111"
    lookup = _make_lookup((sid, "city"), (sid, "state"), (sid, "country"))
    # Rule on ``city`` declares ``state`` as its linked column.
    state_id = str(file_field_column_id(sid, "state"))
    names = resolve_linked_field_names_in_schema([state_id], sid, lookup)
    assert names == ["state"]


def test_drops_links_pointing_at_another_schema():
    sid_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    sid_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    lookup = _make_lookup((sid_a, "city"), (sid_b, "state"))
    # A rule on schema A links to a field that actually lives in schema B.
    state_in_b = str(file_field_column_id(sid_b, "state"))
    names = resolve_linked_field_names_in_schema([state_in_b], sid_a, lookup)
    # mask_row only sees one schema's row, so cross-schema links must be
    # dropped — not raised — so the rule degrades to "use row identity".
    assert names == []


def test_drops_unknown_ids_silently():
    sid = "11111111-1111-1111-1111-111111111111"
    lookup = _make_lookup((sid, "city"))
    names = resolve_linked_field_names_in_schema(
        ["00000000-0000-0000-0000-000000000000"], sid, lookup
    )
    assert names == []


def test_empty_input_returns_empty():
    assert resolve_linked_field_names_in_schema([], "any-sid", {}) == []


def _mock_rule(
    masking_type: str = "hash",
    masking_config: dict | None = None,
    linked_column_ids: list | None = None,
    consistency_group: str | None = None,
) -> SimpleNamespace:
    """Build a duck-typed stand-in for a MaskingRuleModel row.

    Matches the ORM attribute shape: ``masking_type`` is a plain string
    (NOT a MaskingStrategy enum — that's the domain entity), and
    ``linked_column_ids`` is a list of ``uuid.UUID`` objects, never
    strings.
    """
    return SimpleNamespace(
        masking_type=masking_type,
        masking_config=masking_config,
        linked_column_ids=linked_column_ids,
        consistency_group=consistency_group,
    )


def _mock_preset(
    generator_type: str = "fake_email",
    config: dict | None = None,
    name: str = "Email Preset",
    consistency: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        generator_type=generator_type,
        config=config,
        name=name,
        consistency=consistency,
    )


class TestBuildFileRulePayload:
    """Pin the worker's per-rule transformation contract directly.

    The orchestrator-level test in test_file_set_orchestrator_masking.py
    proves that *given* a correctly-shaped rule dict, joint masking
    works. These tests prove the worker actually emits that dict shape
    — without bypassing the worker by hand-crafting the input."""

    SCHEMA_ID = "11111111-1111-1111-1111-111111111111"

    def test_emits_string_masking_type_for_orm_row(self):
        """Codex caught: ``r.masking_type.value`` on a String column
        column would AttributeError at runtime. ORM rows give plain
        strings; the helper must not call ``.value``."""
        rule = _mock_rule(masking_type="hash")
        out = build_file_rule_payload("email", rule, None, self.SCHEMA_ID, {})
        # No exception + masking_type passed through unchanged.
        assert out["masking_type"] == "hash"
        assert out["column_name"] == "email"

    def test_joint_rule_emits_both_linked_ids_and_resolved_names(self):
        """The bug Codex's third pass caught: a rule with non-empty
        ``linked_column_ids`` must have BOTH fields set on the output
        dict — linked_column_ids so partition_masking_rules routes
        joint, linked_column_names so mask_row can seed off the linked
        value. Dropping either silently demoted the rule to the plain
        bucket and broke paired-faker correlation."""
        state_uuid = file_field_column_id(self.SCHEMA_ID, "state")
        lookup = {str(state_uuid): (self.SCHEMA_ID, "state")}
        rule = _mock_rule(
            masking_type="faker_replace",
            masking_config={"provider": "city"},
            linked_column_ids=[state_uuid],
        )
        out = build_file_rule_payload(
            "city", rule, None, self.SCHEMA_ID, lookup
        )
        assert out["linked_column_ids"] == [str(state_uuid)]
        assert out["linked_column_names"] == ["state"]

    def test_cross_schema_linked_ids_dropped_from_names_kept_in_ids(self):
        """A link to a field in a DIFFERENT schema must drop from
        ``linked_column_names`` (mask_row only sees one schema's row).
        ``linked_column_ids`` is still passed through so the rule remains
        in the joint bucket — it just degrades to using row identity for
        the seed rather than crashing."""
        other_schema = "22222222-2222-2222-2222-222222222222"
        foreign_uuid = file_field_column_id(other_schema, "state")
        lookup = {str(foreign_uuid): (other_schema, "state")}
        rule = _mock_rule(linked_column_ids=[foreign_uuid])
        out = build_file_rule_payload(
            "city", rule, None, self.SCHEMA_ID, lookup
        )
        assert out["linked_column_ids"] == [str(foreign_uuid)]
        # Cross-schema link silently dropped — name list is empty.
        assert out["linked_column_names"] == []

    def test_preset_overrides_masking_type_and_merges_config(self):
        """Preset's generator_type wins; preset.config is the base,
        rule masking_config layers on top."""
        rule = _mock_rule(
            masking_type="hash",
            masking_config={"row_override": "yes"},
        )
        preset = _mock_preset(
            generator_type="fake_email",
            config={"locale": "en_US", "row_override": "preset_default"},
        )
        out = build_file_rule_payload(
            "email", rule, preset, self.SCHEMA_ID, {}
        )
        assert out["masking_type"] == "fake_email"
        # Rule config wins on key collision.
        assert out["masking_config"]["row_override"] == "yes"
        assert out["masking_config"]["locale"] == "en_US"

    def test_preset_consistency_promotes_to_consistency_group(self):
        """When preset.consistency is set, preset.name becomes the
        ``consistency_group`` so every rule using that preset emits the
        same masked output for a given input value."""
        rule = _mock_rule(consistency_group=None)
        preset = _mock_preset(name="Customer ID", consistency=True)
        out = build_file_rule_payload(
            "customer_id", rule, preset, self.SCHEMA_ID, {}
        )
        assert out["consistency_group"] == "Customer ID"

    def test_rule_level_consistency_group_used_when_no_preset(self):
        rule = _mock_rule(consistency_group="manually-set-group")
        out = build_file_rule_payload(
            "x", rule, None, self.SCHEMA_ID, {}
        )
        assert out["consistency_group"] == "manually-set-group"

    def test_empty_linked_ids_produces_empty_lists(self):
        """A rule without any linked columns must still pass through
        cleanly — both fields present as empty lists so the
        orchestrator's downstream lookups don't KeyError."""
        rule = _mock_rule(linked_column_ids=None)
        out = build_file_rule_payload("x", rule, None, self.SCHEMA_ID, {})
        assert out["linked_column_ids"] == []
        assert out["linked_column_names"] == []

    def test_payload_shape_matches_partition_masking_rules_contract(self):
        """The output dict must carry the exact keys
        ``partition_masking_rules`` reads — if any are missing, joint
        routing or column-only routing silently fails. Pin the schema."""
        rule = _mock_rule(linked_column_ids=[_uuid.uuid4()])
        out = build_file_rule_payload("x", rule, None, self.SCHEMA_ID, {})
        # These are the exact keys the engine + dispatcher inspect.
        for required_key in (
            "column_name",
            "masking_type",
            "masking_config",
            "consistency_group",
            "linked_column_ids",
            "linked_column_names",
        ):
            assert required_key in out, f"missing key: {required_key}"


class TestIndexPersistedSchemas:
    """Pin the duplicate-name handling Codex's fifth pass surfaced.

    ``file_schemas.name`` is not unique within a project, and the create
    endpoints allow duplicates. Without explicit ids the worker can't
    pick the right schema row for a given name, so it must refuse to
    apply rules for ambiguous names rather than silently bind to an
    arbitrary one (which produced nondeterministic masking before)."""

    A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    C = "cccccccc-cccc-cccc-cccc-cccccccccccc"

    def test_unique_names_pass_through(self):
        rows = [
            (_uuid.UUID(self.A), "customers", [{"name": "id"}, {"name": "email"}]),
            (_uuid.UUID(self.B), "orders", [{"name": "order_id"}]),
        ]
        ids, col_map, duplicates = index_persisted_schemas(rows)
        assert ids == {"customers": self.A, "orders": self.B}
        assert duplicates == set()
        # Reverse map populated for every (schema, field).
        cust_email = str(file_field_column_id(self.A, "email"))
        assert col_map[cust_email] == (self.A, "email")
        order_id = str(file_field_column_id(self.B, "order_id"))
        assert col_map[order_id] == (self.B, "order_id")

    def test_duplicate_names_dropped_from_index_and_reverse_map(self):
        """Two persisted schemas named ``customers`` — refuse to bind the
        name. Rules referencing either id will simply not be applied
        (the loader's WHERE clause filters by ids from this dict, so
        dropping the name implicitly drops its rules too)."""
        rows = [
            (_uuid.UUID(self.A), "customers", [{"name": "id"}]),
            (_uuid.UUID(self.B), "customers", [{"name": "id"}, {"name": "email"}]),
            (_uuid.UUID(self.C), "orders", [{"name": "order_id"}]),
        ]
        ids, col_map, duplicates = index_persisted_schemas(rows)
        # ``customers`` dropped entirely; only the unique ``orders`` remains.
        assert ids == {"orders": self.C}
        assert duplicates == {"customers"}
        # Neither customers id has any entry in the reverse map either —
        # so linked_column_ids on a customers rule resolve to nothing.
        cust_id_a = str(file_field_column_id(self.A, "id"))
        cust_id_b = str(file_field_column_id(self.B, "id"))
        assert cust_id_a not in col_map
        assert cust_id_b not in col_map
        # Orders still mapped.
        assert str(file_field_column_id(self.C, "order_id")) in col_map

    def test_empty_input_returns_empty(self):
        ids, col_map, duplicates = index_persisted_schemas([])
        assert ids == {} and col_map == {} and duplicates == set()

    def test_skips_fields_without_name(self):
        """A malformed row (field dict missing ``name``) should not crash
        the indexer — the field is simply not added to the reverse map."""
        rows = [
            (_uuid.UUID(self.A), "customers",
             [{"name": "id"}, {"no_name": True}, None, "junk"]),
        ]
        ids, col_map, _ = index_persisted_schemas(rows)
        assert ids == {"customers": self.A}
        assert len(col_map) == 1
        assert str(file_field_column_id(self.A, "id")) in col_map


class TestDetermineFileSetJobStatus:
    """Codex review (seventh pass): file-set jobs that silently dropped
    masking rules used to land as ``status="completed"`` — a plain
    green pill — even though some operator-requested operations were
    refused. The new ``completed_with_warnings`` status (+ a one-line
    ``error_message``) makes the partial outcome visible to anyone
    reading the jobs list or the SSE stream.
    """

    def test_clean_run_stays_completed(self):
        status, msg = determine_file_set_job_status([])
        assert status == "completed"
        assert msg is None

    def test_any_skip_demotes_status(self):
        status, msg = determine_file_set_job_status(
            [{"schema": "x", "column": "y", "reason": "z"}]
        )
        assert status == "completed_with_warnings"
        assert msg is not None
        # error_message has to surface the count so UI clients that only
        # know about ``completed`` / ``failed`` still tell the operator
        # something is up.
        assert "1 masking rule" in msg
        assert "result_summary" in msg

    def test_multi_skip_message_uses_correct_count(self):
        skips = [
            {"schema": "a", "column": "c1", "reason": "fk_column_mask"},
            {"schema": "b", "column": None, "reason": "duplicate_schema_name"},
            {"schema": "c", "column": "c3", "reason": "unknown_masking_strategy:'x'"},
        ]
        status, msg = determine_file_set_job_status(skips)
        assert status == "completed_with_warnings"
        assert "3 masking rule" in msg

    def test_status_string_matches_enum(self):
        """The new status string has to match the JobStatus enum value
        verbatim — drift here would break ``JobRepository._to_entity``'s
        ``JobStatus(m.status)`` reconstruction the moment any caller
        loaded a real warning-completed row."""
        from app.domain.shared.job import JobStatus

        status, _ = determine_file_set_job_status([{"reason": "x"}])
        assert status == JobStatus.COMPLETED_WITH_WARNINGS.value
        # Constructor round-trip — the moment this errors, repo reads
        # would fail for warning-completed rows.
        assert JobStatus(status) is JobStatus.COMPLETED_WITH_WARNINGS


def test_preserves_order_for_deterministic_seeding():
    """The MaskingEngine seeds the row from ``sorted(linked_column_names)``
    inside ``mask_row``, so this resolver doesn't need to sort. But the
    callers MUST get the names back in input order so they can rebuild
    the row-seed deterministically when joining with row values. The
    test pins ordering so a future refactor that sorts here would fail
    loudly rather than introduce a subtle drift."""
    sid = "11111111-1111-1111-1111-111111111111"
    lookup = _make_lookup((sid, "a"), (sid, "b"), (sid, "c"))
    a = str(file_field_column_id(sid, "a"))
    b = str(file_field_column_id(sid, "b"))
    c = str(file_field_column_id(sid, "c"))
    # Reverse order in; reverse order out.
    out = resolve_linked_field_names_in_schema([c, b, a], sid, lookup)
    assert out == ["c", "b", "a"]
