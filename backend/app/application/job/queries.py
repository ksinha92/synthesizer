"""Job queries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ListJobsQuery:
    project_id: uuid.UUID
    page: int = 1
    page_size: int = 20
    job_type: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class GetJobQuery:
    job_id: uuid.UUID
