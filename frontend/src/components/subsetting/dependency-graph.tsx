"use client";

import { useMemo } from "react";
import { ReactFlow, Background, Controls, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface TableInfo { name: string; row_count: number; }
interface Relationship { source_table: string; target_table: string; }
interface DryRunRow { table_name: string; subset_count: number; percentage: number; }

interface DependencyGraphProps {
  tables: TableInfo[];
  relationships: Relationship[];
  rootTables: string[];
  traversalDirection: string;
  dryRunData?: DryRunRow[];
}

const COLORS = { upstream: "#3B82F6", downstream: "#22C55E", root: "#8B5CF6" };

// Compact human-readable row counts ("1,632,481" → "1.6M"). Matches the
// Tonic node-chip convention shown in screenshot 11.32.59 so wide tables
// don't blow out the card width.
function compactRows(n: number): string {
  if (!Number.isFinite(n)) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}K`;
  return n.toLocaleString();
}

function nodeLabel(name: string, full: number, dr: DryRunRow | undefined, isRoot: boolean) {
  // Tonic-style node chip: name on top, "full → subset" delta below, and a
  // small status pill ("Root" or percentage retained).
  const delta = dr
    ? `${compactRows(full)} → ${compactRows(dr.subset_count)}`
    : compactRows(full);
  const chip = isRoot
    ? "Root"
    : dr
      ? `${dr.percentage}% kept`
      : null;

  return (
    <div className="flex flex-col items-start gap-1 text-left">
      <span className="text-[11px] font-semibold text-foreground">{name}</span>
      <span className="font-mono text-[10px] text-muted-foreground tabular-nums">{delta}</span>
      {chip && (
        <span
          className={`mt-0.5 inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
            isRoot
              ? "bg-[hsl(var(--dw-pill-success)/0.15)] text-[hsl(var(--dw-pill-success))]"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {chip}
        </span>
      )}
    </div>
  );
}

export function DependencyGraph({ tables, relationships, rootTables, traversalDirection, dryRunData }: DependencyGraphProps) {
  const dryRunMap = useMemo(() => {
    const map: Record<string, DryRunRow> = {};
    dryRunData?.forEach((r) => { map[r.table_name] = r; });
    return map;
  }, [dryRunData]);

  const nodes: Node[] = useMemo(() => {
    const depth: Record<string, number> = {};
    rootTables.forEach((t) => { depth[t] = 0; });

    // Simple BFS for layout
    const queue = [...rootTables];
    const visited = new Set(queue);
    while (queue.length) {
      const node = queue.shift()!;
      const neighbors = traversalDirection === "downstream"
        ? relationships.filter((r) => r.target_table === node).map((r) => r.source_table)
        : relationships.filter((r) => r.source_table === node).map((r) => r.target_table);
      for (const n of neighbors) {
        if (!visited.has(n)) {
          visited.add(n);
          depth[n] = (depth[node] || 0) + 1;
          queue.push(n);
        }
      }
    }
    // Add unvisited tables
    tables.forEach((t) => { if (!(t.name in depth)) depth[t.name] = 99; });

    const layers: Record<number, TableInfo[]> = {};
    tables.filter((t) => depth[t.name] !== 99).forEach((t) => {
      const d = depth[t.name] || 0;
      if (!layers[d]) layers[d] = [];
      layers[d].push(t);
    });

    return Object.entries(layers).flatMap(([layerStr, layerTables]) =>
      layerTables.map((t, i) => {
        const isRoot = rootTables.includes(t.name);
        const dr = dryRunMap[t.name];
        return {
          id: t.name,
          position: { x: i * 250, y: Number(layerStr) * 180 },
          data: { label: nodeLabel(t.name, t.row_count, dr, isRoot) },
          style: {
            background: "var(--card)",
            border: `3px solid ${isRoot ? COLORS.root : "var(--border)"}`,
            borderRadius: 8, padding: "8px 12px", fontSize: 11, minWidth: 180,
          },
          sourcePosition: "bottom" as any,
          targetPosition: "top" as any,
        };
      })
    );
  }, [tables, relationships, rootTables, traversalDirection, dryRunMap]);

  const edges: Edge[] = useMemo(() =>
    relationships.map((r, i) => ({
      id: `e-${i}`,
      source: r.target_table,
      target: r.source_table,
      animated: true,
      style: {
        stroke: traversalDirection === "upstream" ? COLORS.upstream : COLORS.downstream,
        strokeWidth: 2,
      },
      markerEnd: { type: "arrowclosed" as any },
    })),
    [relationships, traversalDirection]
  );

  if (nodes.length === 0) {
    return <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">No relationship data. Run discovery first.</div>;
  }

  return (
    <div className="h-[400px] rounded-lg border border-border overflow-hidden">
      <ReactFlow nodes={nodes} edges={edges} fitView className="bg-background" proOptions={{ hideAttribution: true }}>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
