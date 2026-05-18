"""Webhook dispatcher — fires HTTP POST on job events.

Phase 60 F14 rewrite. Two behaviour changes vs the pre-v0.9 version:

1. **HMAC keyed on the raw secret** (decrypted from the Fernet-encrypted
   ``secret_encrypted`` column). Previously the dispatcher signed with
   ``secret_hash``, which is ``sha256(raw_secret)`` — receivers possessing
   the raw secret returned at webhook creation could never reproduce the
   signature. The new signing string is ``f"{ts}.{body}"`` and the header
   set is ``X-Webhook-Signature: sha256=<hex>`` plus
   ``X-Webhook-Timestamp: <unix ts>``.

2. **Persistent delivery queue.** Each dispatch writes a
   ``WebhookDeliveryModel`` row before the first POST. The dispatcher
   updates ``status`` / ``last_error`` as attempts complete so a periodic
   redrive job can resume work after worker restarts (the previous
   asyncio-task approach dropped retries when the Celery per-task event
   loop closed).

A 90-day deprecation window keeps the old ``secret_hash`` signing path
alive for webhooks whose row still has ``legacy_signing=True`` and no
``secret_encrypted``. Those deliveries get an extra
``X-Webhook-Legacy-Signing: true`` header so receivers can switch on
adoption rather than break instantly.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from app.infrastructure.security.encryption import decrypt_bytes

logger = structlog.get_logger()

RETRY_DELAYS = [5, 15, 60]  # seconds — final element of dispatch loop is a no-sleep terminal pass


@dataclass
class _SigningMaterial:
    """Minimal shape ``_sign`` needs from either a dict or a ``WebhookModel``."""

    secret_encrypted: bytes | None
    secret_hash: str | None
    legacy_signing: bool


def _as_signing_material(webhook: Any) -> _SigningMaterial:
    """Normalise dict / ORM row inputs so callers don't have to care.

    ``fire_webhooks`` historically passed plain dicts assembled from
    ``WebhookModel`` rows; the new persistent path also calls in with the
    ORM instance directly. Accept both.
    """
    if isinstance(webhook, dict):
        return _SigningMaterial(
            secret_encrypted=webhook.get("secret_encrypted"),
            secret_hash=webhook.get("secret_hash"),
            legacy_signing=bool(webhook.get("legacy_signing", True)),
        )
    return _SigningMaterial(
        secret_encrypted=getattr(webhook, "secret_encrypted", None),
        secret_hash=getattr(webhook, "secret_hash", None),
        legacy_signing=bool(getattr(webhook, "legacy_signing", True)),
    )


def _sign(webhook: Any, event_type: str, payload: dict) -> tuple[dict[str, str], bytes]:
    """Return ``(headers, body_bytes)`` ready to POST.

    Two signing paths:

    * **Raw secret (preferred)** — used whenever ``secret_encrypted`` is
      populated. The signing string is ``f"{ts}.{body}"`` keyed with the
      decrypted raw secret. Receivers compute the same and compare with
      ``hmac.compare_digest``.

    * **Legacy** — only when ``secret_encrypted`` is absent and
      ``legacy_signing`` is true. Signs the raw body with ``secret_hash``
      as the HMAC key (the original buggy behaviour we're keeping alive
      during the 90-day deprecation window) and emits
      ``X-Webhook-Legacy-Signing: true``.

    Raises ``ValueError`` if neither signing path is available — a webhook
    with no signing material at all should never have been persisted.
    """
    mat = _as_signing_material(webhook)
    ts = str(int(time.time()))
    body = json.dumps({"event": event_type, "data": payload}, default=str).encode()

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event_type,
        "X-Webhook-Timestamp": ts,
    }

    if mat.secret_encrypted:
        secret = decrypt_bytes(mat.secret_encrypted)
        signing_string = f"{ts}.".encode() + body
        sig = hmac.new(secret, signing_string, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={sig}"
        return headers, body

    if mat.secret_hash and mat.legacy_signing:
        sig = hmac.new(mat.secret_hash.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={sig}"
        headers["X-Webhook-Legacy-Signing"] = "true"
        return headers, body

    raise ValueError("webhook has no signing material")


class WebhookDispatcher:
    """Dispatches webhook notifications for job events."""

    async def dispatch(
        self,
        webhooks: list[dict],
        event_type: str,
        payload: dict,
        existing_delivery_id: uuid.UUID | None = None,
        wait_for_completion: bool = False,
    ) -> None:
        """Fire webhooks matching event_type.

        - ``existing_delivery_id`` (admin retry path) → reuse that row
          instead of opening a fresh ``WebhookDeliveryModel`` so the retry UI
          reflects the actual outcome on the row the admin clicked.
        - ``wait_for_completion`` (Celery-signal path) → ``await`` every
          delivery before returning. Required when the caller wraps us in
          ``asyncio.run(...)`` (Celery ``task_success``/``task_failure``
          signals do this); without it, the event loop tears down right
          after dispatch returns and the in-flight ``create_task`` deliveries
          get cancelled before they POST or update ``webhook_deliveries``.
          FastAPI callers leave this False so the HTTP response isn't held
          for the full 80 s retry window.
        """
        tasks: list[asyncio.Task] = []
        for webhook in webhooks:
            if event_type in webhook.get("events", []) and webhook.get("is_active", True):
                tasks.append(
                    asyncio.create_task(
                        self._deliver(
                            webhook,
                            event_type,
                            payload,
                            existing_delivery_id=existing_delivery_id,
                        )
                    )
                )
        if wait_for_completion and tasks:
            # ``return_exceptions=True`` so one webhook failing doesn't strand the rest.
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _deliver(
        self,
        webhook: dict,
        event_type: str,
        payload: dict,
        existing_delivery_id: uuid.UUID | None = None,
    ) -> None:
        url = webhook["url"]
        webhook_id = webhook.get("id")

        try:
            headers, body = _sign(webhook, event_type, payload)
        except ValueError as e:
            await logger.aerror(
                "webhook_no_signing_material",
                url=url,
                event_type=event_type,
                error=str(e),
            )
            return

        # Best-effort persist a delivery row so admins can replay later.
        # Retry path passes through ``existing_delivery_id`` so the row that
        # the admin reset is the same one that captures the final result.
        if existing_delivery_id is not None:
            delivery_id: uuid.UUID | None = existing_delivery_id
        else:
            delivery_id = await self._open_delivery_row(
                webhook_id=webhook_id,
                event_type=event_type,
                payload=payload,
            )

        last_error: str | None = None
        last_status: int | None = None
        attempts_made = 0

        for attempt, delay in enumerate(RETRY_DELAYS + [0], 1):
            attempts_made = attempt
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, content=body, headers=headers)
                    last_status = resp.status_code
                    resp.raise_for_status()

                await logger.ainfo(
                    "webhook_delivered",
                    url=url,
                    event_type=event_type,
                    status=resp.status_code,
                    attempt=attempt,
                )
                await self._mark_delivery_sent(
                    delivery_id=delivery_id,
                    attempts=attempts_made,
                    response_status=resp.status_code,
                )
                return

            except Exception as e:  # httpx errors + HTTPStatusError
                last_error = str(e)[:1024]
                await logger.awarning(
                    "webhook_delivery_failed",
                    url=url,
                    event_type=event_type,
                    attempt=attempt,
                    error=last_error,
                )
                if delay > 0:
                    await asyncio.sleep(delay)

        await logger.aerror(
            "webhook_delivery_exhausted",
            url=url,
            event_type=event_type,
            attempts=attempts_made,
        )
        await self._mark_delivery_failed(
            delivery_id=delivery_id,
            attempts=attempts_made,
            response_status=last_status,
            last_error=last_error,
        )

    # -- delivery persistence helpers ---------------------------------

    async def _open_delivery_row(
        self,
        webhook_id: Any,
        event_type: str,
        payload: dict,
    ) -> uuid.UUID | None:
        """Insert a ``pending`` row. Returns its id, or ``None`` if persistence is unavailable.

        The whole path is best-effort: a database hiccup must not stop the
        webhook firing. We swallow everything and just lose the audit trail
        for that attempt.
        """
        if not webhook_id:
            return None
        try:
            from app.infrastructure.persistence.database import async_session_factory
            from app.infrastructure.persistence.models.webhook_delivery import (
                WebhookDeliveryModel,
            )
        except ImportError:
            return None

        delivery_id = uuid.uuid4()
        try:
            async with async_session_factory() as session:
                session.add(
                    WebhookDeliveryModel(
                        id=delivery_id,
                        webhook_id=uuid.UUID(str(webhook_id)),
                        event_type=event_type,
                        payload=payload,
                        attempts=0,
                        status="pending",
                    )
                )
                await session.commit()
            return delivery_id
        except Exception as e:  # observability path — never crash on logging
            await logger.awarning("webhook_delivery_persist_failed", error=str(e))
            return None

    async def _mark_delivery_sent(
        self,
        delivery_id: uuid.UUID | None,
        attempts: int,
        response_status: int,
    ) -> None:
        if not delivery_id:
            return
        try:
            from sqlalchemy import update

            from app.infrastructure.persistence.database import async_session_factory
            from app.infrastructure.persistence.models.webhook_delivery import (
                WebhookDeliveryModel,
            )

            async with async_session_factory() as session:
                await session.execute(
                    update(WebhookDeliveryModel)
                    .where(WebhookDeliveryModel.id == delivery_id)
                    .values(
                        status="sent",
                        attempts=attempts,
                        response_status=response_status,
                        sent_at=datetime.now(timezone.utc),
                        last_error=None,
                    )
                )
                await session.commit()
        except Exception as e:
            await logger.awarning("webhook_delivery_mark_sent_failed", error=str(e))

    async def _mark_delivery_failed(
        self,
        delivery_id: uuid.UUID | None,
        attempts: int,
        response_status: int | None,
        last_error: str | None,
    ) -> None:
        if not delivery_id:
            return
        try:
            from sqlalchemy import update

            from app.infrastructure.persistence.database import async_session_factory
            from app.infrastructure.persistence.models.webhook_delivery import (
                WebhookDeliveryModel,
            )

            async with async_session_factory() as session:
                await session.execute(
                    update(WebhookDeliveryModel)
                    .where(WebhookDeliveryModel.id == delivery_id)
                    .values(
                        status="failed",
                        attempts=attempts,
                        response_status=response_status,
                        last_error=last_error,
                        # Backstop: redrive job picks rows whose next_retry_at
                        # has elapsed. One hour is conservative — admins can
                        # force an earlier retry via the admin endpoint.
                        next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    )
                )
                await session.commit()
        except Exception as e:
            await logger.awarning("webhook_delivery_mark_failed_failed", error=str(e))
