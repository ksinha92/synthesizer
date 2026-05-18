# Phase 56 Context — Finish v0.8 Deferred Work

> Discuss-phase output. Tactical follow-up to v0.8 closure.

Five threads from v0.8's deferred list, ordered smallest first so the
plan stays shippable even if context runs short:

| # | Thread | Scope |
|---|---|---|
| A | Generator-presets → Database View binding | Replace in-code generator list with live presets |
| B | `output_mode` end-to-end | Pydantic + UI selector on synthetic / subset config |
| C | Schema-changes UI panel | Fetch `/discovery/diff` and render on connection detail |
| D | Virtual FK add/remove on the relationships graph | Extend existing ReactFlow graph + dashed-edge styling |
| E | Masking engine joint generation | Honor `linked_column_ids` + `consistency_group` in `masking_engine.py` |

## Plans

| Plan | Scope |
| --- | --- |
| **56-01** | Threads A + B (small backend + UI updates) |
| **56-02** | Thread C (new component + page wiring) |
| **56-03** | Thread D (graph extension + virtual-edge style) |
| **56-04** | Thread E (engine update + tests for joint generation) |

Each plan ships green; if context runs out, partial completion still leaves
v0.8 in a coherent state.

---
*Created: 2026-05-16*
