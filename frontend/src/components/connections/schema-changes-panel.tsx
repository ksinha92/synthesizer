"use client";

import { useState } from "react";
import { GitCommitVertical, Loader2, RefreshCw } from "lucide-react";

import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface TableDiff {
  schema_name: string;
  table_name: string;
  change: "added" | "removed";
}

interface ColumnDiff {
  schema_name: string;
  table_name: string;
  column_name: string;
  change: "added" | "removed" | "type_changed";
  old_data_type: string | null;
  new_data_type: string | null;
}

interface SchemaDiff {
  connection_id: string;
  last_discovered_at: string | null;
  added_tables: TableDiff[];
  removed_tables: TableDiff[];
  added_columns: ColumnDiff[];
  removed_columns: ColumnDiff[];
  changed_columns: ColumnDiff[];
}

interface SchemaChangesPanelProps {
  projectId: string;
  connectionId: string;
  connectionName: string;
}

export function SchemaChangesPanel({
  projectId,
  connectionId,
  connectionName,
}: SchemaChangesPanelProps) {
  const [diff, setDiff] = useState<SchemaDiff | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const d = await api.get<SchemaDiff>(
        `/api/v1/projects/${projectId}/discovery/diff?connection_id=${connectionId}`
      );
      setDiff(d);
    } catch {
      toast.error("Schema diff failed — is the connection reachable?");
      setDiff(null);
    }
    setLoading(false);
  };

  const totalChanges =
    (diff?.added_tables.length ?? 0) +
    (diff?.removed_tables.length ?? 0) +
    (diff?.added_columns.length ?? 0) +
    (diff?.removed_columns.length ?? 0) +
    (diff?.changed_columns.length ?? 0);

  return (
    <section className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitCommitVertical className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">
            Schema changes — {connectionName}
          </h3>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs hover:bg-muted disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
          {diff ? "Re-check" : "Check"}
        </button>
      </div>

      {diff === null && !loading && (
        <p className="text-xs text-muted-foreground">
          Click <strong>Check</strong> to compare the latest persisted discovery
          against the live source. Read-only — nothing is modified.
        </p>
      )}

      {diff && (
        <>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>
              Last discovered:{" "}
              {diff.last_discovered_at
                ? new Date(diff.last_discovered_at).toLocaleString()
                : "never"}
            </span>
            <span>•</span>
            <span>
              {totalChanges === 0
                ? "No changes detected"
                : `${totalChanges} change${totalChanges === 1 ? "" : "s"}`}
            </span>
          </div>

          {totalChanges > 0 && (
            <div className="space-y-2 text-xs">
              {diff.added_tables.length > 0 && (
                <DiffGroup
                  label="Tables added"
                  color="bg-[hsl(var(--dw-pill-success)/0.15)] text-[hsl(var(--dw-pill-success))]"
                  items={diff.added_tables.map((t) => `${t.schema_name}.${t.table_name}`)}
                />
              )}
              {diff.removed_tables.length > 0 && (
                <DiffGroup
                  label="Tables removed"
                  color="bg-[hsl(var(--dw-pill-danger)/0.15)] text-[hsl(var(--dw-pill-danger))]"
                  items={diff.removed_tables.map((t) => `${t.schema_name}.${t.table_name}`)}
                />
              )}
              {diff.added_columns.length > 0 && (
                <DiffGroup
                  label="Columns added"
                  color="bg-[hsl(var(--dw-pill-success)/0.15)] text-[hsl(var(--dw-pill-success))]"
                  items={diff.added_columns.map(
                    (c) => `${c.schema_name}.${c.table_name}.${c.column_name} (${c.new_data_type})`
                  )}
                />
              )}
              {diff.removed_columns.length > 0 && (
                <DiffGroup
                  label="Columns removed"
                  color="bg-[hsl(var(--dw-pill-danger)/0.15)] text-[hsl(var(--dw-pill-danger))]"
                  items={diff.removed_columns.map(
                    (c) => `${c.schema_name}.${c.table_name}.${c.column_name}`
                  )}
                />
              )}
              {diff.changed_columns.length > 0 && (
                <DiffGroup
                  label="Columns with type changes"
                  color="bg-[hsl(var(--dw-pill-warning)/0.15)] text-[hsl(var(--dw-pill-warning))]"
                  items={diff.changed_columns.map(
                    (c) =>
                      `${c.schema_name}.${c.table_name}.${c.column_name}: ${c.old_data_type} → ${c.new_data_type}`
                  )}
                />
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function DiffGroup({
  label,
  color,
  items,
}: {
  label: string;
  color: string;
  items: string[];
}) {
  return (
    <div>
      <p className={`inline-block rounded-full px-2 py-0.5 ${color} mb-1`}>{label}</p>
      <ul className="ml-3 space-y-0.5 text-foreground font-mono text-[11px]">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
