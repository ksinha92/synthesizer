"use client";

import { useEffect, useState } from "react";
import { ArrowUp, ArrowDown, ArrowUpDown, Info, Loader2, Play, Settings } from "lucide-react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useSubsettingStore } from "@/stores/subsetting-store";
import { useConnectionStore } from "@/stores/connection-store";
import { ConfigureTableDrawer } from "@/components/subsetting/configure-table-drawer";
import { cn } from "@/lib/utils";

interface SubsettingConfigProps { projectId: string; }

interface AnalysisRow {
  table_name: string;
  full_count: number;
  subset_count: number;
  percentage: number;
}

const TRAVERSALS = [
  { key: "upstream", label: "Upstream", icon: ArrowUp, desc: "Child → Parent" },
  { key: "downstream", label: "Downstream", icon: ArrowDown, desc: "Parent → Child" },
  { key: "both", label: "Both", icon: ArrowUpDown, desc: "Full graph" },
] as const;

export function SubsettingConfig({ projectId }: SubsettingConfigProps) {
  const [connectionId, setConnectionId] = useState("");
  const [name, setName] = useState("");
  const [rootTable, setRootTable] = useState("");
  const [whereFilter, setWhereFilter] = useState("");
  const [traversal, setTraversal] = useState("upstream");
  const [targetPct, setTargetPct] = useState(10);
  const [configId, setConfigId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  // Per-table Configure drawer (T2.4 Tonic 11.31.45). The drawer reads the
  // selected table name; persistence is local for now.
  const [configureTable, setConfigureTable] = useState<string | null>(null);

  const { createConfig, analyze, execute, analysis, analyzing } = useSubsettingStore();
  const { connections, fetchConnections } = useConnectionStore();

  useEffect(() => { fetchConnections(projectId); }, [projectId, fetchConnections]);

  const handleAnalyze = async () => {
    let cid = configId;
    if (!cid) {
      cid = await createConfig(projectId, {
        name: name || "Subset Config", source_connection_id: connectionId,
        target_percentage: targetPct, root_tables: [{ table_name: rootTable, where_filter: whereFilter }],
        traversal_strategy: traversal,
      });
      if (cid) setConfigId(cid);
    }
    if (cid) await analyze(projectId, cid);
  };

  const handleExecute = async () => {
    if (configId) {
      const jid = await execute(projectId, configId);
      if (jid) setJobId(jid);
    }
  };

  const analysisColumns: ColumnsType<AnalysisRow> = [
    {
      title: "Table",
      dataIndex: "table_name",
      key: "table_name",
      sorter: (a, b) => a.table_name.localeCompare(b.table_name),
      render: (name: string) => <span className="font-mono text-foreground">{name}</span>,
    },
    {
      title: "Full Count",
      dataIndex: "full_count",
      key: "full_count",
      align: "right",
      sorter: (a, b) => a.full_count - b.full_count,
      render: (v: number) => <span className="text-muted-foreground">{v.toLocaleString()}</span>,
    },
    {
      title: "Subset Count",
      dataIndex: "subset_count",
      key: "subset_count",
      align: "right",
      sorter: (a, b) => a.subset_count - b.subset_count,
      render: (v: number) => <span className="font-medium text-foreground">{v.toLocaleString()}</span>,
    },
    {
      title: "%",
      dataIndex: "percentage",
      key: "percentage",
      align: "right",
      render: (v: number) => <span className="text-muted-foreground">{v}%</span>,
      width: 80,
    },
    {
      title: "",
      key: "configure",
      width: 110,
      render: (_: unknown, row: AnalysisRow) => (
        <button
          type="button"
          onClick={() => setConfigureTable(row.table_name)}
          className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Settings className="h-3 w-3" />
          Configure
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-foreground">Subset Configuration</h3>

        {/* Source connection */}
        <div>
          <label className="block text-xs font-medium text-foreground mb-1">Source Connection *</label>
          <select value={connectionId} onChange={e => setConnectionId(e.target.value)} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
            <option value="">Select connection...</option>
            {connections.map(c => <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>)}
          </select>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Root Table *</label>
            <input type="text" value={rootTable} onChange={e => setRootTable(e.target.value)} placeholder="claims" className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Target %</label>
            <input type="number" value={targetPct} onChange={e => setTargetPct(Number(e.target.value))} min={1} max={100} className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" />
          </div>
        </div>

        {/* Traversal direction */}
        <div>
          <label className="block text-xs font-medium text-foreground mb-2">Traversal Direction</label>
          <div className="flex gap-2">
            {TRAVERSALS.map(t => (
              <button key={t.key} onClick={() => setTraversal(t.key)} className={cn(
                "flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-all",
                traversal === t.key ? "border-primary bg-primary/5 text-primary" : "border-border text-muted-foreground hover:border-primary/50"
              )}>
                <t.icon className="h-3.5 w-3.5" /> {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* WHERE filter */}
        <div>
          <label className="block text-xs font-medium text-foreground mb-1">WHERE Filter (optional)</label>
          <input type="text" value={whereFilter} onChange={e => setWhereFilter(e.target.value)}
            placeholder="created_at > '2024-01-01' AND status = 'active'"
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono" />
          <p className="mt-1 text-[10px] text-muted-foreground flex items-center gap-1">
            <Info className="h-3 w-3" /> No semicolons or DDL keywords (DROP, ALTER, etc.) allowed
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={handleAnalyze} disabled={!rootTable || !connectionId || analyzing} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50">
            {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {analyzing ? "Analyzing..." : "Analyze (Dry Run)"}
          </button>
          {configId && (
            <button onClick={handleExecute} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              <Play className="h-4 w-4" /> Execute
            </button>
          )}
          {jobId && <span className="text-xs text-muted-foreground">Job: {jobId.slice(0, 8)}...</span>}
        </div>
      </div>

      <ConfigureTableDrawer
        open={configureTable !== null}
        onClose={() => setConfigureTable(null)}
        projectId={projectId}
        schemaId={null}
        tableName={configureTable ?? ""}
        initialTargetType="target_percentage"
        initialWhereFilter={configureTable === rootTable ? whereFilter : ""}
      />

      {/* Dry-run analysis results */}
      {analysis.length > 0 && (
        <div className="ant-scoped">
          <Table<AnalysisRow>
            columns={analysisColumns}
            dataSource={analysis}
            rowKey="table_name"
            pagination={false}
            size="small"
            summary={() => (
              <Table.Summary fixed>
                <Table.Summary.Row className="bg-muted/30 font-medium">
                  <Table.Summary.Cell index={0}>TOTAL</Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right">{analysis.reduce((s, r) => s + r.full_count, 0).toLocaleString()}</Table.Summary.Cell>
                  <Table.Summary.Cell index={2} align="right">{analysis.reduce((s, r) => s + r.subset_count, 0).toLocaleString()}</Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right" />
                </Table.Summary.Row>
              </Table.Summary>
            )}
          />
        </div>
      )}
    </div>
  );
}
