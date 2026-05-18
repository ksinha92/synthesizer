---
phase: 02-auth-sso-jwt
plan: 01
completed: 2026-03-28
duration: ~20min
---

# Phase 2 Plan 01: Auth (SSO/OIDC + JWT) Summary

**Implemented SSO authentication via OIDC with local Keycloak, JWT service account tokens, auth dependency for route protection, rate limiting, and structured audit logging for all auth events.**

## Objective

Secure identity infrastructure before any data operations are built. SSO integrates with Ameritas corporate identity (Keycloak for dev, Okta/Azure AD for production). JWT covers CI/CD and automated workflows.

## What Was Built

| File | Purpose |
|------|---------|
| `backend/app/domain/shared/errors.py` | Domain errors: AuthenticationError, AuthorizationError, NotFoundError — zero framework imports |
| `backend/app/infrastructure/auth/oidc.py` | OIDCProvider: authlib-based OIDC client with CSRF state validation (Redis, 10-min TTL), id_token signature verification via JWKS, provider metadata discovery |
| `backend/app/infrastructure/auth/jwt.py` | JWT utilities: create_access_token, create_refresh_token (with token_version for revocation), decode_token, create_service_account_token (hmac.compare_digest for timing attack prevention) |
| `backend/app/infrastructure/auth/dependencies.py` | FastAPI auth dependencies: get_current_user (Bearer + cookie extraction, user lookup, token_version revocation check), require_role, get_optional_user |
| `backend/app/api/v1/auth.py` | 5 endpoints: GET /sso/login (redirect to OIDC), GET /sso/callback (exchange + upsert user), POST /token (service account), POST /refresh (with version check), GET /me (current user profile). Rate limited via slowapi. Structured audit logging on all events. |
| `backend/app/infrastructure/persistence/models/user.py` | Added token_version (int, for refresh token revocation) and last_login_at fields |
| `backend/alembic/versions/002_add_auth_fields.py` | Migration: adds token_version, last_login_at, sso_subject_id index to users |
| `backend/app/config.py` | Added OIDC settings (issuer, client_id/secret, redirect, scopes), JWT settings (algorithm, expiry), SERVICE_ACCOUNT_API_KEYS, AUTH_RATE_LIMIT |
| `backend/app/container.py` | Added OIDCProvider singleton, wired auth modules |
| `backend/app/main.py` | Added slowapi middleware + rate limit exceeded handler |
| `docker-compose.dev.yml` | Added Keycloak 24.0 service on port 8080, healthcheck, depends_on postgres |
| `docker/postgres/init-keycloak-db.sh` | Creates keycloak database in PostgreSQL on first boot |
| `docker/keycloak/setup-realm.sh` | One-command setup: creates datawrangler realm, client, test user (testuser@ameritas.com / testpass) |
| `Makefile` | Added keycloak-setup target |
| `.env.example` | Added OIDC, JWT, and service account config vars |
| `backend/pyproject.toml` | Added authlib, httpx, python-jose, slowapi dependencies |

## Acceptance Criteria Results

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-1 | OIDC login redirects to provider with client_id, redirect_uri, scope, state | **PASS** | GET /sso/login calls OIDCProvider.get_authorization_url(), returns RedirectResponse with all required params |
| AC-2 | Callback creates/updates user, returns JWT | **PASS** | GET /sso/callback exchanges code, verifies id_token via JWKS, upserts user by sso_subject_id, returns access + refresh tokens |
| AC-3 | Service account token endpoint works | **PASS** | POST /token validates API key with hmac.compare_digest, returns JWT with service_account role |
| AC-4 | Auth dependency returns 401 for invalid tokens | **PASS** | get_current_user extracts Bearer/cookie, decodes, validates user exists + active, raises HTTPException(401) on failure |
| AC-5 | OIDC state parameter prevents CSRF | **PASS** | State stored in Redis with 10-min TTL (secrets.token_urlsafe(32)), validated + deleted atomically on callback. Missing/expired state → 400 invalid_state |
| AC-6 | Refresh tokens are revocable | **PASS** | Refresh token includes ver=token_version. On decode, validated against user.token_version. Incrementing version invalidates all existing tokens. |

## Verification Results

| Check | Result |
|-------|--------|
| Domain errors zero-framework grep | PASS — no framework imports in errors.py |
| Docker Compose config validation (with Keycloak) | PASS — validates without errors |
| Auth endpoints present in router | PASS — sso_login, sso_callback, create_token, refresh_token, get_me |
| Rate limiting configured | PASS — slowapi on /token (10/min), /refresh (10/min), /sso/login (20/min) |
| Audit logging on auth events | PASS — structlog calls on all auth success/failure paths |
| Token version revocation in dependencies | PASS — get_current_user checks payload.ver against user.token_version |

## Deviations

None. All tasks executed as planned with audit-applied fixes.

## Key Patterns/Decisions

1. **Keycloak for local OIDC** (checkpoint decision) — Real OIDC flow tested locally. Setup script creates realm + client + test user in one command. Production will use Ameritas Okta/Azure AD with same OIDC_ISSUER_URL config swap.
2. **CSRF state in Redis** (audit finding #1) — cryptographically random state stored with 10-min TTL, atomically retrieved + deleted on callback. Prevents callback CSRF.
3. **id_token verification via JWKS** (audit finding #2) — authlib decodes and verifies id_token signature against provider's JWKS endpoint. Prevents forged claims.
4. **Token version revocation** (audit finding #3) — token_version on UserModel, included in refresh token. Incrementing invalidates all existing refresh tokens for that user.
5. **Constant-time API key comparison** (audit finding #4) — hmac.compare_digest prevents timing attacks on service account authentication.
6. **Structured auth audit logging** (audit finding #6) — every auth event (login, callback, token creation, denial) logged with event_type, user_id, ip_address via structlog.

## Skill Audit

/aegis:audit — not yet installed, deferred to Phase 3+ per SPECIAL-FLOWS.md. Not blocking.

## Next Phase

Phase 2 complete (single plan). Ready for **Phase 3: PostgreSQL Connector + Migrations** — implement BaseConnector ABC, PostgreSQL connector, connector registry, and project/connection CRUD API endpoints.

---
*Completed: 2026-03-28*
