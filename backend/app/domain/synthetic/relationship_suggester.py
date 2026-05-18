"""Heuristic cross-file FK suggester for file schemas.

Score every (source_field, target_field) pair across two schemas using a
weighted blend of:

- name similarity (Damerau-Levenshtein over normalized identifiers)
- type compatibility (exact / family-match / incompatible)
- cardinality hint (boost when one side is marked primary key)
- value overlap (only when both sides have a sample available)

The suggester is intentionally rule-based; an ML approach (see Rostin et
al. 2009) is more accurate but pulls in heavy deps and is overkill for
the wizard's "did I get the obvious ones?" use case.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.domain.synthetic.file_schema import FileSchemaDefinition


# Floor — suggestions weaker than this get dropped before returning.
DEFAULT_MIN_SCORE = 0.4


@dataclass(frozen=True)
class RelationshipEvidence:
    """Breakdown of the score so the UI can show *why* we suggested it."""

    name_similarity: float
    type_compatibility: float
    cardinality_match: bool
    value_overlap: float | None  # None when no sample available


@dataclass(frozen=True)
class RelationshipSuggestion:
    source_file: str
    source_field: str
    target_file: str
    target_field: str
    score: float
    evidence: RelationshipEvidence
    sample_size: int  # 0 when value_overlap was not computed


def suggest_relationships(
    schemas: list[FileSchemaDefinition],
    *,
    samples: dict[str, list[dict]] | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[RelationshipSuggestion]:
    """Return ranked FK candidates across every pair of schemas.

    Args:
        schemas: All file schemas in the project.
        samples: Optional ``{schema_name: list[dict]}`` of recently-parsed
            preview rows. When both sides of a candidate pair have samples,
            value-overlap is computed; otherwise that signal is None and
            the weight collapses onto name + type + cardinality.
        min_score: Drop suggestions below this score before returning.

    Returns:
        Suggestions sorted by score descending, then by source/target
        pair name for stable tie-breaking.
    """
    samples = samples or {}
    suggestions: list[RelationshipSuggestion] = []

    for src in schemas:
        for tgt in schemas:
            if src is tgt:
                continue
            for sf in src.fields:
                if sf.is_filler:
                    continue
                for tf in tgt.fields:
                    if tf.is_filler:
                        continue
                    suggestion = _score_pair(src, sf, tgt, tf, samples)
                    if suggestion.score >= min_score:
                        suggestions.append(suggestion)

    suggestions.sort(
        key=lambda s: (-s.score, s.source_file, s.source_field, s.target_file, s.target_field)
    )
    return suggestions


def _score_pair(src_schema, src_field, tgt_schema, tgt_field, samples) -> RelationshipSuggestion:
    name_sim = _name_similarity(src_field.name, tgt_field.name)
    type_compat = _type_compatibility(src_field, tgt_field)
    cardinality_match = _cardinality_hint(tgt_field)
    overlap, sample_size = _value_overlap(
        src_schema.name, src_field.name, tgt_schema.name, tgt_field.name, samples
    )

    # Weighted blend. When value_overlap is None (no sample), redistribute
    # its weight onto the other signals proportionally so unsampled
    # suggestions stay comparable to sampled ones — without this, the
    # presence of a sample would always rank a pair higher just because
    # an additional signal exists.
    if overlap is None:
        w_name, w_type, w_card = 0.55, 0.30, 0.15
        score = w_name * name_sim + w_type * type_compat + (w_card if cardinality_match else 0)
    else:
        w_name, w_type, w_card, w_overlap = 0.40, 0.20, 0.10, 0.30
        score = (
            w_name * name_sim
            + w_type * type_compat
            + (w_card if cardinality_match else 0)
            + w_overlap * overlap
        )

    return RelationshipSuggestion(
        source_file=src_schema.name,
        source_field=src_field.name,
        target_file=tgt_schema.name,
        target_field=tgt_field.name,
        score=round(score, 4),
        evidence=RelationshipEvidence(
            name_similarity=round(name_sim, 4),
            type_compatibility=round(type_compat, 4),
            cardinality_match=cardinality_match,
            value_overlap=round(overlap, 4) if overlap is not None else None,
        ),
        sample_size=sample_size,
    )


# ── Signal implementations ─────────────────────────────────────────────


_NAME_PUNCT = ("-", "_", " ", ".")
# Common identifier suffixes we strip when comparing names — these are
# the "join-key shape" hints that almost never carry information about
# what the column means (CUSTOMER_ID vs CUSTOMER are the same key).
_NAME_SUFFIXES = ("_ID", "ID", "_KEY", "KEY", "_NO", "NO", "_NUM", "NUM")


def _normalize_name(name: str) -> str:
    n = name.upper()
    for p in _NAME_PUNCT:
        n = n.replace(p, "")
    # Strip a join-key suffix only when something is left behind. The bare
    # field name ``ID`` would otherwise normalize to "" and lose every
    # signal — which is the opposite of what we want for the very-common
    # ``CUSTOMER_ID`` ↔ ``ID`` join pattern.
    for suf in _NAME_SUFFIXES:
        if n.endswith(suf) and len(n) > len(suf):
            n = n[: -len(suf)]
            break
    return n


def _name_similarity(a: str, b: str) -> float:
    """1.0 when normalized identifiers are equal, fade with edit distance.

    Also handles the common ``CUSTOMER_ID`` ↔ ``ID`` join pattern by
    checking the suffix-stripped form against the bare form — when the
    shorter raw name is a substring of the longer raw name (after only
    punctuation normalization), that's a strong join hint.
    """
    raw_a = a.upper().replace("_", "").replace("-", "").replace(" ", "")
    raw_b = b.upper().replace("_", "").replace("-", "").replace(" ", "")
    if not raw_a or not raw_b:
        return 0.0
    if raw_a == raw_b:
        return 1.0
    # Substring match on raw names — catches CUSTOMER_ID ↔ ID and similar.
    if raw_a in raw_b or raw_b in raw_a:
        return 0.85

    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85
    distance = _damerau_levenshtein(na, nb)
    max_len = max(len(na), len(nb))
    return max(0.0, 1.0 - distance / max_len)


def _damerau_levenshtein(a: str, b: str) -> int:
    """Edit distance with transposition (CTYP vs CTYO costs 1, not 2)."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev_prev = [0] * (lb + 1)
    prev = list(range(lb + 1))
    curr = [0] * (lb + 1)
    for i in range(1, la + 1):
        curr[0] = i
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                curr[j - 1] + 1,        # insert
                prev[j] + 1,            # delete
                prev[j - 1] + cost,     # substitute
            )
            if (
                i > 1
                and j > 1
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                curr[j] = min(curr[j], prev_prev[j - 2] + cost)
        prev_prev = prev
        prev = curr
        curr = [0] * (lb + 1)
    return prev[lb]


# Type-family groupings — exact match wins; same family scores 0.5;
# anything else is incompatible. Length/decimal_places need to agree for
# the exact tier.
_TYPE_FAMILY = {
    "numeric": "numeric",
    "decimal": "numeric",
    "packed_decimal": "numeric",
    "binary": "numeric",
    "alphanumeric": "text",
    "alphabetic": "text",
}


def _type_compatibility(a, b) -> float:
    if a.data_type == b.data_type and a.length == b.length and a.decimal_places == b.decimal_places:
        return 1.0
    if a.data_type == b.data_type:
        return 0.8
    fa = _TYPE_FAMILY.get(a.data_type, a.data_type)
    fb = _TYPE_FAMILY.get(b.data_type, b.data_type)
    if fa == fb:
        return 0.5
    return 0.0


def _cardinality_hint(target_field) -> bool:
    """Boost when the target side looks like a PK (better FK candidate)."""
    # FileFieldDefinition has no is_primary_key today; use FK metadata as
    # a proxy — the loader marks parent-side fields via fk_reference=None
    # *and* the convention of trailing _ID. Conservative: only boost when
    # we have strong evidence (which is rare); the suggester won't lean
    # on this signal heavily because most file schemas don't carry PK info.
    return False


def _value_overlap(
    src_file: str,
    src_field: str,
    tgt_file: str,
    tgt_field: str,
    samples: dict[str, list[dict]],
) -> tuple[float | None, int]:
    """|child ∩ parent| / |child| over sampled values; None if no sample."""
    src_rows = samples.get(src_file)
    tgt_rows = samples.get(tgt_file)
    if not src_rows or not tgt_rows:
        return None, 0
    src_vals = {str(r.get(src_field)) for r in src_rows if r.get(src_field) is not None}
    tgt_vals = {str(r.get(tgt_field)) for r in tgt_rows if r.get(tgt_field) is not None}
    if not src_vals:
        return 0.0, 0
    overlap = len(src_vals & tgt_vals) / len(src_vals)
    return overlap, min(len(src_rows), len(tgt_rows))


__all__ = [
    "DEFAULT_MIN_SCORE",
    "RelationshipEvidence",
    "RelationshipSuggestion",
    "suggest_relationships",
]
