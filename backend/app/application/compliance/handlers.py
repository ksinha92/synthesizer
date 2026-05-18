"""Compliance handlers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog

from app.domain.compliance.entities import ComplianceReport
from app.infrastructure.compliance.hipaa_reporter import HIPAAReporter
from app.infrastructure.compliance.gdpr_reporter import GDPRReporter
from app.infrastructure.compliance.ccpa_reporter import CCPAReporter
from app.infrastructure.compliance.pdf_generator import generate_pdf

from app.application.compliance.commands import GenerateReportCommand

logger = structlog.get_logger()

REPORTERS = {
    "hipaa": HIPAAReporter,
    "gdpr": GDPRReporter,
    "ccpa": CCPAReporter,
}


class GenerateReportHandler:
    """Aggregates discovery + masking + connection state into a regulation report.

    Phase 57 F1: previously the handler shipped empty lists into every reporter,
    so the resulting HIPAA/GDPR/CCPA PDFs had no findings. The handler now
    queries all three repositories and flattens their state into the
    ``pii_columns`` / ``masking_rules`` / ``project_info`` payload that
    reporters expect.

    DDD note: this is orchestration only — all SQL stays in the repositories.
    """

    def __init__(self, compliance_repo, discovery_repo, masking_repo, storage, connection_repo=None):
        self._compliance_repo = compliance_repo
        self._discovery_repo = discovery_repo
        self._masking_repo = masking_repo
        self._storage = storage
        self._connection_repo = connection_repo

    async def handle(self, cmd: GenerateReportCommand) -> ComplianceReport:
        reporter_cls = REPORTERS.get(cmd.regulation)
        if not reporter_cls:
            raise ValueError(f"Unknown regulation: {cmd.regulation}")

        # 1. Connections for the project. Stay defensive — older callers may
        # not pass a connection_repo yet (e.g. unit tests of the reporter
        # layer); fall back to an empty list rather than blowing up.
        connections: list = []
        if self._connection_repo is not None:
            connections = await self._connection_repo.find_by_project_id(cmd.project_id)

        project_info = {
            "project_id": str(cmd.project_id),
            "connections": [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "type": c.connector_type.value if hasattr(c.connector_type, "value") else str(c.connector_type),
                }
                for c in connections
            ],
        }

        # 2. Flatten PII columns across every connection → schema → column.
        # DiscoveredColumn carries table_id (not table_name); resolve table
        # names per-schema via get_tables_by_schema_id().
        pii_columns: list[dict] = []
        if self._discovery_repo is not None:
            for c in connections:
                schemas = await self._discovery_repo.find_by_connection_id(c.id)
                for schema in schemas:
                    tables = await self._discovery_repo.get_tables_by_schema_id(schema.id)
                    table_lookup = {t.id: t.table_name for t in tables}

                    cols = await self._discovery_repo.get_pii_columns(schema.id)
                    for col in cols:
                        pii_type_val = (
                            col.pii_type.value
                            if hasattr(col.pii_type, "value")
                            else str(col.pii_type)
                        )
                        confidence_val = (
                            col.pii_confidence.score
                            if hasattr(col, "pii_confidence") and col.pii_confidence is not None
                            else 0.0
                        )
                        pii_columns.append(
                            {
                                "connection": c.name,
                                "schema": schema.schema_name,
                                "table": table_lookup.get(col.table_id, ""),
                                "table_name": table_lookup.get(col.table_id, ""),
                                "column": col.column_name,
                                "column_name": col.column_name,
                                "pii_type": pii_type_val,
                                "confidence": confidence_val,
                            }
                        )

        # 3. Flatten masking rules across every policy.
        masking_rules: list[dict] = []
        if self._masking_repo is not None:
            policies = await self._masking_repo.find_by_project_id(cmd.project_id)
            for p in policies:
                rules = await self._masking_repo.get_rules_by_policy(p.id)
                for r in rules:
                    strategy_val = (
                        r.masking_type.value
                        if hasattr(r.masking_type, "value")
                        else str(r.masking_type)
                    )
                    masking_rules.append(
                        {
                            "policy": p.name,
                            "policy_name": p.name,
                            "column_id": str(r.column_id) if r.column_id else None,
                            "strategy": strategy_val,
                            "masking_type": strategy_val,
                            "enabled": True,
                        }
                    )

        # 4. Generate report content + PDF
        reporter = reporter_cls()
        report_data = reporter.generate(pii_columns, masking_rules, project_info)
        pdf_bytes = generate_pdf(report_data, cmd.regulation.upper())

        # 5. Persist artifacts to the storage backend
        report_id = uuid.uuid4()
        storage_prefix = f"compliance/{cmd.project_id}/{report_id}"
        json_path = f"{storage_prefix}/report.json"
        pdf_path = f"{storage_prefix}/report.pdf"

        if self._storage:
            await self._storage.save(json_path, json.dumps(report_data, default=str).encode())
            await self._storage.save(pdf_path, pdf_bytes)

        # 6. Save the report-row summary
        report = ComplianceReport(
            id=report_id,
            project_id=cmd.project_id,
            report_type=cmd.regulation,
            generated_at=datetime.now(timezone.utc),
            summary=report_data.get("summary", {}),
            storage_path=pdf_path,
            created_by=cmd.user_id,
        )
        saved = await self._compliance_repo.save(report)

        await logger.ainfo(
            "compliance_report_generated",
            report_id=str(report_id),
            regulation=cmd.regulation,
            project_id=str(cmd.project_id),
            pii_columns=len(pii_columns),
            masking_rules=len(masking_rules),
            connections=len(connections),
        )
        return saved
