"""Guard rails for ``select_applicable_rules`` in masking_tasks.

Codex stop-time review on v0.10: file-schema masking rules (created via
the Files tab) share the ``masking_rules`` table with DB rules but carry
``match_pattern = {"kind": "file_field", ...}``. Before the fix the DB
masking dispatcher fell into the regex path, pulled ``pattern.get("pattern", "")``,
and ``re.search("", col)`` matched every column — so a single file-field
rule silently masked every column in every table in the database run.

These tests lock the fix in:

- file-field rules never enter DB-applicable rules
- empty regex patterns never match any column
- well-formed column_id and regex rules still resolve correctly
"""

from __future__ import annotations

from app.infrastructure.messaging.masking_tasks import select_applicable_rules


def test_file_field_match_pattern_excluded_from_db_run():
    """A file-schema rule must NOT be applied to any DB column even though
    its match_pattern is a dict (without a ``pattern`` key)."""
    rules = [
        {
            "match_pattern": {
                "kind": "file_field",
                "file_schema_id": "abc",
                "field_name": "ssn",
            },
            "masking_type": "redact",
        }
    ]
    out = select_applicable_rules(
        rules,
        schema_name="public",
        table_name="customers",
        column_names=["id", "ssn", "email"],
        column_lookup={},
    )
    assert out == []


def test_empty_pattern_does_not_match_every_column():
    """A dict match_pattern with no ``pattern`` key (or an empty string)
    must not regex-match everything — that's the failure mode that turned
    one stray rule into a database-wide mask."""
    rules = [{"match_pattern": {"pattern": ""}, "masking_type": "hash"}]
    out = select_applicable_rules(
        rules,
        schema_name="public",
        table_name="customers",
        column_names=["id", "email", "phone"],
        column_lookup={},
    )
    assert out == []


def test_column_id_rule_resolves_via_lookup():
    rules = [{"column_id": "col-uuid-1", "masking_type": "hash"}]
    lookup = {"col-uuid-1": ("public", "customers", "email")}
    out = select_applicable_rules(
        rules,
        schema_name="public",
        table_name="customers",
        column_names=["id", "email"],
        column_lookup=lookup,
    )
    assert len(out) == 1
    assert out[0]["column_name"] == "email"
    assert out[0]["masking_type"] == "hash"


def test_regex_match_pattern_still_works():
    """The pre-existing regex pattern path is unaffected — non-empty
    patterns still match columns by name."""
    rules = [{"match_pattern": {"pattern": "^email$"}, "masking_type": "redact"}]
    out = select_applicable_rules(
        rules,
        schema_name="public",
        table_name="customers",
        column_names=["id", "email", "email_verified"],
        column_lookup={},
    )
    assert [r["column_name"] for r in out] == ["email"]


def test_regex_string_pattern_still_works():
    """Bare-string match_pattern (legacy shape) is still honored."""
    rules = [{"match_pattern": "ssn", "masking_type": "redact"}]
    out = select_applicable_rules(
        rules,
        schema_name="public",
        table_name="customers",
        column_names=["customer_ssn", "name"],
        column_lookup={},
    )
    assert [r["column_name"] for r in out] == ["customer_ssn"]


def test_column_id_rule_with_unknown_id_is_skipped():
    """A column_id rule pointing at an id outside ``column_lookup`` (e.g.
    a file-schema synthetic uuid5) must not match anything on the DB."""
    rules = [{"column_id": "file-synth-uuid", "masking_type": "hash"}]
    out = select_applicable_rules(
        rules,
        schema_name="public",
        table_name="customers",
        column_names=["id", "ssn"],
        column_lookup={"real-col-uuid": ("public", "other", "ssn")},
    )
    assert out == []
