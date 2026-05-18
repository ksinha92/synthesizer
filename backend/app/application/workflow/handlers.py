"""Workflow handlers."""

from __future__ import annotations

import uuid

import structlog

from app.domain.shared.errors import NotFoundError
from app.domain.workflow.entities import Workflow
from app.domain.workflow.services import WorkflowValidator

from app.application.workflow.commands import CreateWorkflowCommand, ExecuteWorkflowCommand

logger = structlog.get_logger()


class CreateWorkflowHandler:
    def __init__(self, repo):
        self._repo = repo

    async def handle(self, cmd: CreateWorkflowCommand) -> Workflow:
        dag = cmd.dag_definition or {"nodes": [], "edges": []}
        errors = WorkflowValidator.validate_dag(dag)
        if errors:
            raise ValueError(f"Invalid DAG: {'; '.join(errors)}")

        wf = Workflow(
            project_id=cmd.project_id, name=cmd.name, description=cmd.description,
            dag_definition=dag,
        )
        saved = await self._repo.save(wf)
        await logger.ainfo("workflow_created", workflow_id=str(saved.id))
        return saved


class ExecuteWorkflowHandler:
    def __init__(self, repo, job_session):
        self._repo = repo
        self._session = job_session

    async def handle(self, cmd: ExecuteWorkflowCommand) -> uuid.UUID:
        wf = await self._repo.get(cmd.workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow {cmd.workflow_id} not found")

        # Concurrency limit: 1 active execution per workflow.
        #
        # Phase 59 F11: lock the row with FOR UPDATE so the read+insert below
        # is atomic against a concurrent request hitting the same workflow.
        # Without the lock, two requests can both observe "no active job"
        # before either inserts, producing two parallel runs. The matching
        # partial unique index (migration 026) is the backstop if the lock
        # is skipped (e.g. on SQLite for tests).
        from sqlalchemy import select
        from app.infrastructure.persistence.models.job import JobModel
        result = await self._session.execute(
            select(JobModel).where(
                JobModel.reference_id == cmd.workflow_id,
                JobModel.job_type == "workflow",
                JobModel.status.in_(["pending", "running"]),
            )
            .with_for_update()
        )
        if result.scalar_one_or_none():
            from fastapi import HTTPException
            raise HTTPException(409, {"error": "workflow_already_running", "detail": "Workflow already executing"})

        job = JobModel(
            project_id=cmd.project_id, job_type="workflow",
            reference_id=cmd.workflow_id, status="pending", created_by=cmd.user_id,
        )
        self._session.add(job)
        await self._session.flush()

        from app.infrastructure.messaging.workflow_tasks import run_workflow_task
        run_workflow_task.delay(str(cmd.workflow_id), str(cmd.project_id), str(job.id))

        await logger.ainfo("workflow_execution_triggered", workflow_id=str(cmd.workflow_id), job_id=str(job.id))
        return job.id
