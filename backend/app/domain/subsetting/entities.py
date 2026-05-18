"""Subsetting domain entities. No framework dependencies."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from app.domain.shared.entity import AggregateRoot


@dataclass
class SubsetConfig(AggregateRoot):
    project_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    name: str = ""
    # May be None if the source connection was deleted (FK ON DELETE SET NULL).
    # Callers must reassign a source before analyze/execute can run.
    source_connection_id: uuid.UUID | None = None
    target_connection_id: uuid.UUID | None = None
    target_percentage: float | None = None
    target_row_count: int | None = None
    root_tables: list[dict] = field(default_factory=list)  # [{table_name, where_filter}]
    traversal_strategy: str = "upstream"  # upstream | downstream | both
    # Where the subset output lands; mirrors SubsetConfigModel.output_mode.
    # Valid values are validated at the API boundary (ALLOWED_OUTPUT_MODES).
    output_mode: str = "same_database"


@dataclass
class DependencyGraph:
    """Directed FK dependency graph. Edges: child → parent (FK direction)."""

    nodes: set[str] = field(default_factory=set)
    edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # child → {parents}
    reverse_edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # parent → {children}
    cycle_tables: set[str] = field(default_factory=set)

    def add_edge(self, child: str, parent: str) -> None:
        self.nodes.add(child)
        self.nodes.add(parent)
        if child != parent:  # Skip self-refs
            self.edges[child].add(parent)
            self.reverse_edges[parent].add(child)
