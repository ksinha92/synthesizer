"""Quality evaluation for synthetic data — composite scoring with privacy metrics.
Uses scipy/numpy directly (no sdmetrics — BUSL license)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import structlog
from scipy import stats

logger = structlog.get_logger()

MAX_DCR_SYNTHETIC = 1_000
MAX_DCR_REAL = 5_000


@dataclass
class QualityReport:
    composite_score: float = 0.0
    column_scores: dict = field(default_factory=dict)
    column_pair_score: float = 0.0
    privacy_metrics: dict = field(default_factory=dict)


class QualityEvaluator:
    """Evaluate synthetic data quality against real data."""

    def evaluate(self, real: pd.DataFrame, synthetic: pd.DataFrame) -> QualityReport:
        if real.empty or synthetic.empty:
            return QualityReport()

        # Align columns
        common_cols = [c for c in real.columns if c in synthetic.columns]
        real = real[common_cols]
        synthetic = synthetic[common_cols]

        # Per-column shape scores
        column_scores = {}
        for col in common_cols:
            score = self._column_shape_score(real[col], synthetic[col])
            col_type = "numeric" if pd.api.types.is_numeric_dtype(real[col]) else "categorical"
            column_scores[col] = {"score": round(score, 3), "type": col_type}

        # Column pair correlation
        pair_score = self._column_pair_score(real, synthetic)

        # Privacy metrics
        privacy = self._privacy_metrics(real, synthetic)

        # Composite: 40% shapes + 30% pairs + 30% privacy
        avg_shape = np.mean([v["score"] for v in column_scores.values()]) if column_scores else 0.0
        privacy_score = 1.0 - privacy.get("identical_match_pct", 0.0)  # Higher is better
        composite = (0.4 * avg_shape + 0.3 * pair_score + 0.3 * privacy_score) * 100

        report = QualityReport(
            composite_score=round(min(max(composite, 0), 100), 1),
            column_scores=column_scores,
            column_pair_score=round(pair_score, 3),
            privacy_metrics=privacy,
        )

        logger.info("quality_evaluated", composite=report.composite_score, columns=len(column_scores))
        return report

    def _column_shape_score(self, real_col: pd.Series, synth_col: pd.Series) -> float:
        """Score how well synthetic matches real distribution. 0-1."""
        real_clean = real_col.dropna()
        synth_clean = synth_col.dropna()

        if real_clean.empty or synth_clean.empty:
            return 0.0

        if pd.api.types.is_numeric_dtype(real_col):
            # KS test for numeric
            try:
                ks_stat, _ = stats.ks_2samp(real_clean.astype(float), synth_clean.astype(float))
                return max(0.0, 1.0 - ks_stat)
            except (ValueError, TypeError):
                return 0.5
        else:
            # Chi-squared-like for categorical
            try:
                real_counts = real_clean.value_counts(normalize=True)
                synth_counts = synth_clean.value_counts(normalize=True)
                all_cats = set(real_counts.index) | set(synth_counts.index)
                real_dist = np.array([real_counts.get(c, 0) for c in all_cats])
                synth_dist = np.array([synth_counts.get(c, 0) for c in all_cats])
                # Total variation distance
                tvd = 0.5 * np.sum(np.abs(real_dist - synth_dist))
                return max(0.0, 1.0 - tvd)
            except Exception:
                return 0.5

    def _column_pair_score(self, real: pd.DataFrame, synthetic: pd.DataFrame) -> float:
        """Score correlation preservation between column pairs. 0-1."""
        numeric_cols = real.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) < 2:
            return 1.0  # Nothing to compare

        try:
            real_corr = real[numeric_cols].corr().values
            synth_corr = synthetic[numeric_cols].corr().values

            # Replace NaN with 0
            real_corr = np.nan_to_num(real_corr, 0)
            synth_corr = np.nan_to_num(synth_corr, 0)

            mean_abs_diff = np.mean(np.abs(real_corr - synth_corr))
            return max(0.0, 1.0 - mean_abs_diff)
        except Exception:
            return 0.5

    def _privacy_metrics(self, real: pd.DataFrame, synthetic: pd.DataFrame) -> dict:
        """Compute DCR and identical match metrics. Capped for performance."""
        numeric_cols = real.select_dtypes(include=[np.number]).columns.tolist()

        # Sample for DCR (O(n*m) — hard cap)
        synth_sample = synthetic.head(MAX_DCR_SYNTHETIC)
        real_sample = real.head(MAX_DCR_REAL)

        # Identical matches (exact row match)
        try:
            merged = pd.merge(synthetic, real, how="inner")
            identical_count = len(merged)
            identical_pct = identical_count / max(len(synthetic), 1)
        except Exception:
            identical_count = 0
            identical_pct = 0.0

        # DCR on numeric columns
        dcr_mean = 0.0
        dcr_min = 0.0
        if numeric_cols and len(synth_sample) > 0 and len(real_sample) > 0:
            try:
                synth_arr = synth_sample[numeric_cols].fillna(0).values.astype(float)
                real_arr = real_sample[numeric_cols].fillna(0).values.astype(float)

                # Normalize columns to 0-1 for fair distance
                col_min = np.minimum(synth_arr.min(axis=0), real_arr.min(axis=0))
                col_max = np.maximum(synth_arr.max(axis=0), real_arr.max(axis=0))
                col_range = col_max - col_min
                col_range[col_range == 0] = 1

                synth_norm = (synth_arr - col_min) / col_range
                real_norm = (real_arr - col_min) / col_range

                # Compute distances: for each synthetic row, min distance to any real row
                distances = []
                for s_row in synth_norm:
                    dists = np.sqrt(np.sum((real_norm - s_row) ** 2, axis=1))
                    distances.append(np.min(dists))

                dcr_mean = float(np.mean(distances))
                dcr_min = float(np.min(distances))
            except Exception as e:
                logger.warning("dcr_computation_failed", error=str(e))

        return {
            "dcr_mean": round(dcr_mean, 4),
            "dcr_min": round(dcr_min, 4),
            "identical_matches": identical_count,
            "identical_match_pct": round(identical_pct, 4),
            "synth_sampled": len(synth_sample),
            "real_sampled": len(real_sample),
        }
