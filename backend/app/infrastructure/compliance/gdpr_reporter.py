"""GDPR compliance report generator."""

from __future__ import annotations

from datetime import datetime, timezone


class GDPRReporter:
    def generate(self, pii_columns: list[dict], masking_rules: list[dict], project_info: dict) -> dict:
        total_pii = len(pii_columns)
        masked = sum(1 for c in pii_columns if c.get("masked", False))
        coverage = round(masked / max(total_pii, 1) * 100, 1)

        # Group PII by category for data mapping
        categories: dict[str, list] = {}
        for c in pii_columns:
            cat = c.get("pii_type", "other")
            categories.setdefault(cat, []).append(c)

        return {
            "regulation": "GDPR",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": project_info,
            "sections": {
                "data_mapping": {
                    "title": "Data Mapping (Article 30)",
                    "categories": {k: len(v) for k, v in categories.items()},
                    "total_personal_data_columns": total_pii,
                    "detail": [{"category": k, "columns": [{"table": c.get("table_name"), "column": c.get("column_name")} for c in v]} for k, v in categories.items()],
                },
                "processing_purposes": {
                    "title": "Processing Purposes",
                    "description": "Test data management — creating safe copies of production data for development and QA environments.",
                    "lawful_basis": "Legitimate interest (Article 6(1)(f)) — necessary for software quality assurance.",
                },
                "dpia": {
                    "title": "Data Protection Impact Assessment (DPIA)",
                    "necessity": "Processing of personal data categories for test environment provisioning.",
                    "risks_identified": [f"{len([c for c in pii_columns if not c.get('masked')])} unmasked PII columns"],
                    "mitigations": ["PII detection pipeline", "7 masking strategies", "Deterministic masking", "Audit trail"],
                },
                "right_to_erasure": {
                    "title": "Right to Erasure (Article 17)",
                    "description": "Test data can be regenerated from synthetic engines. Original PII is masked, not copied.",
                    "erasure_capability": "Synthetic data contains no real personal data. Masked data cannot be reversed.",
                },
            },
            "summary": {"total_pii_columns": total_pii, "coverage_percentage": coverage, "categories": len(categories)},
        }
