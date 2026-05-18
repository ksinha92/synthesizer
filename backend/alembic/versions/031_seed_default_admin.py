"""Seed the default admin user — strictly opt-in.

Revision ID: 031
Revises: 030
Create Date: 2026-05-17

By default this migration is a **no-op**. Alembic migrations are the wrong
place to silently materialize credentials; they run unattended on every
``alembic upgrade head`` (CI, prod, fresh devs). Bundling a known-credential
admin into a schema migration risks planting a backdoor in any database that
isn't actively defending against it.

To seed the default admin you must opt in with **all three** environment
variables present at migration time:

* ``SEED_DEFAULT_ADMIN=1``  — single, explicit opt-in switch
* ``ADMIN_DEFAULT_EMAIL``   — the email to provision (no default)
* ``ADMIN_DEFAULT_PASSWORD`` — the plaintext seed (no default; bcrypt hashed before insert)

If any of those is missing, the migration prints a clear reason and exits
cleanly so the rest of the upgrade chain still applies.

Extra prod-safety check: even when opt-in is set, in ``ENVIRONMENT`` values
that are not in ``{development, test, dev, local}`` we refuse to seed if
``ADMIN_DEFAULT_PASSWORD`` equals the well-known repo sentinel
``"Admin@12345"`` — that means a CI pipeline that forgot to swap the value
won't fail open into a known-credential admin.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

from alembic import op
from passlib.context import CryptContext
from sqlalchemy import text

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# The well-known default that ships in the repo. NEVER used as a fallback —
# only compared against to refuse non-dev seeding.
_REPO_SENTINEL_PASSWORD = "Admin@12345"

# Environments where the repo sentinel password is tolerated (with opt-in).
_DEV_ENVIRONMENTS = {"development", "test", "dev", "local"}


def _skip(reason: str) -> None:
    """Skip the seed and surface the reason to stderr so it shows up in CI logs
    and alembic console output even when stdout is captured."""
    print(f"[alembic 031] {reason}", file=sys.stderr)


def upgrade() -> None:
    bind = op.get_bind()

    # Gate 1 — explicit opt-in must be on.
    opt_in = os.environ.get("SEED_DEFAULT_ADMIN", "").strip().lower()
    if opt_in not in {"1", "true", "yes"}:
        _skip(
            "SEED_DEFAULT_ADMIN is not set to 1 — skipping admin seed. "
            "Set SEED_DEFAULT_ADMIN=1 (with ADMIN_DEFAULT_EMAIL + "
            "ADMIN_DEFAULT_PASSWORD) to enable."
        )
        return

    # Gate 2 — credentials must be supplied explicitly. No fallbacks.
    email = (os.environ.get("ADMIN_DEFAULT_EMAIL") or "").strip()
    password = os.environ.get("ADMIN_DEFAULT_PASSWORD") or ""
    if not email or not password:
        _skip(
            "SEED_DEFAULT_ADMIN=1 was set, but ADMIN_DEFAULT_EMAIL and/or "
            "ADMIN_DEFAULT_PASSWORD are missing. Refusing to seed without "
            "explicit credentials."
        )
        return

    # Gate 3 — refuse the repo sentinel password outside dev environments.
    env = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    # Default-deny: if ENVIRONMENT is unset, treat as non-dev. Operators who
    # want the dev path must set ENVIRONMENT explicitly.
    is_dev_like = env in _DEV_ENVIRONMENTS
    if password == _REPO_SENTINEL_PASSWORD and not is_dev_like:
        _skip(
            f"Refusing to seed with the repo's well-known default password in "
            f"ENVIRONMENT={env!r}. Either set ADMIN_DEFAULT_PASSWORD to a strong "
            "unique value, or set ENVIRONMENT to 'development' / 'test' / "
            "'dev' / 'local' if this is genuinely a developer environment."
        )
        return

    full_name = (
        os.environ.get("ADMIN_DEFAULT_FULL_NAME", "").strip() or "Default Admin"
    )

    # Idempotency: only skip when THIS specific seed email already exists.
    # An earlier idempotency check on "any row with role='admin'" was wrong —
    # a pre-existing ad-hoc admin (e.g. the dev-bypass synthetic row) would
    # cause the real seed to never be inserted, locking new dev environments
    # out of the documented default credentials.
    existing = bind.execute(
        text("SELECT 1 FROM users WHERE LOWER(email) = LOWER(:email)"),
        {"email": email},
    ).scalar_one_or_none()
    if existing is not None:
        _skip(f"User {email!r} already exists — skipping seed (no overwrite).")
        return

    bind.execute(
        text(
            """
            INSERT INTO users (
                id, email, full_name, role,
                password_hash, force_password_change,
                is_active, token_version, created_at, updated_at
            ) VALUES (
                :id, :email, :full_name, 'admin',
                :password_hash, TRUE,
                TRUE, 0, :now, :now
            )
            """
        ),
        {
            "id": uuid.uuid4(),
            "email": email,
            "full_name": full_name,
            "password_hash": _pwd_ctx.hash(password),
            "now": datetime.now(timezone.utc),
        },
    )


def downgrade() -> None:
    """Intentionally a no-op.

    A previous version of this migration tried to remove the seeded admin by
    matching ``ADMIN_DEFAULT_EMAIL`` on a local-only row. Codex flagged that
    as a stop-ship hazard, correctly: the migration has no reliable way to
    tell whether the row at that email was inserted by *this* migration or
    later by a legitimate admin (via the admin API, password rotation, etc.).
    Running ``alembic downgrade`` would then delete real user data.

    Seed migrations should never destroy rows on rollback. Operators who
    truly want to remove the seeded admin can run a targeted ``DELETE``
    themselves with the full context of which rows are safe to drop.
    """
    _skip(
        "downgrade is a no-op — a seed migration must not delete user rows "
        "on rollback because it cannot distinguish its own seed from later "
        "operator-provisioned accounts at the same email."
    )
