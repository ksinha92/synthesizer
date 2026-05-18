"""Tests for QualityEvaluator — composite scoring and metrics."""
import pytest
import numpy as np
import pandas as pd

from app.infrastructure.engine.quality_evaluator import QualityEvaluator


@pytest.fixture
def evaluator():
    return QualityEvaluator()


@pytest.fixture
def sample_real_data():
    """Sample real data as DataFrame."""
    np.random.seed(42)
    return pd.DataFrame({
        "age": np.random.normal(35, 10, 100),
        "income": np.random.normal(60000, 15000, 100),
        "score": np.random.uniform(0, 100, 100),
    })


@pytest.fixture
def sample_synthetic_data():
    """Synthetic data similar to real — should score well."""
    np.random.seed(99)
    return pd.DataFrame({
        "age": np.random.normal(35, 10, 100),
        "income": np.random.normal(60000, 15000, 100),
        "score": np.random.uniform(0, 100, 100),
    })


@pytest.fixture
def poor_synthetic_data():
    """Synthetic data very different from real — should score poorly."""
    np.random.seed(7)
    return pd.DataFrame({
        "age": np.random.normal(80, 2, 100),
        "income": np.random.uniform(0, 1000, 100),
        "score": [50.0] * 100,
    })


class TestCompositeScore:
    def test_score_is_between_0_and_100(self, evaluator, sample_real_data, sample_synthetic_data):
        result = evaluator.evaluate(sample_real_data, sample_synthetic_data)
        assert 0 <= result.composite_score <= 100

    def test_good_synthetic_scores_higher(self, evaluator, sample_real_data, sample_synthetic_data, poor_synthetic_data):
        good_result = evaluator.evaluate(sample_real_data, sample_synthetic_data)
        poor_result = evaluator.evaluate(sample_real_data, poor_synthetic_data)
        assert good_result.composite_score >= poor_result.composite_score


class TestColumnScores:
    def test_returns_per_column_scores(self, evaluator, sample_real_data, sample_synthetic_data):
        result = evaluator.evaluate(sample_real_data, sample_synthetic_data)
        for col in sample_real_data.columns:
            assert col in result.column_scores
            assert 0 <= result.column_scores[col]["score"] <= 1

    def test_column_types_detected(self, evaluator, sample_real_data, sample_synthetic_data):
        result = evaluator.evaluate(sample_real_data, sample_synthetic_data)
        for col, info in result.column_scores.items():
            assert "type" in info


class TestPrivacyMetrics:
    def test_privacy_metrics_present(self, evaluator, sample_real_data, sample_synthetic_data):
        result = evaluator.evaluate(sample_real_data, sample_synthetic_data)
        pm = result.privacy_metrics
        assert "dcr_mean" in pm
        assert "dcr_min" in pm
        assert "identical_matches" in pm
        assert "identical_match_pct" in pm

    def test_identical_match_pct_between_0_and_1(self, evaluator, sample_real_data, sample_synthetic_data):
        result = evaluator.evaluate(sample_real_data, sample_synthetic_data)
        assert 0 <= result.privacy_metrics["identical_match_pct"] <= 1


class TestCorrelation:
    def test_column_pair_score(self, evaluator, sample_real_data, sample_synthetic_data):
        result = evaluator.evaluate(sample_real_data, sample_synthetic_data)
        assert 0 <= result.column_pair_score <= 1
