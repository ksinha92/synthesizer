# Phase 54 Context — Destinations + Virtual FKs + Schema-Changes Diff

> Discuss-phase output for v0.8.

## Vision

Three independent backend threads bundled into one plan because each is small:

1. **Destinations**: promote `target_connection_id` from a nullable column to
   a first-class concept by adding `output_mode` (`same_database` /
   `different_connection` / `download_zip` / `s3`). Updates `synthetic_configs`
   + `subset_configs`. UI selector for output mode lands in 55 or later.
2. **Virtual FKs**: add `is_virtual` boolean to `discovered_relationships`.
   User-asserted relationships flagged. New POST/DELETE endpoints to create
   and remove virtual FKs.
3. **Schema-changes diff**: `GET /api/v1/projects/{id}/discovery/diff` that
   compares the latest persisted discovery for a connection against a fresh
   live introspection, returning added/removed/changed tables and columns.

## Constraints

- Migration 020 is additive only — nullable columns + nullable boolean default
  false. No data backfill required.
- Schema-changes diff is read-only: it does NOT persist the fresh
  introspection. Users see what would change before they re-run discovery.
- Virtual FKs are stored in the same `discovered_relationships` table; the
  `is_virtual=true` flag is the only differentiator.

## Plans

| Plan | Scope |
| --- | --- |
| **54-01** | Migration 020 + output_mode plumbing + virtual FK endpoints + schema diff endpoint |

---
*Created: 2026-05-16*
