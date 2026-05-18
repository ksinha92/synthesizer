"""Job entity for async task tracking. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.domain.shared.entity import Entity


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    # Job finished and the artifact (bundle, masked DB write-back, etc.)
    # is usable, but the worker had to drop one or more requested
    # operations on the way through. The job's ``error_message`` carries
    # a one-line summary and ``result_summary`` carries the structured
    # detail. Terminal-state callers (download endpoints, SSE) treat
    # this exactly like ``completed`` — the UI surfaces the warning.
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    DISCOVERY = "discovery"
    MASKING = "masking"
    GENERATION = "generation"
    SUBSETTING = "subsetting"
    WORKFLOW = "workflow"
    FILE_SET = "file_set"
    COMPLIANCE = "compliance"
    EPHEMERAL = "ephemeral"


@dataclass
class Job(Entity):
    """Job record for async task tracking with checkpoint/resume support."""

    project_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    job_type: JobType = JobType.DISCOVERY
    reference_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    error_message: str | None = None
    created_by: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    checkpoint: dict | None = None
    celery_task_id: str | None = None
    result_summary: dict | None = None

    def can_retry(self) -> bool:
        return self.status in (JobStatus.FAILED, JobStatus.CANCELLED)
