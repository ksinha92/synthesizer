---
phase: 42-ux-edge-cases
plan: 01
status: complete
completed: 2026-04-01
---

## What Was Done

Fixed 4 UX edge cases to harden the frontend for real-world usage.

### AC-1: SSE Reconnection with Exponential Backoff ✓
- Added retry logic: 1s, 2s, 4s, 8s, 16s (capped at 30s), max 5 attempts
- New `reconnecting` boolean in return state
- Reset retry counter on successful data receipt
- No retry on AbortError (intentional disconnect)
- After max retries: error message "Connection lost after 5 retries"
- Cleanup: timeout cleared on unmount

### AC-2: NLP Synthetic Generation Timeout UX ✓
- Elapsed time counter shown on button: "Generating... 12s"
- Warning text at 25s: "This is taking longer than usual..."
- Client-side AbortController with 35s timeout
- Explicit timeout error: "Generation timed out. Try a simpler prompt or fewer tables."
- Switched from api.post to raw fetch for AbortController support

### AC-3: Notification Persistence ✓
- Notifications persisted to localStorage on every mutation
- Hydrated from localStorage on store initialization
- User-scoped key: `dw-notifications-${userId}` (reads from auth-store in localStorage)
- 24-hour TTL: stale notifications discarded on hydration
- SSR-safe with try/catch guards
- Quota exceeded errors silently ignored

### AC-4: User-Scoped Onboarding ✓
- Replaced hardcoded `dw-onboarding-done` with `dw-onboarding-${userId}`
- `getOnboardingKey()` helper reads userId from auth-store localStorage
- Falls back to global key if no user authenticated
- All localStorage calls use scoped key
- SSR-safe initialization

## Files Modified
- `frontend/src/hooks/use-sse.ts` — reconnection with exponential backoff
- `frontend/src/components/synthetic/nlp-prompt-form.tsx` — timeout UX with timer
- `frontend/src/stores/notification-store.ts` — localStorage persistence
- `frontend/src/stores/onboarding-store.ts` — user-scoped key

## Verification
- Frontend `next build` succeeds ✓
- synthetic: 10.1kB → 10.4kB ✓
- No backend changes ✓

## Plan vs Actual Reconciliation

| Planned | Actual | Status |
|---------|--------|--------|
| AC-1: SSE backoff | Built as planned | ✓ Match |
| AC-2: NLP timeout | Built as planned + switched to raw fetch | ✓ Enhanced |
| AC-3: Notification persistence | Built as planned | ✓ Match |
| AC-4: User-scoped onboarding | Built as planned | ✓ Match |

### Deviations
- **NLP form uses raw fetch instead of api.post:** The `api.post` helper from `use-api.ts` doesn't support AbortController/signal. Switched to direct `fetch()` with `credentials: "include"` to enable the 35s client-side timeout. Same auth behavior (cookies), just bypasses the wrapper.
- **Notification user-scoping reads auth-store from localStorage directly** instead of importing useAuthStore (to avoid circular dependency at module init time). This works because the auth store uses Zustand's persist middleware pattern.

### Deferred Issues
- SSE hook's `reconnecting` state is not yet consumed by any component (available for future UI indicators)
- Notification store assumes auth-store data structure in localStorage — brittle if auth store changes
- No migration path for old global onboarding key — users who completed before the change will see wizard again under their user-scoped key
