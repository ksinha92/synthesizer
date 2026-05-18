"""Unit tests for the expanded JobType enum (Phase 59 F10).

The enum is the source of truth for ``job_type`` strings stored in
``jobs.job_type`` and used everywhere from job_repo to the jobs API to the
SSE event stream. Phase 59 added four new values (workflow, file_set,
compliance, ephemeral) so that newly-spawned async work in those domains
can be tracked alongside the original four (discovery, masking, generation,
subsetting).
"""

from __future__ import annotations

import pytest

from app.domain.shared.job import JobType


class TestJobTypeEnumValues:
    def test_all_eight_values_present(self):
        """Each ``JobType`` value below corresponds to a worker module or
        background controller that writes JobModel rows. If you add a new
        worker, add the value here AND in the assertion below.
        """
        expected = {
            "discovery",
            "masking",
            "generation",
            "subsetting",
            "workflow",
            "file_set",
            "compliance",
            "ephemeral",
        }
        actual = {t.value for t in JobType}
        assert actual == expected

    def test_value_round_trip_workflow(self):
        """The enum is a ``str, Enum`` so ``JobType("workflow")`` must round-trip
        to ``JobType.WORKFLOW``. This is what the repo does when hydrating a
        Job from a JobModel row.
        """
        assert JobType("workflow") == JobType.WORKFLOW

    def test_value_round_trip_file_set(self):
        assert JobType("file_set") == JobType.FILE_SET

    def test_value_round_trip_compliance(self):
        assert JobType("compliance") == JobType.COMPLIANCE

    def test_value_round_trip_ephemeral(self):
        assert JobType("ephemeral") == JobType.EPHEMERAL

    def test_unknown_value_raises_value_error(self):
        """Constructing the enum with an unknown string must raise. The jobs
        API has a ``_safe_job_type`` helper that catches this exact error so
        an unknown raw string in the DB column does not 500 the endpoint —
        this test pins down the precondition that helper relies on.
        """
        with pytest.raises(ValueError):
            JobType("not_a_real_job_type")
