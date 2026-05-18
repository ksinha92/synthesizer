"""Phase 59 F11 — checkpoint resume math.

The orchestrator persists ``JobModel.checkpoint = {"step": i, "current_node": id}``
after each successful node. On crash + retry, the next run must resume at
``step + 1`` rather than restart from zero. The math lives in the pure
helper ``compute_start_index`` so it can be tested without the async loop.
"""

from __future__ import annotations

from app.infrastructure.messaging.workflow_tasks import compute_start_index


def test_no_checkpoint_starts_at_zero() -> None:
    assert compute_start_index(None) == 0


def test_empty_checkpoint_starts_at_zero() -> None:
    assert compute_start_index({}) == 0


def test_checkpoint_without_current_node_starts_at_zero() -> None:
    # A stray step without a node id means we never actually completed
    # anything — restart from the top instead of guessing.
    assert compute_start_index({"step": 5}) == 0


def test_checkpoint_resumes_after_last_completed_step() -> None:
    # The orchestrator writes step=i (zero-indexed) after node i finishes.
    # If we crashed after the third node, step=2 → next run starts at i=3.
    assert compute_start_index({"step": 2, "current_node": "node-c"}) == 3


def test_first_node_completed_resumes_at_one() -> None:
    assert compute_start_index({"step": 0, "current_node": "node-a"}) == 1


def test_malformed_step_falls_back_to_zero() -> None:
    # JSONB can hold anything; a string in the step field must not crash.
    assert compute_start_index({"step": "oops", "current_node": "x"}) == 0


def test_non_dict_checkpoint_starts_at_zero() -> None:
    # Defensive: callers can pass weird shapes from old code paths.
    assert compute_start_index("not a dict") == 0  # type: ignore[arg-type]
