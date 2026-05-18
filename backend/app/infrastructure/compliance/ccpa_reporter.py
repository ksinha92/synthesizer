"""CCPA compliance report generator."""

from __future__ import annotations

from datetime import datetime, timezone

# CCPA data categories mapping
PII_TO_CCPA_CATEGORY = {
    "email": "Identifiers",
    "phone": "Identifiers",
    "ssn": "Identifiers",
    "person_name": "Identifiers",
    "address": "Identifiers",
    "ip_address": "Internet Activity",
    "date_of_birth": "Protected Classifications",
    "medical_record": "Medical Information",
    "financial_account": "Financial Information",
    "credit_card": "Financial Information",
}


class CCPAReporter:
    def generate(self, pii_columns: list[dict], masking_rules: list[dict], project_info: dict) -> dict:
        total_pii = len(pii_columns)
        masked = sum(1 for c in pii_columns if c.get("masked", False))
        coverage = round(masked / max(total_pii, 1) * 100, 1)

        # Map to CCPA categories
        ccpa_categories: dict[str, list] = {}
        for c in pii_columns:
            cat = PII_TO_CCPA_CATEGORY.get(c.get("pii_type", ""), "Other Personal Information")
            ccpa_categories.setdefault(cat, []).append(c)

        return {
            "regulation": "CCPA",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": project_info,
            "sections": {
                "consumer_data_categories": {
                    "title": "Categories of Personal Information Collected",
                    "categories": {k: {"count": len(v), "columns": [{"table": c.get("table_name"), "column": c.get("column_name")} for c in v]} for k, v in ccpa_categories.items()},
                },
                "data_sources": {
                    "title": "Sources of Personal Information",
                    "sources": project_info.get("connections", []),
                    "description": "Data sources connected for test data management.",
                },
                "business_purpose": {
                    "title": "Business Purpose",
                    "purposes": ["Software quality assurance", "Test environment provisioning", "Development data management"],
                    "description": "Personal information is processed solely for creating masked/synthetic test data.",
                },
                "opt_out": {
                    "title": "Right to Opt-Out",
                    "description": "DataWrangler does not sell personal information. Data is masked or replaced with synthetic alternatives.",
                    "sale_sharing": "No personal information is sold or shared with third parties.",
                },
            },
            "summary": {"total_pii_columns": total_pii, "coverage_percentage": coverage, "ccpa_categories": len(ccpa_categories)},
        }
