"""Webhook CRUD + delivery-replay API.

Phase 60 F14. ``POST /projects/{project_id}/webhooks`` now stores the raw
secret Fernet-encrypted on the row so the dispatcher can recover it and
HMAC-sign with the receiver-verifiable key. The raw secret is returned in
the response *once* — exactly the same shape as the prior endpoint,
documented in the response payload itself so admins know to save it.

Two new admin endpoints back the delivery-replay UI:

* ``GET  /admin/webhook-deliveries`` — paginated list of past attempts.
* ``POST /admin/webhook-deliveries/{id}/retry`` — re-runs dispatch.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.rbac import require_admin
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.webhook import WebhookModel
from app.infrastructure.persistence.models.webhook_delivery import WebhookDeliveryModel
from app.infrastructure.security.encryption import encrypt_bytes
from app.infrastructure.webhooks.dispatcher import WebhookDispatcher

router = APIRouter(prefix="/projects/{project_id}/webhooks", tags=["webhooks"])
admin_router = APIRouter(prefix="/admin/webhook-deliveries", tags=["webhooks", "admin"])


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = ["job.completed", "job.failed"]


@router.post("", status_code=201)
async def create_webhook(
    project_id: uuid.UUID,
    body: WebhookCreate,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Register a webhook. The raw signing secret is returned ONCE — save it.

    Storage shape:

    * ``secret_hash`` — sha256 of the raw secret. Kept populated for the
      90-day deprecation window so the legacy dispatch path still works
      for rows created before F14 lands. New rows still write it so
      downstream tooling that indexes on it doesn't break.
    * ``secret_encrypted`` — Fernet-encrypted raw secret. The dispatcher
      decrypts this at send time and uses it as the HMAC key.
    * ``legacy_signing=False`` — opts new rows out of the deprecation
      header so receivers don't get false ``X-Webhook-Legacy-Signing``
      values.
    """
    secret = secrets.token_urlsafe(32)
    secret_hash = hashlib.sha256(secret.encode()).hexdigest()

    try:
        secret_encrypted = encrypt_bytes(secret.encode())
    except ValueError as e:
        # No FERNET_KEY configured — refuse to create a webhook we couldn't
        # later verify. Better to surface the misconfig than persist a
        # row that triggers a 90-day deprecation header on every fire.
        raise HTTPException(
            status_code=500,
            detail={"error": "fernet_key_missing", "message": str(e)},
        )

    model = WebhookModel(
        project_id=project_id,
        url=body.url,
        events=body.events,
        secret_hash=secret_hash,
        secret_encrypted=secret_encrypted,
        legacy_signing=False,
    )
    session.add(model)
    await session.flush()

    return {
        "id": str(model.id),
        "url": model.url,
        "events": model.events,
        "secret": secret,  # Shown ONCE — never returned again
        "note": "Save this secret — it will not be shown again.",
    }


@router.get("")
async def list_webhooks(
    project_id: uuid.UUID,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(WebhookModel).where(WebhookModel.project_id == project_id)
    )
    webhooks = result.scalars().all()
    return {
        "webhooks": [
            {
                "id": str(w.id),
                "url": w.url,
                "events": w.events,
                "is_active": w.is_active,
                "legacy_signing": w.legacy_signing,
                "created_at": w.created_at.isoformat() if w.created_at else "",
            }
            for w in webhooks
        ]
    }


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await session.execute(
        delete(WebhookModel).where(
            WebhookModel.id == webhook_id,
            WebhookModel.project_id == project_id,
        )
    )


# -- Admin delivery-replay endpoints ----------------------------------


@admin_router.get("")
async def list_webhook_deliveries(
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Paginated list of webhook delivery attempts. Admin-only.

    Filter by ``status`` (``pending`` | ``sent`` | ``failed``) when
    triaging. ``page_size`` is clamped to 200 to keep the UI snappy and
    to avoid loading a megabyte of payloads in one shot.
    """
    page_size = max(1, min(page_size, 200))
    offset = (max(1, page) - 1) * page_size

    stmt = select(WebhookDeliveryModel).order_by(desc(WebhookDeliveryModel.created_at))
    if status:
        stmt = stmt.where(WebhookDeliveryModel.status == status)
    stmt = stmt.limit(page_size).offset(offset)

    rows = (await session.execute(stmt)).scalars().all()
    return {
        "deliveries": [
            {
                "id": str(r.id),
                "webhook_id": str(r.webhook_id),
                "event_type": r.event_type,
                "status": r.status,
                "attempts": r.attempts,
                "last_error": r.last_error,
                "response_status": r.response_status,
                "next_retry_at": r.next_retry_at.isoformat() if r.next_retry_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            }
            for r in rows
        ],
        "page": page,
        "page_size": page_size,
    }


@admin_router.post("/{delivery_id}/retry")
async def retry_webhook_delivery(
    delivery_id: uuid.UUID,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Re-run dispatch for a specific delivery row.

    Loads the delivery + parent webhook, hands them to the dispatcher
    through the same code path used by ``fire_webhooks``. The original
    delivery row is marked ``pending`` again so the periodic redrive job
    doesn't double-fire it.
    """
    delivery = (
        await session.execute(
            select(WebhookDeliveryModel).where(WebhookDeliveryModel.id == delivery_id)
        )
    ).scalar_one_or_none()
    if delivery is None:
        raise HTTPException(status_code=404, detail={"error": "delivery_not_found"})

    webhook = (
        await session.execute(
            select(WebhookModel).where(WebhookModel.id == delivery.webhook_id)
        )
    ).scalar_one_or_none()
    if webhook is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "webhook_not_found", "delivery_id": str(delivery_id)},
        )

    # Reset retry bookkeeping. A retry that fails again will overwrite
    # these values via the dispatcher's normal failure path.
    delivery.status = "pending"
    delivery.next_retry_at = None
    delivery.last_error = None
    delivery.sent_at = None
    delivery.attempts = 0
    delivery.created_at = datetime.now(timezone.utc)
    await session.flush()

    dispatcher = WebhookDispatcher()
    await dispatcher.dispatch(
        [
            {
                "id": str(webhook.id),
                "url": webhook.url,
                "events": webhook.events or [delivery.event_type],
                "secret_hash": webhook.secret_hash,
                "secret_encrypted": webhook.secret_encrypted,
                "legacy_signing": webhook.legacy_signing,
                "is_active": webhook.is_active,
            }
        ],
        delivery.event_type,
        delivery.payload,
        # Reuse THIS delivery row so the admin sees the retry outcome on the
        # row they clicked; otherwise dispatch opens a fresh row and the
        # original stays "pending" forever (sweep would also re-pick it up).
        existing_delivery_id=delivery.id,
    )

    return {"status": "queued", "delivery_id": str(delivery_id)}
