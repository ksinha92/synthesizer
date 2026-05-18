"""Unit tests for Job entity."""

from app.domain.shared.job import Job, JobStatus, JobType


class TestJobCanRetry:
    def test_can_retry_failed(self, sample_job):
        job = sample_job(status=JobStatus.FAILED)
        assert job.can_retry() is True

    def test_can_retry_cancelled(self, sample_job):
        job = sample_job(status=JobStatus.CANCELLED)
        assert job.can_retry() is True

    def test_cannot_retry_running(self, sample_job):
        job = sample_job(status=JobStatus.RUNNING)
        assert job.can_retry() is False

    def test_cannot_retry_completed(self, sample_job):
        job = sample_job(status=JobStatus.COMPLETED)
        assert job.can_retry() is False

    def test_cannot_retry_pending(self, sample_job):
        job = sample_job(status=JobStatus.PENDING)
        assert job.can_retry() is False


class TestJobStatusEnum:
    def test_all_statuses_present(self):
        expected = {
            "pending",
            "running",
            "completed",
            "completed_with_warnings",
            "failed",
            "cancelled",
        }
        actual = {s.value for s in JobStatus}
        assert actual == expected

    def test_all_job_types_present(self):
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
