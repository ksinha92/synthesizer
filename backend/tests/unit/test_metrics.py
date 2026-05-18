"""Tests for the operational metrics endpoint."""

from app.infrastructure.monitoring.metrics import _to_prometheus


def test_prometheus_output_includes_help_and_type_lines():
    out = _to_prometheus({"pending": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0})
    assert "# HELP datawrangler_jobs_total" in out
    assert "# TYPE datawrangler_jobs_total gauge" in out


def test_prometheus_output_one_line_per_status():
    counts = {"pending": 3, "running": 1, "completed": 42, "failed": 2, "cancelled": 0}
    out = _to_prometheus(counts)
    for status, value in counts.items():
        assert f'datawrangler_jobs_total{{status="{status}"}} {value}' in out


def test_prometheus_output_is_text_plain():
    out = _to_prometheus({"pending": 1})
    # Each metric ends with a newline so the exposition parser doesn't choke.
    assert out.endswith("\n")
