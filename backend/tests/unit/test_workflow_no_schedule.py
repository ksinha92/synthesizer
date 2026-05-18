"""Verify the legacy ``schedule`` field is gone (Phase 59 F12)."""

from __future__ import annotations

from dataclasses import fields

from app.api.v1.workflows import WorkflowCreate, WorkflowResponse
from app.application.workflow.commands import CreateWorkflowCommand
from app.domain.workflow.entities import Workflow
from app.infrastructure.persistence.models.workflow import WorkflowModel


def test_workflow_entity_has_no_schedule_field():
    names = {f.name for f in fields(Workflow)}
    assert "schedule" not in names, (
        "Workflow domain entity must not carry a schedule field "
        "after Phase 59 F12 — found: %r" % sorted(names)
    )


def test_create_workflow_command_has_no_schedule_field():
    names = {f.name for f in fields(CreateWorkflowCommand)}
    assert "schedule" not in names


def test_workflow_create_schema_has_no_schedule_property():
    schema = WorkflowCreate.model_json_schema()
    props = set(schema.get("properties", {}).keys())
    assert "schedule" not in props


def test_workflow_response_schema_has_no_schedule_property():
    schema = WorkflowResponse.model_json_schema()
    props = set(schema.get("properties", {}).keys())
    assert "schedule" not in props


def test_workflow_orm_model_has_no_schedule_column():
    cols = {c.name for c in WorkflowModel.__table__.columns}
    assert "schedule" not in cols, (
        "WorkflowModel must not declare a schedule column after F12 — "
        "the migration drops it in alembic 025."
    )
