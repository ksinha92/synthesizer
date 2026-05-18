"""HIPAA compliance report generator."""

from __future__ import annotations

from datetime import datetime, timezone


class HIPAAReporter:
    """Generates HIPAA compliance report from PII detections and masking data."""

    def generate(self, pii_columns: list[dict], masking_rules: list[dict], project_info: dict) -> dict:
        total_pii = len(pii_columns)
        masked = sum(1 for c in pii_columns if c.get("classification") == "auto_classified" or c.get("masked", False))
        unmasked = total_pii - masked
        coverage = round(masked / max(total_pii, 1) * 100, 1)

        return {
            "regulation": "HIPAA",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": project_info,
            "sections": {
                "phi_inventory": {
                    "title": "Protected Health Information (PHI) Inventory",
                    "total_pii_columns": total_pii,
                    "columns": [
                        {"table": c.get("table_name", ""), "column": c.get("column_name", ""), "pii_type": c.get("pii_type", ""), "confidence": c.get("confidence", 0)}
                        for c in pii_columns
                    ],
                },
                "access_controls": {
                    "title": "Access Controls Summary",
                    "description": "Role-based access control is configured per project.",
                    "note": "RBAC enforced via project-scoped membership; full audit trail via /admin/audit-logs (see infrastructure/auth/rbac.py)",
                },
                "encryption_masking_status": {
                    "title": "Encryption & Masking Status",
                    "total_pii": total_pii,
                    "masked_count": masked,
                    "unmasked_count": unmasked,
                    "coverage_percentage": coverage,
                    "strategies_used": list(set(r.get("masking_type", "") for r in masking_rules)),
                },
                "data_flow": {
                    "title": "Data Flow Documentation",
                    "connections": project_info.get("connections", []),
                },
                "risk_assessment": {
                    "title": "Risk Assessment",
                    "high_risk_columns": [c for c in pii_columns if c.get("confidence", 0) >= 0.8 and not c.get("masked", False)],
                    "risk_level": "HIGH" if unmasked > 0 else "LOW",
                },
            },
            "summary": {
                "total_pii_columns": total_pii,
                "coverage_percentage": coverage,
                "risk_level": "HIGH" if unmasked > 0 else "LOW",
            },
        }
