"""Celery application and shared task utilities."""

from __future__ import annotations

import asyncio
import uuid as _uuid
from datetime import datetime, timezone

from celery import Celery
from celery.signals import task_failure, task_success

from app.config import settings

celery_app = Celery(
    "datawrangler",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    include=[
        "app.infrastructure.messaging.discovery_tasks",
        "app.infrastructure.messaging.masking_tasks",
        "app.infrastructure.messaging.subsetting_tasks",
        "app.infrastructure.messaging.synthetic_tasks",
        "app.infrastructure.messaging.workflow_tasks",
        "app.infrastructure.messaging.compliance_tasks",
        "app.infrastructure.messaging.ephemeral_tasks",
    ],
)


@task_failure.connect
def _handle_task_failure_to_dlq(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    einfo=None,
    **_,
):
    """Insert a ``DeadLetterJobModel`` row when a Celery task exhausts its retries.

    Celery fires ``task_failure`` on every terminal failure of the task, which
    includes intermediate ``Retry`` attempts. We only want to dead-letter
    a job once the task is truly out of retries, so we gate on
    ``request.retries >= max_retries`` (with ``max_retries`` falling back to 0
    for tasks that do not declare it).

    The handler is intentionally defensive: any failure inside the handler is
    swallowed because letting it raise would mask the original task exception
    and could destabilise the worker. Best-effort, fire-and-forget.
    """
    if not sender:
        return
    request = getattr(sender, "request", None)
    max_retries = getattr(sender, "max_retries", 0) or 0
    retries = getattr(request, "retries", 0) if request else 0
    if retries < max_retries:
        return  # not yet exhausted; let autoretry continue

    # Locate the job_id. Prefer the kwarg; fall back to introspecting the task's
    # function signature so we pick the *correct* positional slot. Several of our
    # tasks (masking, discovery, synthetic, subsetting, workflow) take other
    # UUIDs positionally before job_id — naively trusting args[0] silently
    # inserts the wrong original_job_id (e.g. policy_id for masking).
    kw = dict(kwargs or {})
    job_id_raw = kw.get("job_id")
    if not job_id_raw and args:
        try:
            import inspect

            run_fn = getattr(sender, "run", None)
            if run_fn is not None:
                sig = inspect.signature(run_fn)
                params = [
                    name for name in sig.parameters.keys() if name != "self"
                ]
                if "job_id" in params:
                    idx = params.index("job_id")
                    if idx < len(args):
                        candidate = args[idx]
                        # Sanity-check it parses as a UUID — guards against
                        # tasks whose first positional arg happens to be at
                        # the same index but isn't actually a job UUID.
                        _uuid.UUID(str(candidate))
                        job_id_raw = candidate
        except (ValueError, TypeError, AttributeError):
            pass
    if not job_id_raw:
        return

    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from app.infrastructure.persistence.database import get_sync_session
        from app.infrastructure.persistence.models.job import DeadLetterJobModel
    except ImportError:
        return  # database helpers not available; skip silently

    exception_msg = str(exception)[:1024] if exception else None
    try:
        with get_sync_session() as s:
            stmt = (
                pg_insert(DeadLetterJobModel)
                .values(
                    id=_uuid.uuid4(),
                    original_job_id=_uuid.UUID(str(job_id_raw)),
                    job_type=sender.name.split(".")[-1] if sender.name else "unknown",
                    payload={
                        "args": [str(a) for a in (args or [])],
                        "kwargs": {k: str(v) for k, v in kw.items()},
                        "exception": exception_msg,
                    },
                    error_message=exception_msg,
                    retry_count=retries,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["original_job_id"])
            )
            s.execute(stmt)
            s.commit()
    except Exception:
        # Don't let DLQ insertion failure mask the original task failure or
        # crash the Celery worker. This is observability, not correctness.
        pass


async def fire_webhooks(project_id: str, event_type: str, payload: dict) -> None:
    """Load project webhooks from DB and dispatch event. Non-blocking, safe to call from any task."""
    import uuid
    import structlog

    from sqlalchemy import select
    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.webhook import WebhookModel
    from app.infrastructure.webhooks.dispatcher import WebhookDispatcher

    logger = structlog.get_logger()

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(WebhookModel).where(
                    WebhookModel.project_id == uuid.UUID(project_id),
                    WebhookModel.is_active == True,
                )
            )
            models = result.scalars().all()
            if not models:
                return

            webhooks = [
                {
                    "id": str(m.id),
                    "url": m.url,
                    "events": m.events or [],
                    "secret_hash": m.secret_hash,
                    "secret_encrypted": m.secret_encrypted,
                    "legacy_signing": m.legacy_signing,
                    "is_active": m.is_active,
                }
                for m in models
            ]

        dispatcher = WebhookDispatcher()
        # Celery signal handlers call us via ``asyncio.run(...)``; without
        # ``wait_for_completion``, the loop is torn down right after dispatch
        # returns and the pending ``create_task`` deliveries are cancelled
        # before they POST or persist their delivery row.
        await dispatcher.dispatch(
            webhooks, event_type, payload, wait_for_completion=True
        )

    except Exception as e:
        await logger.awarning("webhook_fire_failed", project_id=project_id, event=event_type, error=str(e))


def _resolve_project_and_job_for_signal(sender, args, kwargs) -> tuple[str | None, str | None]:
    """Best-effort extract ``(project_id, job_id)`` from a Celery task signal.

    Mirrors the introspection done by the DLQ handler so we don't have to
    keep two parallel signature maps in sync. Returns ``(None, None)`` if
    we can't find them — caller silently skips firing.
    """
    kw = dict(kwargs or {})
    project_id = kw.get("project_id")
    job_id = kw.get("job_id")
    if project_id and job_id:
        return str(project_id), str(job_id)

    try:
        import inspect

        run_fn = getattr(sender, "run", None)
        if run_fn is not None and args:
            sig = inspect.signature(run_fn)
            params = [name for name in sig.parameters.keys() if name != "self"]
            if not project_id and "project_id" in params:
                idx = params.index("project_id")
                if idx < len(args):
                    project_id = args[idx]
            if not job_id and "job_id" in params:
                idx = params.index("job_id")
                if idx < len(args):
                    job_id = args[idx]
    except (ValueError, TypeError, AttributeError):
        pass

    if not project_id or not job_id:
        return None, None
    return str(project_id), str(job_id)


def _fire_webhook_event_sync(project_id: str, event_type: str, payload: dict) -> None:
    """Run :func:`fire_webhooks` from a synchronous Celery signal context.

    Celery signal handlers are plain functions, so we manage our own event
    loop. The handler is defensive — any error is swallowed because letting
    it raise would mask the original task's success/failure path.
    """
    try:
        asyncio.run(fire_webhooks(project_id, event_type, payload))
    except Exception:
        # Best-effort observability path.
        pass


@task_success.connect
def _fire_webhook_on_task_success(sender=None, result=None, **_):
    """Fire ``job.completed`` webhooks once a Celery task returns cleanly.

    Phase 60 F14. Replaces the old in-task ``asyncio.create_task`` path
    that dropped retries when the per-task event loop closed. Going
    through Celery's signal layer means the dispatch is enqueued *after*
    the task has resolved its DB writes, and the persistent delivery
    queue picks up the rest.
    """
    if not sender:
        return
    request = getattr(sender, "request", None)
    args = getattr(request, "args", None) if request else None
    kwargs = getattr(request, "kwargs", None) if request else None
    project_id, job_id = _resolve_project_and_job_for_signal(sender, args, kwargs)
    if not project_id or not job_id:
        return
    _fire_webhook_event_sync(
        project_id=project_id,
        event_type="job.completed",
        payload={"job_id": job_id, "result": result if isinstance(result, dict) else None},
    )


@task_failure.connect
def _fire_webhook_on_task_failure(sender=None, exception=None, args=None, kwargs=None, **_):
    """Fire ``job.failed`` webhooks on terminal task failure.

    Like the DLQ handler, we only fire once retries are exhausted so
    receivers don't see flapping failure events.
    """
    if not sender:
        return
    request = getattr(sender, "request", None)
    max_retries = getattr(sender, "max_retries", 0) or 0
    retries = getattr(request, "retries", 0) if request else 0
    if retries < max_retries:
        return

    project_id, job_id = _resolve_project_and_job_for_signal(sender, args, kwargs)
    if not project_id or not job_id:
        return
    _fire_webhook_event_sync(
        project_id=project_id,
        event_type="job.failed",
        payload={"job_id": job_id, "error": (str(exception)[:1024] if exception else None)},
    )


async def redrive_pending_webhook_deliveries(limit: int = 100) -> int:
    """Re-fire webhook deliveries left in ``pending`` or due ``failed`` state.

    Designed to be invoked from a periodic Celery beat task. Picks rows
    whose ``status='pending'`` (never resolved — usually worker died
    mid-dispatch) or ``status='failed' AND next_retry_at <= NOW()``, then
    re-runs the dispatcher against the parent webhook row.

    Returns the number of deliveries re-attempted. Errors are logged but
    not raised — this is a recovery path, not a critical correctness
    path.
    """
    import structlog

    from sqlalchemy import or_, select

    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.webhook import WebhookModel
    from app.infrastructure.persistence.models.webhook_delivery import (
        WebhookDeliveryModel,
    )
    from app.infrastructure.webhooks.dispatcher import WebhookDispatcher

    rd_logger = structlog.get_logger()
    redriven = 0

    try:
        async with async_session_factory() as session:
            now = datetime.now(timezone.utc)
            stmt = (
                select(WebhookDeliveryModel, WebhookModel)
                .join(WebhookModel, WebhookModel.id == WebhookDeliveryModel.webhook_id)
                .where(
                    or_(
                        WebhookDeliveryModel.status == "pending",
                        (WebhookDeliveryModel.status == "failed")
                        & (WebhookDeliveryModel.next_retry_at <= now),
                    )
                )
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()

        dispatcher = WebhookDispatcher()
        for delivery, webhook in rows:
            webhook_dict = {
                "id": str(webhook.id),
                "url": webhook.url,
                "events": webhook.events or [delivery.event_type],
                "secret_hash": webhook.secret_hash,
                "secret_encrypted": webhook.secret_encrypted,
                "legacy_signing": webhook.legacy_signing,
                "is_active": webhook.is_active,
            }
            # Use the same dispatch path so a fresh delivery row is opened
            # and the old one ages out — keeps the audit trail intact.
            # Redrive runs under ``asyncio.run(...)`` from a Celery context,
            # so wait_for_completion is required (see note in fire_webhooks).
            await dispatcher.dispatch(
                [webhook_dict],
                delivery.event_type,
                delivery.payload,
                wait_for_completion=True,
            )
            redriven += 1

    except Exception as e:
        await rd_logger.awarning("webhook_redrive_failed", error=str(e))

    return redriven
