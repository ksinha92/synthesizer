"""Custom sensitivity-rule matcher (Phase 53).

Single source of truth for rule precedence: ``match_all_rules`` evaluates
every match strategy together in priority order. The discovery service
is the only call site that has raw samples + column metadata available at
the same time, so it's the only place precedence can be honored across
all rule types.

``match_column_name_rules`` is a fallback used by the detector when an
upstream ``match_all_rules`` call wasn't possible (e.g., older flows). It
evaluates only column-name strategies — ``value_regex`` rules are skipped
because the samples available to the detector are already masked, and
silently running them on masked text would break advertised behavior.

Rule dict shape (loaded from the ``sensitivity_rules`` table):
  {
    "id": str,
    "match_type": "column_name_regex" | "column_name_contains" | "value_regex",
    "pattern": str,
    "suggested_pii_type": str,            # PIIType.value
    "priority": int,                       # lower runs first
    "enabled": bool,
  }
"""

from __future__ import annotations

import re
from typing import Iterable

from app.domain.discovery.value_objects import PIIType


CUSTOM_RULE_CONFIDENCE = 0.9


def _safe_compile(pattern: str) -> re.Pattern | None:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return None


def _ordered_enabled(rules: list[dict]) -> list[dict]:
    return [
        r
        for r in sorted(rules, key=lambda r: (r.get("priority", 100), r.get("name", "")))
        if r.get("enabled", True)
    ]


def _resolve_pii(rule: dict) -> PIIType | None:
    try:
        return PIIType(rule.get("suggested_pii_type") or "other")
    except ValueError:
        return None


def _evaluate(rule: dict, column_name: str, samples_text: str) -> bool:
    """Return True if the given rule matches the column/sample inputs."""
    match_type = rule.get("match_type")
    pattern = rule.get("pattern") or ""
    if match_type == "column_name_contains":
        return pattern.lower() in (column_name or "").lower()
    if match_type == "column_name_regex":
        compiled = _safe_compile(pattern)
        return compiled is not None and bool(compiled.search(column_name or ""))
    if match_type == "value_regex":
        if not samples_text:
            return False
        compiled = _safe_compile(pattern)
        return compiled is not None and bool(compiled.search(samples_text))
    return False


def match_all_rules(
    column_name: str,
    raw_sample_values: Iterable | None,
    rules: list[dict],
) -> tuple[PIIType, float] | None:
    """Evaluate every match strategy together in priority order.

    Call this where RAW sample values are available — typically inside
    ``SchemaDiscoveryService`` before ``_mask_sample_values``. This is the
    only call site that can honor user-supplied priority across both
    column-name and value-regex rules in a single pass.

    Rules are sorted ascending by ``priority``; first match wins.
    """
    if not rules:
        return None

    samples_text = ""
    if raw_sample_values is not None:
        samples_text = " ".join(
            str(v) for v in raw_sample_values if v is not None
        )

    for rule in _ordered_enabled(rules):
        if _evaluate(rule, column_name, samples_text):
            pii = _resolve_pii(rule)
            if pii is not None:
                return pii, CUSTOM_RULE_CONFIDENCE
    return None


def match_column_name_rules(
    column_name: str,
    rules: list[dict],
) -> tuple[PIIType, float] | None:
    """Detector fallback. Evaluates column-name strategies only.

    Used by ``PIIDetectionService.detect`` when the column was not already
    classified upstream by ``match_all_rules``. ``value_regex`` rules are
    skipped here — samples at this point are masked, so running them would
    silently fail to match real PII.
    """
    if not rules:
        return None

    for rule in _ordered_enabled(rules):
        if rule.get("match_type") not in {"column_name_contains", "column_name_regex"}:
            continue
        if _evaluate(rule, column_name, ""):
            pii = _resolve_pii(rule)
            if pii is not None:
                return pii, CUSTOM_RULE_CONFIDENCE
    return None
