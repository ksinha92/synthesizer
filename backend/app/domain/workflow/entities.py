"""Workflow domain entities. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.domain.shared.entity import AggregateRoot


@dataclass
class WorkflowNode:
    id: str = ""
    type: str = ""  # discover | mask | generate | subset | export
    config: dict = field(default_factory=dict)
    position: dict = field(default_factory=lambda: {"x": 0, "y": 0})


@dataclass
class WorkflowEdge:
    source_node_id: str = ""
    target_node_id: str = ""


@dataclass
class Workflow(AggregateRoot):
    project_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    name: str = ""
    description: str = ""
    dag_definition: dict = field(default_factory=lambda: {"nodes": [], "edges": []})
    is_active: bool = True
