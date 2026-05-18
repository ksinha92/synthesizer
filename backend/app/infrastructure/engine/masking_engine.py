"""Masking engine — 7 strategies with deterministic HMAC and chunked processing."""

from __future__ import annotations

import hashlib
import hmac
import random
import string
from typing import Any

import structlog
from faker import Faker

from app.domain.masking.value_objects import MaskingStrategy

logger = structlog.get_logger()

CHUNK_SIZE = 10_000


class MaskingEngine:
    """Applies masking strategies to data values and DataFrames."""

    def __init__(self, salt: str) -> None:
        self._salt = salt
        self._faker = Faker()
        self._fpe_key = None
        self._fpe_tweak = None
        self._presidio_analyzer = None  # Lazy-init in _presidio_redact

    def _get_presidio_analyzer(self):
        """Lazy-load Presidio AnalyzerEngine (spaCy model loads slowly)."""
        if self._presidio_analyzer is None:
            try:
                from presidio_analyzer import AnalyzerEngine
                self._presidio_analyzer = AnalyzerEngine()
            except Exception as exc:
                logger.warning("presidio_unavailable", error=str(exc))
                self._presidio_analyzer = False  # Sentinel for "tried, failed"
        return self._presidio_analyzer if self._presidio_analyzer is not False else None

    def mask_value(
        self,
        value: Any,
        strategy: MaskingStrategy,
        config: dict | None = None,
        consistency_group: str | None = None,
        row_seed: str | None = None,
    ) -> Any:
        """Mask a single value using the specified strategy.

        Phase 56-04 additions:
        - ``consistency_group`` mixes a group label into the HMAC salt so the
          same input value in the same group produces the same hash across
          every column in the group.
        - ``row_seed`` derives a per-row Faker seed so ``faker_replace`` for
          linked columns generates correlated values within a single row
          (e.g. matched ``city`` / ``state`` pairs).
        """
        if value is None:
            return None

        config = config or {}
        str_value = str(value)

        if strategy == MaskingStrategy.HASH:
            return self._hash(str_value, consistency_group=consistency_group)
        elif strategy == MaskingStrategy.REDACT:
            return self._redact(str_value, config)
        elif strategy == MaskingStrategy.FAKER_REPLACE:
            return self._faker_replace(config, row_seed=row_seed)
        elif strategy == MaskingStrategy.NULLIFY:
            return None
        elif strategy == MaskingStrategy.FPE:
            return self._fpe(str_value, config)
        elif strategy == MaskingStrategy.PARTIAL_MASK:
            return self._partial_mask(str_value, config)
        elif strategy == MaskingStrategy.PRESIDIO_REDACT:
            return self._presidio_redact(str_value, config)
        elif strategy == MaskingStrategy.SHUFFLE:
            return value  # Shuffle operates on column level, not single value
        else:
            return self._redact(str_value, config)

    def mask_column(self, values: list[Any], strategy: MaskingStrategy, config: dict | None = None) -> list[Any]:
        """Mask an entire column. Required for shuffle strategy."""
        if strategy == MaskingStrategy.SHUFFLE:
            return self._shuffle(values, config)
        return [self.mask_value(v, strategy, config) for v in values]

    def mask_preview(self, rows: list[dict], rules: list[dict], limit: int = 5) -> list[dict]:
        """Generate side-by-side preview: [{original: {}, masked: {}}]."""
        preview = []
        for row in rows[:limit]:
            masked_row = self.mask_row(row, rules)
            preview.append({"original": dict(row), "masked": masked_row})
        return preview

    def mask_row(self, row: dict, rules: list[dict]) -> dict:
        """Apply every rule to one row, honoring consistency_group + linked columns.

        Phase 56-04:
        - Rules sharing the same ``consistency_group`` produce the same masked
          output when their inputs are equal (so a customer's masked id stays
          identical across every column that references it).
        - For ``faker_replace`` rules with ``linked_column_ids``, the engine
          derives a deterministic per-row seed from the linked columns so
          generators produce internally-consistent paired output (City→State,
          etc.). Without linked columns the seed is the row identity, so a
          single row's faker output stays stable across re-renders.

        Phase 51-DBV:
        - Column names may be dotted paths (``address.city``) that target
          nested fields in document-store rows (MongoDB). Before, the flat
          ``not in`` check made every nested-path rule a silent no-op. The
          ``_resolve_path`` helpers walk the dotted path on read and write,
          so a Mongo masking rule on ``address.city`` actually masks the
          inner value instead of skipping it.
        """
        masked_row = dict(row)
        # Pre-compute a row-identity seed once. Caller can override per-rule
        # via linked_column_ids → values lookup below.
        base_row_seed = self._hash(
            "|".join(f"{k}={row.get(k)}" for k in sorted(row.keys()))
        )

        for rule in rules:
            col_name = rule.get("column_name", "")
            present, current_value = _resolve_path_get(masked_row, col_name)
            if not present:
                continue
            strategy = MaskingStrategy(rule.get("masking_type", "redact"))
            # SHUFFLE (and any future column-only strategy) cannot be applied
            # per row — mask_value returns the value unchanged for SHUFFLE.
            # Refuse to silently no-op: tell the caller to send the rule
            # through mask_column instead.
            if strategy == MaskingStrategy.SHUFFLE:
                raise ValueError(
                    f"Rule for column {col_name!r} uses SHUFFLE, which is "
                    "a column-only strategy; apply via mask_column, not mask_row"
                )
            consistency_group = rule.get("consistency_group")

            # Build per-rule row seed from linked-column values, falling back
            # to base_row_seed when no linkage is declared. Linked-column
            # names also support dotted paths so a faker_replace pair like
            # ``address.city`` / ``address.state`` stays internally consistent.
            linked_names = rule.get("linked_column_names") or []
            if linked_names:
                linked_pairs = []
                for n in sorted(linked_names):
                    _, lv = _resolve_path_get(row, n)
                    linked_pairs.append(f"{n}={lv}")
                row_seed = self._hash("|".join(linked_pairs))
            else:
                row_seed = base_row_seed

            masked = self.mask_value(
                current_value,
                strategy,
                rule.get("masking_config"),
                consistency_group=consistency_group,
                row_seed=row_seed,
            )
            _resolve_path_set(masked_row, col_name, masked)
        return masked_row

    # --- Strategy Implementations ---

    def _hash(self, value: str, consistency_group: str | None = None) -> str:
        """Deterministic HMAC-SHA256 hash.

        Without ``consistency_group``: same input + global salt → same output.
        With ``consistency_group``: same input + same group + salt → same
        output across every column tagged with that group.
        """
        salted_key = (
            f"{self._salt}|group:{consistency_group}"
            if consistency_group
            else self._salt
        )
        h = hmac.new(salted_key.encode(), value.encode(), hashlib.sha256)
        return h.hexdigest()[:16]

    def _redact(self, value: str, config: dict) -> str:
        """Replace with redaction character."""
        char = config.get("char", "X")
        return char * len(value)

    def _faker_replace(self, config: dict, row_seed: str | None = None) -> Any:
        """Replace with realistic Faker-generated value.

        When ``row_seed`` is provided, Faker is seeded deterministically from
        it so columns sharing the same linked-column values produce paired
        output that stays consistent within a row.
        """
        if row_seed is not None:
            # Convert the hex seed string to an int and reseed.
            try:
                seed_int = int(row_seed, 16)
            except ValueError:
                seed_int = abs(hash(row_seed))
            self._faker.seed_instance(seed_int)

        provider = config.get("provider", "text")
        if hasattr(self._faker, provider):
            return getattr(self._faker, provider)()
        return self._faker.text(max_nb_chars=50)

    def _shuffle(self, values: list[Any], config: dict | None = None) -> list[Any]:
        """Random permutation of column values."""
        non_null = [v for v in values if v is not None]
        unique_count = len(set(str(v) for v in non_null))

        if unique_count < 10:
            logger.warning(
                "shuffle_low_cardinality",
                unique_values=unique_count,
                message="Shuffle provides weak protection for low-cardinality columns. Consider redact or hash.",
            )

        shuffled = list(values)
        random.shuffle(shuffled)
        return shuffled

    def _fpe(self, value: str, config: dict) -> str:
        """Format-preserving encryption via FF3-1 with HKDF-derived key."""
        try:
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashes
            import ff3

            if self._fpe_key is None:
                # Derive AES-128 key from salt via HKDF
                hkdf_key = HKDF(
                    algorithm=hashes.SHA256(),
                    length=16,
                    salt=b"datawrangler-fpe-key",
                    info=b"fpe-aes-key",
                )
                self._fpe_key = hkdf_key.derive(self._salt.encode())

                # Derive 7-byte tweak
                hkdf_tweak = HKDF(
                    algorithm=hashes.SHA256(),
                    length=7,
                    salt=b"datawrangler-fpe-tweak",
                    info=b"fpe-tweak",
                )
                self._fpe_tweak = hkdf_tweak.derive(self._salt.encode()).hex()

            # Determine alphabet
            if value.isdigit():
                alphabet = string.digits
            elif value.isalpha():
                alphabet = string.ascii_lowercase
            else:
                alphabet = string.ascii_lowercase + string.digits

            # FF3 requires min 2 chars
            if len(value) < 2:
                return self._hash(value)[:len(value)] if value else value

            cipher = ff3.FF3Cipher(self._fpe_key.hex(), self._fpe_tweak, radix=len(alphabet))

            # Normalize to alphabet indices
            normalized = ""
            for c in value.lower():
                if c in alphabet:
                    normalized += c
                else:
                    normalized += alphabet[0]

            if len(normalized) < 2:
                return self._hash(value)[:len(value)]

            encrypted = cipher.encrypt(normalized)
            return encrypted[:len(value)]

        except Exception as e:
            logger.warning("fpe_fallback_to_hash", error=str(e))
            return self._hash(value)[:len(value)]

    def _presidio_redact(self, value: str, config: dict) -> str:
        """Free-text PII redaction using Presidio's entity detector.

        Detects PII spans (PERSON, EMAIL_ADDRESS, US_SSN, PHONE_NUMBER, etc.)
        and replaces each span with a typed placeholder so the surrounding
        narrative text stays readable. Empty input + Presidio-unavailable
        environments fall through to ``_redact`` so behavior is well-defined.

        ``config`` knobs:
        - ``language``: ISO language code, default "en".
        - ``entities``: list[str] restricting detection to specific entity
          types (default: detect all that Presidio knows).
        - ``score_threshold``: float in [0, 1], default 0.5 — lower catches
          more (and risks false positives).
        - ``placeholder_format``: format string with ``{type}`` token,
          default ``"[{type}]"``. e.g. ``"<{type}>"`` or ``"REDACTED"``.
        """
        if not value:
            return value

        analyzer = self._get_presidio_analyzer()
        if analyzer is None:
            # No NLP runtime available — degrade to whole-value redact so
            # callers get the safer behavior rather than a leaked value.
            return self._redact(value, config)

        language = config.get("language", "en")
        entities = config.get("entities")  # None means "all known"
        score_threshold = float(config.get("score_threshold", 0.5))
        placeholder_format = config.get("placeholder_format", "[{type}]")

        try:
            results = analyzer.analyze(
                text=value,
                entities=entities,
                language=language,
                score_threshold=score_threshold,
            )
        except Exception as exc:
            logger.warning("presidio_analyze_failed", error=str(exc))
            return self._redact(value, config)

        if not results:
            return value

        # Replace spans back-to-front so earlier offsets stay valid as we
        # splice. Presidio returns overlapping results sometimes; keep the
        # highest-scoring one per range.
        spans = sorted(results, key=lambda r: (r.start, -r.score))
        kept: list = []
        last_end = -1
        for r in spans:
            if r.start >= last_end:
                kept.append(r)
                last_end = r.end

        out = value
        for r in reversed(kept):
            placeholder = placeholder_format.format(type=r.entity_type)
            out = out[: r.start] + placeholder + out[r.end :]
        return out

    def _partial_mask(self, value: str, config: dict) -> str:
        """Show first N and last M chars, mask middle."""
        show_first = config.get("show_first", 1)
        show_last = config.get("show_last", 4)
        mask_char = config.get("mask_char", "*")

        if len(value) <= show_first + show_last:
            return mask_char * len(value)

        first = value[:show_first]
        last = value[-show_last:] if show_last > 0 else ""
        middle = mask_char * (len(value) - show_first - show_last)
        return first + middle + last


def _resolve_path_get(row: dict, path: str) -> tuple[bool, Any]:
    """Look up a dotted path against a possibly-nested dict.

    Returns ``(present, value)``. ``present`` is False when any segment is
    missing or any intermediate value is not a dict — the engine treats
    that as "no rule applies to this row" rather than raising, matching the
    flat-key behavior callers already rely on.

    Flat keys are tried first so MongoDB documents whose flattener already
    produced ``{"address.city": "NYC"}`` (the Database View preview shape)
    work unchanged.
    """
    if path in row:
        return True, row[path]
    parts = path.split(".")
    if len(parts) == 1:
        return False, None
    cursor: Any = row
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            return False, None
        cursor = cursor[part]
    return True, cursor


def _resolve_path_set(row: dict, path: str, value: Any) -> None:
    """Set a dotted path on a possibly-nested dict, mirroring _resolve_path_get.

    If the flat key exists at the top level, prefer assigning there so the
    masked row keeps the same shape as the input (important for the
    flattened-preview path). Otherwise walk + create intermediate dicts.
    """
    if path in row:
        row[path] = value
        return
    parts = path.split(".")
    if len(parts) == 1:
        row[parts[0]] = value
        return
    cursor: Any = row
    for part in parts[:-1]:
        next_cursor = cursor.get(part) if isinstance(cursor, dict) else None
        if not isinstance(next_cursor, dict):
            next_cursor = {}
            cursor[part] = next_cursor
        cursor = next_cursor
    cursor[parts[-1]] = value
