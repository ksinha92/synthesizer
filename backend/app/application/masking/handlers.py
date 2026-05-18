"""Masking handlers."""

from __future__ import annotations

import uuid

import structlog

from app.domain.masking.entities import MaskingPolicy, MaskingRule
from app.domain.masking.repository import MaskingRepository
from app.domain.masking.value_objects import MaskingStrategy
from app.domain.discovery.value_objects import PIIType

from app.application.masking.commands import (
    AddRuleCommand, AutoSuggestRulesCommand, CreatePolicyCommand,
    ExecuteMaskingCommand, PreviewMaskingCommand,
)

logger = structlog.get_logger()

# PIIType → suggested masking strategy (cardinality-aware)
PII_STRATEGY_MAP = {
    PIIType.EMAIL: MaskingStrategy.FAKER_REPLACE,
    PIIType.SSN: MaskingStrategy.REDACT,
    PIIType.PHONE: MaskingStrategy.PARTIAL_MASK,
    PIIType.PERSON_NAME: MaskingStrategy.FAKER_REPLACE,
    PIIType.ADDRESS: MaskingStrategy.FAKER_REPLACE,
    PIIType.CREDIT_CARD: MaskingStrategy.REDACT,
    PIIType.IP_ADDRESS: MaskingStrategy.HASH,
    PIIType.DATE_OF_BIRTH: MaskingStrategy.NULLIFY,
    PIIType.MEDICAL_RECORD: MaskingStrategy.REDACT,
    PIIType.FINANCIAL_ACCOUNT: MaskingStrategy.HASH,
}

# Stronger strategies for low-cardinality columns
LOW_CARDINALITY_UPGRADE = {
    MaskingStrategy.PARTIAL_MASK: MaskingStrategy.REDACT,
    MaskingStrategy.SHUFFLE: MaskingStrategy.HASH,
}


class CreatePolicyHandler:
    def __init__(self, repo: MaskingRepository):
        self._repo = repo

    async def handle(self, cmd: CreatePolicyCommand) -> MaskingPolicy:
        policy = MaskingPolicy(project_id=cmd.project_id, name=cmd.name, description=cmd.description, is_default=cmd.is_default)
        saved = await self._repo.save(policy)
        await logger.ainfo("masking_policy_created", policy_id=str(saved.id))
        return saved


class AddRuleHandler:
    def __init__(self, repo: MaskingRepository):
        self._repo = repo

    async def handle(self, cmd: AddRuleCommand) -> MaskingRule:
        rule = MaskingRule(
            policy_id=cmd.policy_id, column_id=cmd.column_id, match_pattern=cmd.match_pattern,
            masking_type=MaskingStrategy(cmd.masking_type), masking_config=cmd.masking_config,
            preserve_format=cmd.preserve_format, deterministic=cmd.deterministic,
            linked_column_ids=list(cmd.linked_column_ids or []),
            consistency_group=cmd.consistency_group,
        )
        return await self._repo.add_rule(rule)


class PreviewHandler:
    def __init__(self, repo: MaskingRepository):
        self._repo = repo

    async def handle(self, cmd: PreviewMaskingCommand) -> list[dict]:
        rules = await self._repo.get_rules_by_policy(cmd.policy_id)
        from app.infrastructure.engine.masking_engine import MaskingEngine
        engine = MaskingEngine(salt="preview-salt")

        # Build rule dicts for preview
        rule_dicts = [
            {"column_name": str(r.column_id), "masking_type": r.masking_type.value, "masking_config": r.masking_config}
            for r in rules
        ]
        # Placeholder sample data — real implementation reads from connector
        return engine.mask_preview([], rule_dicts, limit=5)


class ExecuteHandler:
    def __init__(self, repo: MaskingRepository, job_session):
        self._repo = repo
        self._session = job_session

    async def handle(self, cmd: ExecuteMaskingCommand) -> uuid.UUID:
        from app.infrastructure.persistence.models.job import JobModel
        job = JobModel(project_id=cmd.project_id, job_type="masking", reference_id=cmd.policy_id, status="pending", created_by=cmd.user_id)
        self._session.add(job)
        await self._session.flush()

        from app.infrastructure.messaging.masking_tasks import run_masking_task
        run_masking_task.delay(str(cmd.policy_id), str(cmd.connection_id), str(cmd.project_id), str(job.id))

        await logger.ainfo("masking_execution_triggered", policy_id=str(cmd.policy_id), job_id=str(job.id))
        return job.id


class AutoSuggestHandler:
    def __init__(self, discovery_repo):
        self._discovery_repo = discovery_repo

    async def handle(self, cmd: AutoSuggestRulesCommand) -> list[dict]:
        pii_columns = await self._discovery_repo.get_pii_columns(cmd.schema_id, min_confidence=0.4)
        suggestions = []

        for col in pii_columns:
            strategy = PII_STRATEGY_MAP.get(col.pii_type, MaskingStrategy.REDACT)

            # Cardinality-aware upgrade
            cardinality = col.stats.get("cardinality", 100) if col.stats else 100
            warning = None
            if cardinality < 10 and strategy in LOW_CARDINALITY_UPGRADE:
                original = strategy
                strategy = LOW_CARDINALITY_UPGRADE[strategy]
                warning = f"Upgraded from {original.value} to {strategy.value} due to low cardinality ({cardinality} unique values)"

            suggestions.append({
                "column_id": str(col.id),
                "column_name": col.column_name,
                "pii_type": col.pii_type.value,
                "suggested_strategy": strategy.value,
                "confidence": col.pii_confidence.score,
                "cardinality": cardinality,
                "warning": warning,
            })

        return suggestions
