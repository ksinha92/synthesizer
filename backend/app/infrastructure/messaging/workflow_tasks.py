"""Workflow Celery tasks — sequential node execution with polling."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import structlog

from app.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger()

NODE_POLL_INTERVAL = 5  # seconds
NODE_TIMEOUT = 1800  # 30 minutes per node
WORKFLOW_TIMEOUT = 7200  # 2 hours total


def compute_start_index(checkpoint: dict | None) -> int:
    """Return the loop index from which a workflow should resume.

    Pure helper extracted so the resume-math is unit-testable without
    standing up the async orchestrator. ``checkpoint`` is whatever the
    worker last wrote to ``JobModel.checkpoint`` — a dict like
    ``{"step": 2, "current_node": "<node-id>"}`` after the third node
    completed.

    Resume rules:
    - No checkpoint, or no ``current_node`` recorded → start at 0.
    - Recorded checkpoint of ``{"step": N, "current_node": ...}`` →
      start at ``N + 1`` (i.e. the node after the last completed one).
    - Malformed step (non-int) → fall back to 0.
    """
    if not checkpoint or not isinstance(checkpoint, dict):
        return 0
    if not checkpoint.get("current_node"):
        return 0
    try:
        last_step = int(checkpoint.get("step", -1))
    except (TypeError, ValueError):
        return 0
    return max(0, last_step + 1)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=120, acks_late=True)
def run_workflow_task(self, workflow_id: str, project_id: str, job_id: str):
    asyncio.run(_run_async(self, workflow_id, project_id, job_id))


async def _run_async(task, workflow_id, project_id, job_id):
    import uuid
    from sqlalchemy import select, update

    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.job import JobModel
    from app.infrastructure.persistence.models.workflow import WorkflowModel
    from app.infrastructure.messaging.progress_pubsub import publish_progress
    from app.domain.workflow.services import WorkflowValidator

    job_uuid = uuid.UUID(job_id)
    wf_uuid = uuid.UUID(workflow_id)
    workflow_start = time.monotonic()

    async with async_session_factory() as session:
        try:
            # Load the parent job up front so we can (1) stamp celery_task_id,
            # (2) read checkpoint for resume, and (3) inherit created_by onto
            # any child jobs spawned by node executors.
            parent_job = await session.get(JobModel, job_uuid)
            if parent_job is None:
                raise ValueError(f"Job {job_id} not found")

            # F9: stamp the Celery task id so cancel-by-Celery-ID works.
            if not parent_job.celery_task_id:
                parent_job.celery_task_id = task.request.id

            # Resume from last completed node if we crashed mid-run.
            start_index = compute_start_index(parent_job.checkpoint)

            await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(status="running", started_at=datetime.now(timezone.utc)))
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": parent_job.progress or 0,
                "result_summary": None,
            })

            # Load workflow
            result = await session.execute(select(WorkflowModel).where(WorkflowModel.id == wf_uuid))
            wf_model = result.scalar_one_or_none()
            if not wf_model:
                raise ValueError(f"Workflow {workflow_id} not found")

            dag = wf_model.dag_definition or {}
            errors = WorkflowValidator.validate_dag(dag)
            if errors:
                raise ValueError(f"Invalid DAG: {'; '.join(errors)}")

            order = WorkflowValidator.get_execution_order(dag)
            node_map = {n.get("id"): n for n in dag.get("nodes", [])}
            total_nodes = len(order)

            for i, node_id in enumerate(order):
                # Skip already-completed nodes when resuming from checkpoint.
                if i < start_index:
                    continue

                # Workflow timeout check
                if time.monotonic() - workflow_start > WORKFLOW_TIMEOUT:
                    raise TimeoutError(f"Workflow exceeded {WORKFLOW_TIMEOUT}s timeout")

                node = node_map.get(node_id, {})
                node_type = node.get("type", "unknown")

                await logger.ainfo("workflow_node_start", workflow_id=workflow_id, node_id=node_id, node_type=node_type, step=f"{i+1}/{total_nodes}")

                # Dispatch node operation based on type, bounded by NODE_TIMEOUT.
                node_config = node.get("data", node.get("config", {}))
                try:
                    await asyncio.wait_for(
                        _execute_node(
                            session,
                            node_type,
                            node_config,
                            project_id,
                            job_uuid,
                            parent_created_by=parent_job.created_by,
                        ),
                        timeout=NODE_TIMEOUT,
                    )
                except asyncio.TimeoutError as e:
                    raise RuntimeError(
                        f"Workflow node {node_id} ({node_type}) exceeded NODE_TIMEOUT={NODE_TIMEOUT}s"
                    ) from e

                # Update progress + checkpoint after each successful node.
                progress = int((i + 1) / total_nodes * 100)
                await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(progress=progress, checkpoint={"current_node": str(node_id), "step": i}))
                await session.commit()
                publish_progress(str(job_uuid), {
                    "status": "running",
                    "progress": progress,
                    "result_summary": None,
                })

            # Complete
            workflow_result_summary = {
                "nodes_executed": total_nodes,
                "duration_ms": round((time.monotonic() - workflow_start) * 1000),
            }
            await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(
                status="completed", progress=100, completed_at=datetime.now(timezone.utc),
                result_summary=workflow_result_summary,
            ))
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "completed",
                "progress": 100,
                "result_summary": workflow_result_summary,
            })

            await logger.ainfo("workflow_completed", workflow_id=workflow_id, job_id=job_id, nodes=total_nodes)

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.completed", {"job_id": job_id, "job_type": "workflow", "nodes_executed": total_nodes})

        except Exception as exc:
            await session.rollback()
            async with async_session_factory() as err_session:
                await err_session.execute(update(JobModel).where(JobModel.id == job_uuid).values(status="failed", error_message=str(exc)[:1000]))
                await err_session.commit()
            publish_progress(str(job_uuid), {
                "status": "failed",
                "progress": 0,
                "result_summary": None,
            })
            await logger.aerror("workflow_failed", workflow_id=workflow_id, error=str(exc))

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.failed", {"job_id": job_id, "job_type": "workflow", "error": str(exc)[:500]})

            raise task.retry(exc=exc)


async def _execute_node(
    session,
    node_type: str,
    node_config: dict,
    project_id: str,
    parent_job_uuid,
    *,
    parent_created_by,
) -> None:
    """Dispatch a workflow node to the appropriate engine/task.

    Unknown node types raise ``ValueError`` so a typo or removed type
    fails the workflow loudly rather than being silently skipped.
    ``parent_created_by`` is propagated onto every child JobModel so
    downstream RBAC / audit sees the correct actor.
    """
    import uuid

    from app.domain.workflow.services import canonicalize_node_type
    from app.infrastructure.persistence.models.job import JobModel

    # Accept legacy node-type names (discover/mask/generate/subset) for DAGs
    # saved before the rename to canonical executor branches.
    node_type = canonicalize_node_type(node_type)

    if node_type == "discovery":
        connection_id = node_config.get("connection_id")
        if not connection_id:
            raise ValueError("Discovery node requires connection_id")
        # Run discovery inline (reuse the async implementation)
        from app.infrastructure.messaging.discovery_tasks import _run_discovery_async

        child_job_id = str(uuid.uuid4())
        from app.infrastructure.persistence.database import async_session_factory
        async with async_session_factory() as child_session:
            child_job = JobModel(
                id=uuid.UUID(child_job_id), project_id=uuid.UUID(project_id),
                job_type="discovery", reference_id=uuid.UUID(connection_id),
                status="pending", created_by=parent_created_by,
            )
            child_session.add(child_job)
            await child_session.commit()

        # Use a placeholder task object for retries
        class _NoRetryTask:
            class request:
                retries = 0
                id = None
            @staticmethod
            def retry(exc):
                raise exc

        await _run_discovery_async(_NoRetryTask(), connection_id, project_id, child_job_id)

    elif node_type == "masking":
        policy_id = node_config.get("policy_id")
        connection_id = node_config.get("connection_id")
        if not policy_id or not connection_id:
            raise ValueError("Masking node requires policy_id and connection_id")

        from app.infrastructure.messaging.masking_tasks import _run_masking_async

        child_job_id = str(uuid.uuid4())
        from app.infrastructure.persistence.database import async_session_factory
        async with async_session_factory() as child_session:
            child_job = JobModel(
                id=uuid.UUID(child_job_id), project_id=uuid.UUID(project_id),
                job_type="masking", reference_id=uuid.UUID(policy_id),
                status="pending", created_by=parent_created_by,
            )
            child_session.add(child_job)
            await child_session.commit()

        class _NoRetryTask:
            class request:
                retries = 0
                id = None
            @staticmethod
            def retry(exc):
                raise exc

        await _run_masking_async(_NoRetryTask(), policy_id, connection_id, project_id, child_job_id)

    elif node_type == "synthetic":
        config_id = node_config.get("config_id")
        if not config_id:
            raise ValueError("Synthetic node requires config_id")

        from app.infrastructure.messaging.synthetic_tasks import _run_generation_async

        child_job_id = str(uuid.uuid4())
        from app.infrastructure.persistence.database import async_session_factory
        async with async_session_factory() as child_session:
            child_job = JobModel(
                id=uuid.UUID(child_job_id), project_id=uuid.UUID(project_id),
                job_type="generation", reference_id=uuid.UUID(config_id),
                status="pending", created_by=parent_created_by,
            )
            child_session.add(child_job)
            await child_session.commit()

        class _NoRetryTask:
            class request:
                retries = 0
                id = None
            @staticmethod
            def retry(exc):
                raise exc

        await _run_generation_async(_NoRetryTask(), config_id, project_id, child_job_id)

    elif node_type == "subsetting":
        config_id = node_config.get("config_id")
        if not config_id:
            raise ValueError("Subsetting node requires config_id")

        from app.infrastructure.messaging.subsetting_tasks import _run_async as _run_subsetting_async

        child_job_id = str(uuid.uuid4())
        from app.infrastructure.persistence.database import async_session_factory
        async with async_session_factory() as child_session:
            child_job = JobModel(
                id=uuid.UUID(child_job_id), project_id=uuid.UUID(project_id),
                job_type="subsetting", reference_id=uuid.UUID(config_id),
                status="pending", created_by=parent_created_by,
            )
            child_session.add(child_job)
            await child_session.commit()

        class _NoRetryTask:
            class request:
                retries = 0
                id = None
            @staticmethod
            def retry(exc):
                raise exc

        await _run_subsetting_async(_NoRetryTask(), config_id, project_id, child_job_id)

    else:
        # Phase 59 F11: fail fast on unknown node types instead of silent
        # skip. quality_check has been removed; legacy DAGs referencing it
        # will now surface a clear error on next execute.
        raise ValueError(
            f"Unknown workflow node type: {node_type!r} (parent_job={parent_job_uuid})"
        )
