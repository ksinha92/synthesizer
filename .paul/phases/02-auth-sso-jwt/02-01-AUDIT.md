# Enterprise Plan Audit Report

**Plan:** .paul/phases/02-auth-sso-jwt/02-01-PLAN.md
**Audited:** 2026-03-28
**Verdict:** Conditionally Acceptable (after applied fixes)

---

## 1. Executive Verdict

**Conditionally acceptable.** The original plan had the right architecture (OIDC + JWT + FastAPI dependencies) but had three critical security gaps that would fail any real authentication audit: no CSRF protection on OIDC callback, no id_token signature verification, and irrevocable 7-day refresh tokens. These are not obscure — they are OWASP top-10 authentication vulnerabilities. All three have been remediated. Additionally, missing rate limiting and audit logging were addressed.

Would I sign off on the original plan? No — authentication code without CSRF protection is a hard stop. After fixes? Yes.

---

## 2. What Is Solid

- **SSO-first approach is correct** for an internal enterprise tool. No password-based auth reduces attack surface.
- **JWT for service accounts** is the right pattern for CI/CD — stateless, auditable, separate from user auth.
- **Auth dependency as FastAPI Depends** is the correct injection pattern — every route that needs auth gets it declaratively.
- **Domain errors (AuthenticationError, AuthorizationError)** in domain/shared with no framework imports — maintains DDD boundary.
- **Checkpoint for SSO provider decision** — honest acknowledgment that the provider is unknown. Good engineering discipline.
- **Boundaries protect Phase 1 work** — domain base classes and connection context marked DO NOT CHANGE.

---

## 3. Enterprise Gaps Identified

1. **CSRF vulnerability on OIDC callback** — `state` parameter existed but was not validated against a server-side store. An attacker could craft a callback URL with their own authorization code, potentially linking the victim's session to the attacker's account.
2. **No id_token signature verification** — exchanging the code and "extracting user info" without verifying the id_token against the provider's JWKS means a man-in-the-middle could forge user claims.
3. **Irrevocable refresh tokens** — 7-day stateless JWTs with no revocation mechanism. A compromised refresh token gives 7 days of access with no ability to revoke. In a platform handling PII, this is a HIPAA audit finding.
4. **API keys compared without constant-time comparison** — `SERVICE_ACCOUNT_API_KEYS` list membership check is vulnerable to timing attacks.
5. **No rate limiting on auth endpoints** — brute-force protection is table stakes.
6. **No structured audit logging** — SOC 2 and HIPAA both require audit trails for authentication events.

---

## 4. Upgrades Applied to Plan

### Must-Have (Release-Blocking)

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 1 | CSRF on OIDC callback | Task 1, oidc.py action | State stored in Redis with 10-min TTL, validated + deleted on callback. Added AC-5. |
| 2 | id_token not verified | Task 1, oidc.py action | Added explicit instruction to verify id_token signature against provider JWKS |
| 3 | Irrevocable refresh tokens | Task 1, jwt.py + UserModel | Added token_version to UserModel and refresh token. Incrementing version invalidates all tokens. Added AC-6. Migration 002 added. |

### Strongly Recommended

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 4 | Timing attack on API key comparison | Task 1, jwt.py action | Changed to hmac.compare_digest for constant-time comparison |
| 5 | No rate limiting | Task 2, new step 4 + config.py + pyproject.toml | Added slowapi dependency, rate limits on /token (10/min), /refresh (10/min), /sso/login (20/min) |
| 6 | No auth event audit logging | Task 2, new step 5 | Added structured auth event logging (sso_login, callback, token_created, auth_denied, etc.) |

### Deferred (Can Safely Defer)

| # | Finding | Rationale for Deferral |
|---|---------|----------------------|
| 7 | Migration 002 was in files_modified but no task created it | Added to Task 1 as step 7 — resolved |
| 8 | RSA/ES256 JWT signing for production | Noted as TODO in plan. HS256 acceptable for Phase 2 with strong SECRET_KEY. Production hardening in Phase 3. |

---

## 5. Audit & Compliance Readiness

**Audit evidence:** Structured auth event logging (finding #6) now produces a defensible trail of login success/failure, token creation, and auth denial events. Each log entry includes event_type, user_id, ip_address, and timestamp.

**Silent failures prevented:** CSRF validation (finding #1) prevents silent session hijacking. id_token verification (finding #2) prevents silent impersonation. Token version check (finding #3) enables active revocation.

**Post-incident reconstruction:** Auth event logs support reconstruction of: who logged in, when, from where, which tokens were issued, which were rejected. This satisfies HIPAA access log requirements.

**Ownership:** Auth infrastructure owned by Platform/DevOps role per PLANNING.md.

---

## 6. Final Release Bar

**What must be true before this plan ships:**
- OIDC state parameter stored in Redis and validated on callback (CSRF protection)
- id_token signature verified against provider JWKS
- Refresh tokens include token_version, validated against user record
- API key comparison uses constant-time hmac.compare_digest
- Auth endpoints rate-limited (429 on excess)
- All auth events produce structured log entries

**Remaining risks if shipped as-is (after fixes):**
- API keys stored as plaintext in config (acceptable for Phase 2 — no real service accounts yet)
- JWT uses HS256 not RS256 (noted TODO, acceptable for internal tool)
- No RBAC enforcement beyond basic role check (Phase 3)

**Sign-off:** After 6 applied fixes and 2 new acceptance criteria, this plan meets enterprise authentication standards. The OIDC flow is CSRF-protected, tokens are verifiable and revocable, and auth events are audited.

---

**Summary:** Applied 3 must-have + 3 strongly-recommended upgrades. Added AC-5 (CSRF) and AC-6 (revocation). Deferred 2 items.
**Plan status:** Updated and ready for APPLY

---
*Audit performed by PAUL Enterprise Audit Workflow*
*Audit template version: 1.0*
