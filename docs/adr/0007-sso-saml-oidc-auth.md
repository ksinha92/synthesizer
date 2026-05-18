# ADR-0007: SSO via SAML/OIDC with JWT Fallback for Service Accounts

- **Status:** Proposed (OIDC partially implemented; SAML + service-account JWT scope not yet ratified)
- **Date:** 2026-05-17
- **Deciders:** Synthia core team, security architect, IT Identity team (review pending)
- **Tags:** auth, security, sso, compliance

**Implementation status (2026-05-17):** `backend/app/infrastructure/auth/` contains `oidc.py`, `jwt.py`, `rbac.py`, and `rate_limit.py`. There is **no SAML implementation** and **no SAML library** (`python3-saml`) in `pyproject.toml`. The "JWT fallback for service accounts" exists as a JWT module but the admin-issued, scoped service-account workflow described here is not implemented. Promotion to Accepted requires IT Identity team sign-off on the IdP integration plan and a follow-up implementation ADR for service-account issuance semantics.

## Context

Synthia must authenticate two distinct caller classes:

1. **Human users** — Ameritas QA, dev, and compliance staff. They already have corporate identities in Okta / Azure AD. Provisioning a separate password database for Synthia is both a security regression (credential sprawl, no central revocation) and an IT policy violation.
2. **Service accounts** — CI pipelines, scheduled masking jobs, and external automation that invoke Synthia's API without an interactive browser flow.

Compliance regimes Synthia serves (GDPR / HIPAA / CCPA) all require centralized authentication, group-based access control, audit-traceable identity, and the ability to revoke access at the IdP.

## Decision

**Primary path: SAML 2.0 and OIDC via Ameritas corporate IdP (Okta or Azure AD).**

- Both SAML and OIDC are supported (library: `authlib` + `python3-saml`). Choice is per-tenant configuration; OIDC preferred for new deployments.
- User identity is asserted by the IdP. Synthia does **not** store passwords.
- Group claims from the IdP map to Synthia roles (`admin`, `engineer`, `auditor`, `viewer`) via configurable claim-to-role rules.
- Session tokens are short-lived (default 8h) with silent refresh.

**Fallback path: JWT-based service accounts.**

- Used only for non-interactive callers (CI, cron jobs).
- Service-account JWTs are issued by Synthia's admin console, scoped (role + bounded-context allowlist), and have explicit expiry.
- Service accounts cannot be created by self-service; admin role required.
- Service-account JWTs are auditable independently of human sessions.

**Common requirements:**

- All authenticated calls produce an audit log entry tagged with `subject_type` (`user` | `service_account`), subject ID, and roles.
- Failed auth attempts are rate-limited and alerted on threshold breach.

## Consequences

**Positive**
- Single source of identity truth; deprovisioning at Okta/Azure AD immediately revokes Synthia access.
- Compliance-friendly: every action is attributable to an IdP-anchored identity.
- Service-account JWT fallback unblocks CI/automation without weakening human-user posture.

**Negative / Tradeoffs**
- SAML + OIDC + JWT means three code paths to maintain and test.
- IdP integration is environment-specific; local dev runs against a stubbed provider, not a real Okta.
- Token refresh, clock skew, and SAML metadata rotation are perennial operational chores.

**Neutral**
- JWT signing key rotation is on a 90-day cadence, automated via Vault (or equivalent secrets backend).
- MFA enforcement is the IdP's responsibility, not Synthia's.

## Alternatives Considered

- **Username/password (with bcrypt) only.** Rejected: violates IT policy, no central revocation, credential sprawl.
- **OIDC-only (no SAML).** Considered. Rejected for now: some Ameritas IdP integrations are SAML-legacy; supporting both removes a deployment blocker.
- **Auth0 / Okta Customer Identity SaaS in front.** Rejected: data residency posture and unnecessary cost given Ameritas already operates the corporate IdP.
- **mTLS for service accounts.** Considered. Deferred: introduces cert-distribution ops complexity; JWTs are good enough for current threat model. Revisit if service-account count grows >50.

## Related

- Related to: ADR-0013 (single-tenant — IdP is Ameritas's), ADR-0011 (audit events emitted from auth middleware)
- References: `backend/app/middleware/` (auth middleware); `authlib`, `python3-saml`
