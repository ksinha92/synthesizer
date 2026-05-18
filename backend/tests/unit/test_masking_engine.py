"""Unit tests for masking engine."""

from app.domain.masking.value_objects import MaskingStrategy
from app.infrastructure.engine.masking_engine import MaskingEngine


class TestMaskingStrategies:
    def setup_method(self):
        self.engine = MaskingEngine(salt="test-salt-123")

    def test_hash_deterministic(self):
        result1 = self.engine.mask_value("john@email.com", MaskingStrategy.HASH)
        result2 = self.engine.mask_value("john@email.com", MaskingStrategy.HASH)
        assert result1 == result2
        assert result1 != "john@email.com"

    def test_hash_different_values(self):
        r1 = self.engine.mask_value("a", MaskingStrategy.HASH)
        r2 = self.engine.mask_value("b", MaskingStrategy.HASH)
        assert r1 != r2

    def test_redact_replaces(self):
        result = self.engine.mask_value("john@email.com", MaskingStrategy.REDACT)
        assert "john" not in result
        assert len(result) == len("john@email.com")
        assert all(c == "X" for c in result)

    def test_redact_custom_char(self):
        result = self.engine.mask_value("test", MaskingStrategy.REDACT, {"char": "*"})
        assert result == "****"

    def test_nullify(self):
        result = self.engine.mask_value("anything", MaskingStrategy.NULLIFY)
        assert result is None

    def test_nullify_already_none(self):
        result = self.engine.mask_value(None, MaskingStrategy.NULLIFY)
        assert result is None

    def test_partial_mask_default(self):
        result = self.engine.mask_value("john@email.com", MaskingStrategy.PARTIAL_MASK)
        assert result.startswith("j")
        assert result.endswith(".com")
        assert "*" in result

    def test_partial_mask_custom(self):
        result = self.engine.mask_value("1234567890", MaskingStrategy.PARTIAL_MASK, {"show_first": 0, "show_last": 4, "mask_char": "#"})
        assert result.endswith("7890")
        assert result.startswith("#")

    def test_shuffle_returns_same_values(self):
        values = ["a", "b", "c", "d", "e"]
        result = self.engine.mask_column(values, MaskingStrategy.SHUFFLE)
        assert sorted(result) == sorted(values)

    def test_preview_side_by_side(self):
        rows = [{"name": "John", "email": "john@test.com"}]
        rules = [{"column_name": "email", "masking_type": "redact", "masking_config": {}}]
        preview = self.engine.mask_preview(rows, rules)
        assert len(preview) == 1
        assert preview[0]["original"]["email"] == "john@test.com"
        assert preview[0]["masked"]["email"] != "john@test.com"


class TestPresidioRedactFallback:
    """When Presidio can't load (no spaCy model installed), the strategy must
    degrade to whole-value redaction so values never leak through."""

    def setup_method(self):
        self.engine = MaskingEngine(salt="test-salt-123")
        # Force the lazy-loader into the "tried, failed" sentinel so we can
        # exercise the fallback branch without needing the heavy spaCy model.
        self.engine._presidio_analyzer = False

    def test_falls_back_to_redact_when_presidio_unavailable(self):
        out = self.engine.mask_value(
            "Call John at 555-123-4567",
            MaskingStrategy.PRESIDIO_REDACT,
        )
        assert "John" not in out
        assert "555" not in out
        assert len(out) == len("Call John at 555-123-4567")

    def test_empty_string_passthrough(self):
        out = self.engine.mask_value("", MaskingStrategy.PRESIDIO_REDACT)
        assert out == ""

    def test_none_passthrough(self):
        out = self.engine.mask_value(None, MaskingStrategy.PRESIDIO_REDACT)
        assert out is None


class TestPresidioRedactSpanReplacement:
    """Drive _presidio_redact directly with a stub analyzer to verify the
    span-replacement logic without depending on Presidio's spaCy model."""

    def setup_method(self):
        self.engine = MaskingEngine(salt="test-salt-123")

    def _stub_analyzer(self, spans):
        """spans: list of (start, end, entity_type, score) tuples."""
        class _StubResult:
            def __init__(self, start, end, entity_type, score):
                self.start = start
                self.end = end
                self.entity_type = entity_type
                self.score = score

        class _StubAnalyzer:
            def analyze(_self, text, entities=None, language="en", score_threshold=0.5):
                return [
                    _StubResult(s, e, et, sc)
                    for s, e, et, sc in spans
                    if sc >= score_threshold
                ]

        self.engine._presidio_analyzer = _StubAnalyzer()

    def test_single_span_replaced(self):
        text = "Email me at john@example.com please"
        self._stub_analyzer([(12, 28, "EMAIL_ADDRESS", 0.95)])
        out = self.engine.mask_value(text, MaskingStrategy.PRESIDIO_REDACT)
        assert out == "Email me at [EMAIL_ADDRESS] please"

    def test_multiple_spans_back_to_front(self):
        text = "John Doe lives at 1 Main St"
        # Person: 0-8, address: 18-27
        self._stub_analyzer([
            (0, 8, "PERSON", 0.9),
            (18, 27, "LOCATION", 0.85),
        ])
        out = self.engine.mask_value(text, MaskingStrategy.PRESIDIO_REDACT)
        assert out == "[PERSON] lives at [LOCATION]"

    def test_overlapping_spans_keep_first(self):
        text = "John Doe"
        # Two overlapping spans — first one wins; later overlapping span is dropped.
        self._stub_analyzer([
            (0, 8, "PERSON", 0.9),
            (5, 8, "LAST_NAME", 0.7),
        ])
        out = self.engine.mask_value(text, MaskingStrategy.PRESIDIO_REDACT)
        assert out == "[PERSON]"

    def test_custom_placeholder_format(self):
        text = "Call John today"
        self._stub_analyzer([(5, 9, "PERSON", 0.95)])
        out = self.engine.mask_value(
            text,
            MaskingStrategy.PRESIDIO_REDACT,
            {"placeholder_format": "<<{type}>>"},
        )
        assert out == "Call <<PERSON>> today"

    def test_score_threshold_filters_low_confidence(self):
        text = "John was here"
        self._stub_analyzer([(0, 4, "PERSON", 0.3)])  # below default 0.5
        out = self.engine.mask_value(text, MaskingStrategy.PRESIDIO_REDACT)
        assert out == "John was here"  # nothing redacted


class TestNestedPathMasking:
    """mask_row must walk dotted column names through nested dicts.

    Regression: before this fix, every MongoDB masking rule that targeted a
    nested field path (e.g. ``address.city``) was a silent no-op because
    the engine only checked ``col_name in row`` against the top-level keys.
    """

    def setup_method(self):
        self.engine = MaskingEngine(salt="test-salt-nested")

    def test_nested_dotted_path_is_masked(self):
        row = {"_id": "u1", "address": {"city": "Boston", "state": "MA"}}
        rules = [
            {"column_name": "address.city", "masking_type": "redact", "masking_config": {}}
        ]
        masked = self.engine.mask_row(row, rules)
        assert masked["address"]["city"] != "Boston"
        assert masked["address"]["city"] == "X" * len("Boston")
        # Sibling untouched.
        assert masked["address"]["state"] == "MA"

    def test_flat_key_with_dot_still_works(self):
        # If the flattener already produced a flat key like "address.city",
        # we prefer that to walking — preserves shape parity with the preview.
        row = {"_id": "u1", "address.city": "NYC"}
        rules = [
            {"column_name": "address.city", "masking_type": "redact", "masking_config": {}}
        ]
        masked = self.engine.mask_row(row, rules)
        assert masked["address.city"] == "XXX"

    def test_missing_nested_path_is_skipped(self):
        row = {"_id": "u1", "address": {"city": "Boston"}}
        rules = [
            {"column_name": "address.zip", "masking_type": "redact", "masking_config": {}}
        ]
        masked = self.engine.mask_row(row, rules)
        assert masked == row

    def test_non_dict_intermediate_is_skipped(self):
        row = {"_id": "u1", "address": "not-a-dict"}
        rules = [
            {"column_name": "address.city", "masking_type": "redact", "masking_config": {}}
        ]
        masked = self.engine.mask_row(row, rules)
        assert masked["address"] == "not-a-dict"

    def test_deeply_nested_path(self):
        row = {"user": {"profile": {"name": "Alice"}}}
        rules = [
            {"column_name": "user.profile.name", "masking_type": "redact", "masking_config": {}}
        ]
        masked = self.engine.mask_row(row, rules)
        assert masked["user"]["profile"]["name"] == "X" * len("Alice")

    def test_linked_columns_resolve_through_dot(self):
        row = {"address": {"city": "NYC", "state": "NY"}, "name": "Alice"}
        rules = [
            {
                "column_name": "address.city",
                "masking_type": "faker_replace",
                "masking_config": {"provider": "city"},
                "linked_column_names": ["address.city", "address.state"],
            },
            {
                "column_name": "address.state",
                "masking_type": "faker_replace",
                "masking_config": {"provider": "state_abbr"},
                "linked_column_names": ["address.city", "address.state"],
            },
        ]
        a = self.engine.mask_row(row, rules)
        b = self.engine.mask_row(row, rules)
        # Same linked-column seed → same faker output across calls.
        assert a["address"]["city"] == b["address"]["city"]
        assert a["address"]["state"] == b["address"]["state"]
