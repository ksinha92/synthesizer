---
phase: 04-frontend-foundation
plan: 01
completed: 2026-03-28
duration: ~20min
---

# Phase 4 Plan 01: Frontend Foundation Summary

**Initialized the Next.js 14 frontend with hybrid design system (shadcn/ui + Tailwind + Ant Design CSS-scoped), dark/light/system theme, AppShell layout, Zustand stores, auth hook, SSO login page, and test scaffolding.**

## Objective

Establish the frontend foundation that all subsequent UI phases build on. Hybrid design system, theme, and AppShell must be solid before page development starts.

## What Was Built

| File | Purpose |
|------|---------|
| `frontend/package.json` | Next.js 14, React 18, shadcn deps, Ant Design 5, next-themes, Zustand, Lucide, testing deps |
| `frontend/next.config.js` | CSP headers (default-src, script-src, connect-src), X-Frame-Options DENY, X-Content-Type-Options nosniff |
| `frontend/tailwind.config.ts` | CSS variable tokens (background, foreground, card, primary, etc.), Ameritas Blue #1B65A6, dark mode via class |
| `frontend/src/app/globals.css` | Light + dark CSS variable blocks, CSS @layer (tailwind, ant) for Ant Design isolation |
| `frontend/src/app/layout.tsx` | Root layout: ThemeProvider + ErrorBoundary + Suspense, Inter + JetBrains Mono fonts |
| `frontend/src/components/theme/theme-provider.tsx` | next-themes wrapper + Ant Design ConfigProvider token sync (dark/light algorithm) |
| `frontend/src/components/theme/theme-toggle.tsx` | Three-way toggle: Sun/Moon/Monitor icons, persisted via next-themes |
| `frontend/src/components/ui/error-boundary.tsx` | React ErrorBoundary with "Something went wrong" + refresh button |
| `frontend/src/components/layout/sidebar.tsx` | Collapsible sidebar: 240px expanded / 64px collapsed, global nav + project-scoped nav, Lucide icons, active state, mobile: overlay drawer |
| `frontend/src/components/layout/header.tsx` | 56px header: logo, Cmd+K search placeholder, ThemeToggle, notification bell placeholder, user avatar |
| `frontend/src/components/layout/breadcrumbs.tsx` | Auto-generated from pathname with label mapping, Home icon root, ChevronRight separators |
| `frontend/src/components/layout/app-shell.tsx` | Composes sidebar + header + breadcrumbs + content. Max-width 1440px centered. Mobile drawer overlay. Sidebar collapse persisted. |
| `frontend/src/app/page.tsx` | Dashboard placeholder with stat cards and section placeholders in AppShell |
| `frontend/src/stores/auth-store.ts` | Zustand: user state, loadUser via GET /auth/me with credentials: "include" (httpOnly cookies), logout redirects to /login |
| `frontend/src/stores/theme-store.ts` | Zustand: sidebar collapsed state persisted in localStorage |
| `frontend/src/hooks/use-api.ts` | API hook: credentials: "include" on all requests, 401→redirect to /login?redirect=, typed get/post/put/del methods |
| `frontend/src/app/(auth)/login/page.tsx` | SSO login page: branded design, "Sign in with SSO" button, redirect preservation via sessionStorage, Keycloak dev note |
| `frontend/jest.config.ts` | Next.js jest config with SWC transform, jsdom environment, path aliases |
| `frontend/playwright.config.ts` | Chromium + Firefox, screenshots on failure, webServer auto-start |

## Acceptance Criteria Results

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-1 | Hybrid design system builds and runs | **PASS** | shadcn/ui + Tailwind render, Ant Design CSS-scoped via @layer, next.config.js with CSP headers |
| AC-2 | Theme toggle switches light/dark/system | **PASS** | ThemeToggle with Sun/Moon/Monitor, next-themes persistence, Ant Design ConfigProvider token sync |
| AC-3 | AppShell with collapsible sidebar + header | **PASS** | Sidebar 240px→64px collapse, header 56px with logo/search/theme/user, breadcrumbs, max-width 1440px content, mobile drawer |
| AC-4 | Login redirects to SSO, useApi handles auth | **PASS** | Login page SSO button, redirect preservation in sessionStorage, useApi credentials:"include", 401→/login?redirect= |

## Verification Results

| Check | Result |
|-------|--------|
| No tokens in localStorage | PASS — grep confirms no localStorage token storage; httpOnly cookies via credentials:"include" |
| CSP headers in next.config.js | PASS — Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| CSS @layer for Ant Design (not all:revert) | PASS — globals.css uses @layer tailwind, ant |
| ErrorBoundary in root layout | PASS — ErrorBoundary + Suspense wrapping children |
| Redirect preservation on 401 | PASS — useApi stores ?redirect= param, login page reads from sessionStorage |
| Visual checkpoint | PASS — user approved theme switching, sidebar collapse, responsive behavior |

## Deviations

None.

## Key Patterns/Decisions

1. **httpOnly cookies, not localStorage** (audit finding #1) — tokens never accessible to JavaScript. useApi and auth-store use `credentials: "include"` for cookie-based auth.
2. **CSP headers** (audit finding #2) — Content-Security-Policy restricts script/style/connect sources. X-Frame-Options DENY prevents clickjacking.
3. **CSS @layer for Ant Design scoping** (audit finding #3) — `@layer tailwind, ant` gives clean precedence without breaking Ant component layout. Replaced original `all: revert` approach.
4. **ErrorBoundary + Suspense in root layout** (audit finding #4) — prevents white-screen crashes, shows recovery UI.
5. **Redirect preservation** (audit finding #5) — useApi 401 handler adds `?redirect=` param, login page stores in sessionStorage before SSO navigation.
6. **Navigation config arrays** — sidebar nav items defined as arrays, not hardcoded. Phase 8 can extend without modifying sidebar component.

## Skill Audit

/aegis:audit — not yet installed, deferred per SPECIAL-FLOWS.md.

## Next Phase

Phase 4 complete. Ready for **Phase 5: Schema Discovery + PII Detection** — discovery bounded context, 4-layer PII pipeline, discovery API endpoints, Celery tasks.

---
*Completed: 2026-03-28*
