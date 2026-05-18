"""Workflow commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class CreateWorkflowCommand:
    project_id: uuid.UUID
    name: str
    description: str = ""
    dag_definition: dict | None = None


@dataclass(frozen=True)
class ExecuteWorkflowCommand:
    workflow_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
