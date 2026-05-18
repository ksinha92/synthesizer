"""4-layer PII detection pipeline."""

from __future__ import annotations

import re
import string

import structlog

from app.domain.discovery.entities import DiscoveredColumn
from app.domain.discovery.value_objects import Classification, PIIConfidence, PIIType

logger = structlog.get_logger()

# --- Layer 1: Regex Patterns ---

_PATTERNS: list[tuple[PIIType, re.Pattern, float]] = [
    (PIIType.EMAIL, re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), 0.95),
    (PIIType.SSN, re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), 0.95),
    (PIIType.CREDIT_CARD, re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), 0.90),
    (PIIType.PHONE, re.compile(r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), 0.85),
    (PIIType.IP_ADDRESS, re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), 0.80),
]

# --- Layer 3: Column Name Heuristics ---

_HEURISTICS: list[tuple[PIIType, list[str], float]] = [
    (PIIType.EMAIL, ["email", "e_mail", "email_address", "emailaddress", "user_email"], 0.70),
    (PIIType.SSN, ["ssn", "social_security", "social_sec", "social_security_number", "sin"], 0.80),
    (PIIType.PHONE, ["phone", "mobile", "cell", "telephone", "phone_number", "fax", "tel"], 0.70),
    (PIIType.PERSON_NAME, ["first_name", "last_name", "full_name", "name", "given_name", "surname", "middle_name"], 0.60),
    (PIIType.ADDRESS, ["address", "street", "city", "zip", "postal", "zip_code", "postal_code", "state", "addr"], 0.60),
    (PIIType.DATE_OF_BIRTH, ["dob", "date_of_birth", "birth_date", "birthdate", "birthday"], 0.70),
    (PIIType.CREDIT_CARD, ["card_number", "credit_card", "cc_num", "cc_number", "card_num"], 0.80),
    (PIIType.IP_ADDRESS, ["ip", "ip_address", "ipaddress", "ip_addr", "client_ip"], 0.70),
    (PIIType.FINANCIAL_ACCOUNT, ["account_number", "acct_num", "bank_account", "routing_number"], 0.75),
    (PIIType.MEDICAL_RECORD, ["medical_record", "mrn", "patient_id", "health_id"], 0.75),
]


class PIIDetectionService:
    """4-layer PII detection: regex → Presidio+spaCy → heuristics → LLM fallback."""

    def __init__(self, llm_provider=None) -> None:
        self._llm_provider = llm_provider
        self._presidio_analyzer = None  # Lazy init — spaCy model is heavy
        self._llm_failure_count = 0
        self._llm_circuit_open = False

    def _get_presidio_analyzer(self):
        """Initialize Presidio AnalyzerEngine once (singleton per service instance)."""
        if self._presidio_analyzer is not None:
            return self._presidio_analyzer

        try:
            from presidio_analyzer import AnalyzerEngine
            self._presidio_analyzer = AnalyzerEngine()
            return self._presidio_analyzer
        except Exception as e:
            logger.warning("presidio_init_failed", error=str(e))
            return None

    async def detect(
        self,
        columns: list[DiscoveredColumn],
        custom_rules: list[dict] | None = None,
    ) -> list[DiscoveredColumn]:
        """Run the detection pipeline on all columns.

        Custom rule precedence is the responsibility of
        ``SchemaDiscoveryService`` — it has both raw samples and the column
        name, so it can rank ALL rule types (column-name + value-regex)
        together in user-defined priority order via ``match_all_rules``. Any
        column that arrives here already stamped with ``detector="custom_rule"``
        is honored: Layers 1-4 are skipped, so ``_combine_scores`` cannot
        overwrite the upstream hit.

        Fallback Layer 0: if a column is NOT pre-classified (typically only
        happens on legacy flows that bypass the discovery service's rule
        pass), evaluate column-name rules locally. ``value_regex`` is
        intentionally NOT evaluated here — samples available to the detector
        are masked.

        Layers 1-4: regex / Presidio / heuristics / LLM fallback.
        """
        from app.infrastructure.ai.custom_rules import match_column_name_rules

        for column in columns:
            # Honor upstream custom-rule matches. The discovery service runs
            # match_all_rules (column-name + value-regex together) against
            # raw samples and stamps detector="custom_rule" when a rule wins.
            # Layers 1-4 are skipped so _combine_scores can't overwrite.
            existing_detector = getattr(column.pii_confidence, "detector", "") or ""
            if existing_detector.startswith("custom_rule"):
                continue

            # Fallback Layer 0 — column-name rules only. value_regex is
            # skipped (samples here are masked; ranking those against
            # column-name rules would also break precedence).
            if custom_rules:
                custom_hit = match_column_name_rules(
                    column.column_name, custom_rules
                )
                if custom_hit is not None:
                    matched_type, matched_score = custom_hit
                    column.pii_type = matched_type
                    column.pii_confidence = PIIConfidence(
                        score=matched_score,
                        detector="custom_rule",
                    )
                    column.classification = Classification.AUTO_CLASSIFIED
                    continue

            results: list[tuple[PIIType, float, str]] = []

            # Layer 1: Regex
            regex_result = self._detect_regex(column)
            if regex_result[0] != PIIType.NONE:
                results.append((*regex_result, "regex"))

            # Layer 2: Presidio + spaCy
            presidio_result = self._detect_presidio(column)
            if presidio_result[0] != PIIType.NONE:
                results.append((*presidio_result, "presidio"))

            # Layer 3: Column name heuristics
            heuristic_result = self._detect_heuristics(column)
            if heuristic_result[0] != PIIType.NONE:
                results.append((*heuristic_result, "heuristic"))

            # Combine scores from Layers 1-3
            max_confidence = max((r[1] for r in results), default=0.0)

            # Layer 4: LLM (only if Layers 1-3 confidence < 0.4)
            if max_confidence < 0.4 and not self._llm_circuit_open:
                llm_result = await self._detect_llm(column)
                if llm_result[0] != PIIType.NONE:
                    results.append((*llm_result, "llm"))

            # Assign final classification
            pii_type, confidence, classification = self._combine_scores(results)
            column.pii_type = pii_type
            column.pii_confidence = confidence
            column.classification = classification

        return columns

    def _detect_regex(self, column: DiscoveredColumn) -> tuple[PIIType, float]:
        """Layer 1: High-precision regex matching on sample values."""
        samples_text = " ".join(str(v) for v in column.sample_values if v)
        if not samples_text:
            return PIIType.NONE, 0.0

        for pii_type, pattern, confidence in _PATTERNS:
            if pattern.search(samples_text):
                return pii_type, confidence

        return PIIType.NONE, 0.0

    def _detect_presidio(self, column: DiscoveredColumn) -> tuple[PIIType, float]:
        """Layer 2: Presidio + spaCy NER."""
        analyzer = self._get_presidio_analyzer()
        if analyzer is None:
            return PIIType.NONE, 0.0

        samples_text = " ".join(str(v) for v in column.sample_values if v)
        if not samples_text or len(samples_text) < 3:
            return PIIType.NONE, 0.0

        try:
            results = analyzer.analyze(text=samples_text, language="en")
            if not results:
                return PIIType.NONE, 0.0

            # Map Presidio entity type to PIIType
            best = max(results, key=lambda r: r.score)
            type_map = {
                "PERSON": PIIType.PERSON_NAME,
                "LOCATION": PIIType.ADDRESS,
                "DATE_TIME": PIIType.DATE_OF_BIRTH,
                "EMAIL_ADDRESS": PIIType.EMAIL,
                "PHONE_NUMBER": PIIType.PHONE,
                "CREDIT_CARD": PIIType.CREDIT_CARD,
                "US_SSN": PIIType.SSN,
                "IP_ADDRESS": PIIType.IP_ADDRESS,
                "MEDICAL_LICENSE": PIIType.MEDICAL_RECORD,
                "US_BANK_NUMBER": PIIType.FINANCIAL_ACCOUNT,
            }
            pii_type = type_map.get(best.entity_type, PIIType.OTHER)
            return pii_type, best.score

        except Exception as e:
            logger.warning("presidio_detection_failed", error=str(e), column=column.column_name)
            return PIIType.NONE, 0.0

    def _detect_heuristics(self, column: DiscoveredColumn) -> tuple[PIIType, float]:
        """Layer 3: Column name pattern matching."""
        col_lower = column.column_name.lower().strip()

        for pii_type, patterns, confidence in _HEURISTICS:
            for pattern in patterns:
                if col_lower == pattern or col_lower.endswith(f"_{pattern}") or col_lower.startswith(f"{pattern}_"):
                    return pii_type, confidence

        return PIIType.NONE, 0.0

    async def _detect_llm(self, column: DiscoveredColumn) -> tuple[PIIType, float]:
        """Layer 4: LLM classification — FALLBACK ONLY when Layers 1-3 < 0.4."""
        if self._llm_provider is None:
            logger.info("llm_skipped", reason="no_provider", column=column.column_name)
            return PIIType.NONE, 0.0

        # Sanitize inputs to prevent prompt injection
        safe_name = _sanitize_for_llm(column.column_name, max_len=100)
        safe_type = _sanitize_for_llm(column.data_type, max_len=50)
        safe_samples = [_sanitize_for_llm(str(v), max_len=200) for v in column.sample_values[:3]]

        try:
            # Check LLM budget before calling
            if hasattr(self._llm_provider, 'check_budget') and not self._llm_provider.check_budget():
                return PIIType.NONE, 0.0

            pii_options = [t.value for t in PIIType]
            prompt = (
                "Classify whether this database column contains personally identifiable information (PII).\n\n"
                f"<column_name>{safe_name}</column_name>\n"
                f"<data_type>{safe_type}</data_type>\n"
                f"<samples>{', '.join(safe_samples)}</samples>\n\n"
                "Valid PII types: email, phone, ssn, credit_card, ip_address, person_name, address, "
                "date_of_birth, medical_record, financial_account, other, none"
            )

            choice, confidence = await self._llm_provider.classify(prompt, pii_options)

            try:
                pii_type = PIIType(choice)
            except ValueError:
                pii_type = PIIType.OTHER if confidence > 0.5 else PIIType.NONE

            return pii_type, confidence

        except Exception as e:
            self._llm_failure_count += 1
            if self._llm_failure_count >= 5:
                self._llm_circuit_open = True
                logger.warning("llm_circuit_opened", failures=self._llm_failure_count)
            logger.warning("llm_detection_failed", error=str(e), column=column.column_name)
            return PIIType.NONE, 0.0

    @staticmethod
    def _combine_scores(
        results: list[tuple[PIIType, float, str]],
    ) -> tuple[PIIType, PIIConfidence, Classification]:
        """Combine multi-layer results into final classification."""
        if not results:
            return (
                PIIType.NONE,
                PIIConfidence(score=0.0, detector="none", details={}),
                Classification.DISMISSED,
            )

        # Take highest confidence detection
        best = max(results, key=lambda r: r[1])
        pii_type, score, detector = best

        # Build details from all layers
        details = {r[2]: {"type": r[0].value, "score": r[1]} for r in results}

        confidence = PIIConfidence(score=score, detector=detector, details=details)

        if score >= 0.65:
            classification = Classification.AUTO_CLASSIFIED
        elif score >= 0.4:
            classification = Classification.NEEDS_REVIEW
        else:
            classification = Classification.DISMISSED

        return pii_type, confidence, classification


def _sanitize_for_llm(text: str, max_len: int = 200) -> str:
    """Sanitize text before including in LLM prompt. Prevents prompt injection."""
    # Strip control characters
    cleaned = "".join(c for c in text if c in string.printable and c not in "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f")
    # Truncate
    return cleaned[:max_len]
