"""Shared test fixtures."""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

# Force test environment BEFORE app imports — auth dependency reads settings.ENVIRONMENT
# and bypasses auth in "development". Tests must validate real auth behavior.
os.environ["ENVIRONMENT"] = "test"

from app.config import settings
settings.ENVIRONMENT = "test"

from app.domain.discovery.entities import DiscoveredColumn
from app.domain.discovery.value_objects import Classification, PIIConfidence, PIIType
from app.domain.shared.job import Job, JobStatus, JobType


@pytest.fixture
def sample_column():
    """Create a DiscoveredColumn for testing."""
    def _make(
        column_name: str = "test_col",
        data_type: str = "varchar",
        pii_type: PIIType = PIIType.NONE,
        sample_values: list | None = None,
    ) -> DiscoveredColumn:
        return DiscoveredColumn(
            id=uuid.uuid4(),
            table_id=uuid.uuid4(),
            column_name=column_name,
            data_type=data_type,
            sample_values=sample_values or [],
            pii_type=pii_type,
            pii_confidence=PIIConfidence(),
            classification=Classification.NEEDS_REVIEW,
        )
    return _make


@pytest.fixture
def sample_job():
    """Create a Job for testing."""
    def _make(status: JobStatus = JobStatus.PENDING) -> Job:
        return Job(
            project_id=uuid.uuid4(),
            job_type=JobType.DISCOVERY,
            reference_id=uuid.uuid4(),
            status=status,
            created_by=uuid.uuid4(),
        )
    return _make


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider."""
    provider = AsyncMock()
    provider.classify = AsyncMock(return_value=("email", 0.7))
    provider.check_budget = lambda: True
    provider.increment_call_count = lambda: None
    return provider
