"""Unit tests for PII detection pipeline."""

import pytest
from unittest.mock import AsyncMock

from app.domain.discovery.value_objects import Classification, PIIType
from app.infrastructure.ai.pii_detector import PIIDetectionService


class TestRegexDetection:
    def setup_method(self):
        self.service = PIIDetectionService(llm_provider=None)

    def test_regex_detects_email(self, sample_column):
        col = sample_column(sample_values=["john@email.com", "jane@test.org"])
        result = self.service._detect_regex(col)
        assert result[0] == PIIType.EMAIL
        assert result[1] >= 0.9

    def test_regex_detects_ssn(self, sample_column):
        col = sample_column(sample_values=["123-45-6789", "987-65-4321"])
        result = self.service._detect_regex(col)
        assert result[0] == PIIType.SSN
        assert result[1] >= 0.9

    def test_regex_detects_phone(self, sample_column):
        col = sample_column(sample_values=["555-123-4567", "(800) 555-0100"])
        result = self.service._detect_regex(col)
        assert result[0] == PIIType.PHONE
        assert result[1] >= 0.8

    def test_regex_no_match(self, sample_column):
        col = sample_column(sample_values=["hello", "world", "42"])
        result = self.service._detect_regex(col)
        assert result[0] == PIIType.NONE


class TestHeuristicsDetection:
    def setup_method(self):
        self.service = PIIDetectionService(llm_provider=None)

    def test_heuristics_detects_email_column(self, sample_column):
        col = sample_column(column_name="email_address")
        result = self.service._detect_heuristics(col)
        assert result[0] == PIIType.EMAIL
        assert result[1] >= 0.7

    def test_heuristics_detects_ssn_column(self, sample_column):
        col = sample_column(column_name="ssn")
        result = self.service._detect_heuristics(col)
        assert result[0] == PIIType.SSN
        assert result[1] >= 0.8

    def test_heuristics_detects_phone_column(self, sample_column):
        col = sample_column(column_name="phone_number")
        result = self.service._detect_heuristics(col)
        assert result[0] == PIIType.PHONE

    def test_heuristics_no_match(self, sample_column):
        col = sample_column(column_name="created_at")
        result = self.service._detect_heuristics(col)
        assert result[0] == PIIType.NONE


class TestLLMFallback:
    @pytest.mark.asyncio
    async def test_llm_not_called_when_confidence_high(self, sample_column, mock_llm_provider):
        service = PIIDetectionService(llm_provider=mock_llm_provider)
        col = sample_column(column_name="email", sample_values=["john@email.com"])
        await service.detect([col])
        mock_llm_provider.classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_called_when_confidence_low(self, sample_column, mock_llm_provider):
        service = PIIDetectionService(llm_provider=mock_llm_provider)
        col = sample_column(column_name="x_field_99", sample_values=["abc123"])
        await service.detect([col])
        mock_llm_provider.classify.assert_called_once()


class TestCombineScores:
    def test_auto_classify_threshold(self):
        results = [(PIIType.EMAIL, 0.65, "regex")]
        pii_type, confidence, classification = PIIDetectionService._combine_scores(results)
        assert classification == Classification.AUTO_CLASSIFIED

    def test_needs_review_threshold(self):
        results = [(PIIType.PERSON_NAME, 0.5, "heuristic")]
        pii_type, confidence, classification = PIIDetectionService._combine_scores(results)
        assert classification == Classification.NEEDS_REVIEW

    def test_dismissed_below_threshold(self):
        results = [(PIIType.OTHER, 0.2, "heuristic")]
        pii_type, confidence, classification = PIIDetectionService._combine_scores(results)
        assert classification == Classification.DISMISSED

    def test_highest_confidence_wins(self):
        results = [
            (PIIType.EMAIL, 0.95, "regex"),
            (PIIType.PERSON_NAME, 0.6, "presidio"),
        ]
        pii_type, confidence, classification = PIIDetectionService._combine_scores(results)
        assert pii_type == PIIType.EMAIL
        assert confidence.score == 0.95
