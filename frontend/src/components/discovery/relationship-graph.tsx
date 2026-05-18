"use client";

import { useMemo } from "react";
import { ReactFlow, Background, Controls, MiniMap, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface TableInfo { name: string; row_count: number; pii_count?: number; }
interface Relationship {
  id?: string;
  source_table: string;
  target_table: string;
  source_column?: string;
  is_virtual?: boolean;
}

interface RelationshipGraphProps {
  tables: TableInfo[];
  relationships: Relationship[];
  onNodeClick?: (tableName: string) => void;
  onDeleteRelationship?: (relationshipId: string) => void;
}

const MAX_TABLES = 50;

function layoutNodes(tables: TableInfo[], relationships: Relationship[]): Node[] {
  // BFS layered layout: assign depth from leaf tables, space within layers
  const adj: Record<string, Set<string>> = {};
  const tableNames = new Set(tables.map((t) => t.name));

  // Filter to FK-connected tables only if too many
  const connectedTables = new Set<string>();
  for (const rel of relationships) {
    connectedTables.add(rel.source_table);
    connectedTables.add(rel.target_table);
    if (!adj[rel.source_table]) adj[rel.source_table] = new Set();
    adj[rel.source_table].add(rel.target_table);
  }

  const displayTables = tables.length > MAX_TABLES
    ? tables.filter((t) => connectedTables.has(t.name)).slice(0, MAX_TABLES)
    : tables;

  // Assign depth via BFS from tables with no parents (root tables)
  const depth: Record<string, number> = {};
  const roots = displayTables.filter((t) => !relationships.some((r) => r.source_table === t.name));
  const queue = roots.map((t) => t.name);
  queue.forEach((n) => { depth[n] = 0; });

  const visited = new Set(queue);
  while (queue.length > 0) {
    const node = queue.shift()!;
    const children = relationships.filter((r) => r.target_table === node).map((r) => r.source_table);
    for (const child of children) {
      if (!visited.has(child)) {
        visited.add(child);
        depth[child] = (depth[node] || 0) + 1;
        queue.push(child);
      }
    }
  }

  // Assign remaining unvisited tables
  displayTables.forEach((t) => { if (!(t.name in depth)) depth[t.name] = 0; });

  // Group by depth layer
  const layers: Record<number, TableInfo[]> = {};
  displayTables.forEach((t) => {
    const d = depth[t.name] || 0;
    if (!layers[d]) layers[d] = [];
    layers[d].push(t);
  });

  // Position: 250px horizontal gap, 200px vertical gap
  const nodes: Node[] = [];
  Object.entries(layers).forEach(([layerStr, layerTables]) => {
    const layer = Number(layerStr);
    layerTables.forEach((t, i) => {
      nodes.push({
        id: t.name,
        position: { x: i * 250, y: layer * 200 },
        data: { label: t.name, rowCount: t.row_count, piiCount: t.pii_count || 0 },
        type: "default",
        style: {
          background: "var(--card)", border: "2px solid var(--border)", borderRadius: 8,
          padding: "8px 12px", fontSize: 12, minWidth: 140,
        },
      });
    });
  });

  return nodes;
}

export function RelationshipGraph({
  tables,
  relationships,
  onNodeClick,
  onDeleteRelationship,
}: RelationshipGraphProps) {
  const nodes = useMemo(() => layoutNodes(tables, relationships), [tables, relationships]);
  const edges: Edge[] = useMemo(
    () =>
      relationships.map((r, i) => {
        const virtual = !!r.is_virtual;
        const label = virtual
          ? `${r.source_column || ""} • virtual`
          : r.source_column || "";
        return {
          id: r.id ? `r-${r.id}` : `e-${i}`,
          source: r.target_table, // parent
          target: r.source_table, // child (FK points parent→child visually)
          animated: virtual,
          label,
          labelStyle: virtual
            ? { fill: "hsl(var(--dw-brand))", fontWeight: 600 }
            : undefined,
          style: {
            stroke: virtual ? "hsl(var(--dw-brand))" : "var(--muted-foreground)",
            strokeWidth: virtual ? 2 : 1.5,
            strokeDasharray: virtual ? "6 4" : undefined,
          },
          markerEnd: { type: "arrowclosed" as any },
          data: { relationshipId: r.id, isVirtual: virtual },
        };
      }),
    [relationships]
  );

  const hiddenCount = tables.length > MAX_TABLES ? tables.length - nodes.length : 0;
  const virtualCount = relationships.filter((r) => r.is_virtual).length;

  const handleEdgeClick = (
    _evt: React.MouseEvent,
    edge: Edge,
  ) => {
    const data = edge.data as { relationshipId?: string; isVirtual?: boolean } | undefined;
    if (!onDeleteRelationship || !data?.isVirtual || !data.relationshipId) return;
    if (window.confirm("Delete this virtual FK?")) {
      onDeleteRelationship(data.relationshipId);
    }
  };

  return (
    <div className="h-[500px] rounded-lg border border-border overflow-hidden relative">
      {(hiddenCount > 0 || virtualCount > 0) && (
        <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
          {virtualCount > 0 && (
            <span className="rounded-full bg-[hsl(var(--dw-brand)/0.15)] px-3 py-1 text-xs text-[hsl(var(--dw-brand))]">
              {virtualCount} virtual FK{virtualCount === 1 ? "" : "s"}
            </span>
          )}
          {hiddenCount > 0 && (
            <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
              {hiddenCount} standalone tables hidden
            </span>
          )}
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={(_, node) => onNodeClick?.(node.id)}
        onEdgeClick={handleEdgeClick}
        fitView
        className="bg-background"
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
