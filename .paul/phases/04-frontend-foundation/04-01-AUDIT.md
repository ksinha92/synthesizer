# Enterprise Plan Audit Report

**Plan:** .paul/phases/04-frontend-foundation/04-01-PLAN.md
**Audited:** 2026-03-28
**Verdict:** Conditionally Acceptable (after applied fixes)

---

## 1. Executive Verdict

**Conditionally acceptable.** The plan's architecture (hybrid shadcn + Ant Design, AppShell, theme system) is well-designed. However, the original plan stored JWT tokens in localStorage — a known XSS vector that is unacceptable for an enterprise app handling PII. Additionally, no CSP headers were specified, the Ant Design CSS scoping approach (`all: revert`) would break component rendering, and no error boundaries protected against white-screen crashes. All remediated.

---

## 2. What Is Solid

- **Hybrid design system architecture is correct.** shadcn/ui for primary UI, Ant Design only for Table/Tree — isolated. This avoids Ant Design's heavy global CSS while getting its best data components.
- **next-themes for theme management** is the right choice. Handles SSR hydration, localStorage persistence, and system preference detection out of the box.
- **Collapsible sidebar with responsive drawer** is the correct responsive pattern. Desktop fixed, mobile overlay.
- **Navigation config array** (not hardcoded items) enables Phase 8 to add project-scoped nav without modifying sidebar code.
- **Human-verify checkpoint for visual validation** is appropriate — CSS scoping and theme behavior need human eyes.
- **Zustand for client state** is lightweight and appropriate. Not over-engineering with Redux.

---

## 3. Enterprise Gaps Identified

1. **JWT in localStorage** — any XSS vulnerability exposes the token. The app will render user-controlled data (database column names, schema names, LLM outputs) that could contain injection payloads.
2. **No CSP headers** — Content Security Policy is the primary defense against XSS for web applications. Not having it is a P1 security gap.
3. **`all: revert` CSS scoping breaks Ant Design** — reverts display, position, flex, grid on the container, breaking Ant Table/Tree rendering. CSS @layer is the correct approach.
4. **No error boundary** — unhandled React error crashes the entire app. White screen with no recovery.
5. **SSO redirect loses intended URL** — user visits /projects/123/discovery, gets redirected to /login, SSO completes, lands on / instead of the page they wanted.

---

## 4. Upgrades Applied to Plan

### Must-Have (Release-Blocking)

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 1 | JWT in localStorage XSS risk | Task 3, auth-store action | Changed to httpOnly cookies (credentials: "include"). No token in localStorage. Backend Phase 2 already supports cookie extraction. |
| 2 | No CSP headers | Task 1, new step 9 (next.config.js) | Added Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy headers |

### Strongly Recommended

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 3 | `all: revert` breaks Ant Design | Task 1, globals.css step 3 | Replaced with CSS @layer approach (tailwind, ant layers with clean precedence) |
| 4 | No error boundary | Task 1, layout.tsx step 6 | Added React ErrorBoundary + Suspense boundary with fallbacks |
| 5 | SSO redirect loses URL | Task 3, login page + useApi hook | Store intended URL in sessionStorage before SSO redirect. useApi 401 handler preserves ?redirect= param. |

### Deferred (Can Safely Defer)

| # | Finding | Rationale for Deferral |
|---|---------|----------------------|
| 6 | Docker Compose frontend service | Dev runs npm directly. Docker integration in Phase 8/9. |
| 7 | Accessibility audit | Phase 10 polish. Foundation structure supports it. |

---

## 5. Audit & Compliance Readiness

**XSS protection:** httpOnly cookies + CSP headers provide defense-in-depth. Tokens cannot be exfiltrated via JavaScript. CSP blocks inline script injection.

**Error resilience:** ErrorBoundary prevents white-screen crashes. Users see a recovery UI instead of nothing.

**Session continuity:** Redirect preservation ensures users don't lose their place after SSO authentication.

---

## 6. Final Release Bar

**What must be true:**
- No JWT tokens stored in localStorage (httpOnly cookies only)
- CSP headers set in next.config.js
- Ant Design CSS uses @layer, not `all: revert`
- ErrorBoundary + Suspense in root layout
- SSO redirect preserves intended URL

**Sign-off:** After 5 applied fixes, this plan delivers a secure, resilient frontend foundation.

---

**Summary:** Applied 2 must-have + 3 strongly-recommended upgrades. Deferred 2 items.
**Plan status:** Updated and ready for APPLY

---
*Audit performed by PAUL Enterprise Audit Workflow*
*Audit template version: 1.0*
