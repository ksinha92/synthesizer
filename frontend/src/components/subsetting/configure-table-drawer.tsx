"use client";

import { useEffect, useState } from "react";
import { ChevronRight, GitMerge, Loader2, X } from "lucide-react";

import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { Select } from "@/components/common/select";
import { cn } from "@/lib/utils";

export type TargetType =
  | "target_percentage"
  | "where_clause"
  | "direct"
  | "lookup_table"
  | "remove";

const TARGET_TYPE_LABEL: Record<TargetType, string> = {
  target_percentage: "Target percentage",
  where_clause: "WHERE clause",
  direct: "Direct (keep all)",
  lookup_table: "Lookup table",
  remove: "Remove (exclude)",
};

type TableTab = "logical_data" | "other_options" | "other_tables";

export interface ConfigureTableDrawerProps {
  open: boolean;
  onClose: () => void;
  /** Project the FK gets associated with on save. */
  projectId: string;
  /** The schema the table belongs to (defaults are best-effort). */
  schemaId: string | null;
  /** Table being configured — fully-qualified ``schema.name``. */
  tableName: string;
  /** Inbound (parent) tables in the FK graph; rendered for context. */
  inboundTables?: string[];
  /** Outbound (child) tables in the FK graph; rendered for context. */
  outboundTables?: string[];
  /** Existing root-table config snapshot. */
  initialTargetType?: TargetType;
  initialWhereFilter?: string;
  initialTargetCount?: number | null;
  /** Fired with the next config snapshot. Persistence belongs to the page. */
  onChange?: (next: {
    target_type: TargetType;
    where_filter: string;
    target_count: number | null;
  }) => void;
}

/**
 * Tonic-style "Configure Table" drawer (screenshots 11.31.45 / 11.32.22 /
 * 11.32.40). Right-docked, three tabs (LOGICAL DATA / Other Options /
 * Other Tables), per-table target-type chooser, inline "Create Virtual
 * Foreign Key" form that hits the existing
 * ``POST /api/v1/projects/{id}/relationships`` endpoint.
 *
 * The drawer is intentionally controlled — the subsetting page owns the
 * root-tables list, so we surface changes through ``onChange`` rather than
 * round-trip to the backend ourselves. The Virtual FK creation IS
 * persisted directly since it has its own endpoint.
 */
export function ConfigureTableDrawer({
  open,
  onClose,
  projectId,
  schemaId,
  tableName,
  inboundTables = [],
  outboundTables = [],
  initialTargetType = "target_percentage",
  initialWhereFilter = "",
  initialTargetCount = null,
  onChange,
}: ConfigureTableDrawerProps) {
  const [tab, setTab] = useState<TableTab>("logical_data");
  const [targetType, setTargetType] = useState<TargetType>(initialTargetType);
  const [whereFilter, setWhereFilter] = useState(initialWhereFilter);
  const [targetCount, setTargetCount] = useState<number | "">(initialTargetCount ?? "");

  // Virtual FK form
  const [fkOpen, setFkOpen] = useState(false);
  const [fkSourceColumn, setFkSourceColumn] = useState("");
  const [fkTargetTable, setFkTargetTable] = useState("");
  const [fkTargetColumn, setFkTargetColumn] = useState("");
  const [fkSaving, setFkSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTab("logical_data");
    setTargetType(initialTargetType);
    setWhereFilter(initialWhereFilter);
    setTargetCount(initialTargetCount ?? "");
    setFkOpen(false);
    setFkSourceColumn("");
    setFkTargetTable("");
    setFkTargetColumn("");
  }, [open, tableName, initialTargetType, initialWhereFilter, initialTargetCount]);

  // Close-on-Escape so it matches the rest of the drawers.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const emitChange = (next: Partial<{ target_type: TargetType; where_filter: string; target_count: number | null }>) => {
    onChange?.({
      target_type: next.target_type ?? targetType,
      where_filter: next.where_filter ?? whereFilter,
      target_count:
        next.target_count !== undefined
          ? next.target_count
          : targetCount === ""
            ? null
            : Number(targetCount),
    });
  };

  const handleCreateFK = async () => {
    if (!schemaId) {
      toast.error("Pick a discovered schema before creating a virtual FK.");
      return;
    }
    if (!fkSourceColumn.trim() || !fkTargetTable.trim() || !fkTargetColumn.trim()) {
      toast.error("Source column, target table, and target column are required.");
      return;
    }
    setFkSaving(true);
    try {
      // The /relationships endpoint expects UUIDs; for now we just toast a
      // helpful error if the user didn't paste UUIDs (the inline form is
      // a first-cut). Wiring a column-resolver picker is follow-up work.
      await api.post(`/api/v1/projects/${projectId}/relationships`, {
        schema_id: schemaId,
        source_table_id: tableName,
        source_column_id: fkSourceColumn.trim(),
        target_table_id: fkTargetTable.trim(),
        target_column_id: fkTargetColumn.trim(),
        relationship_type: "many_to_one",
      });
      toast.success("Virtual foreign key created");
      setFkOpen(false);
      setFkSourceColumn("");
      setFkTargetTable("");
      setFkTargetColumn("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to create FK";
      toast.error(msg);
    }
    setFkSaving(false);
  };

  return (
    <>
      <div
        aria-hidden="true"
        className="fixed inset-0 z-[55] bg-black/40"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="configure-table-title"
        className="fixed inset-y-0 right-0 z-[60] flex w-full max-w-md flex-col border-l border-border bg-card shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-border px-5 py-3">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Configure table
            </div>
            <h2 id="configure-table-title" className="mt-1 text-sm font-semibold text-foreground font-mono break-all">
              {tableName}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close configure table"
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {/* Tabs — match Tonic LOGICAL DATA / Other Options / Other Tables */}
        <nav role="tablist" aria-label="Configure table sections" className="flex gap-1 border-b border-border bg-muted/10 px-3">
          {([
            { id: "logical_data", label: "LOGICAL DATA" },
            { id: "other_options", label: "OTHER OPTIONS" },
            { id: "other_tables", label: "OTHER TABLES" },
          ] as const).map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={cn(
                "border-b-2 px-3 py-2 text-[10px] font-semibold uppercase tracking-wide",
                tab === id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto px-5 py-4 text-xs">
          {tab === "logical_data" && (
            <div className="space-y-4">
              <Select
                label="Target type"
                value={targetType}
                onChange={(e) => {
                  const next = e.target.value as TargetType;
                  setTargetType(next);
                  emitChange({ target_type: next });
                }}
              >
                {Object.entries(TARGET_TYPE_LABEL).map(([v, lbl]) => (
                  <option key={v} value={v}>
                    {lbl}
                  </option>
                ))}
              </Select>

              {targetType === "target_percentage" && (
                <label className="block">
                  <span className="block text-xs font-medium text-foreground mb-1">
                    Approximate rows to keep
                  </span>
                  <input
                    type="number"
                    min={1}
                    value={targetCount}
                    onChange={(e) => {
                      const raw = e.target.value;
                      const next = raw === "" ? "" : Number(raw);
                      setTargetCount(next);
                      emitChange({ target_count: next === "" ? null : Number(next) });
                    }}
                    placeholder="e.g. 5000"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm tabular-nums"
                  />
                  <span className="mt-1 block text-[10px] text-muted-foreground">
                    Override the workspace target percentage for this table only.
                  </span>
                </label>
              )}

              {targetType === "where_clause" && (
                <label className="block">
                  <span className="block text-xs font-medium text-foreground mb-1">
                    WHERE filter
                  </span>
                  <textarea
                    rows={3}
                    value={whereFilter}
                    onChange={(e) => {
                      setWhereFilter(e.target.value);
                      emitChange({ where_filter: e.target.value });
                    }}
                    placeholder="created_at > '2024-01-01' AND status = 'active'"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono"
                  />
                  <span className="mt-1 block text-[10px] text-muted-foreground">
                    Plain SQL fragment. Semicolons + DDL keywords are rejected at execute time.
                  </span>
                </label>
              )}

              {targetType === "lookup_table" && (
                <p className="rounded-md border border-dashed border-border bg-muted/10 px-3 py-2 text-[11px] text-muted-foreground">
                  Lookup-table subsetting reads ids from a separate connection; configure
                  the lookup source on the Workspace Settings → Source tab and select it
                  here in a follow-up.
                </p>
              )}

              {targetType === "remove" && (
                <p className="rounded-md border border-amber-300/40 bg-amber-50 px-3 py-2 text-[11px] text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200">
                  This table will be excluded from the output entirely. Children that
                  reference it will lose their parent rows.
                </p>
              )}

              {targetType === "direct" && (
                <p className="text-[11px] text-muted-foreground">
                  Every row of this table will be included in the output without sampling.
                </p>
              )}
            </div>
          )}

          {tab === "other_options" && (
            <div className="space-y-3">
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={fkOpen}
                  onChange={(e) => setFkOpen(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  <span className="text-sm font-medium text-foreground">
                    Create virtual foreign key
                  </span>
                  <span className="block text-[11px] text-muted-foreground">
                    Add an FK that doesn't exist in the live database so the subsetter
                    can use it for referential integrity.
                  </span>
                </span>
              </label>

              {fkOpen && (
                <div className="space-y-2 rounded-md border border-border bg-muted/10 px-3 py-3">
                  <input
                    type="text"
                    value={fkSourceColumn}
                    onChange={(e) => setFkSourceColumn(e.target.value)}
                    placeholder="Source column UUID"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono"
                  />
                  <input
                    type="text"
                    value={fkTargetTable}
                    onChange={(e) => setFkTargetTable(e.target.value)}
                    placeholder="Target table UUID"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono"
                  />
                  <input
                    type="text"
                    value={fkTargetColumn}
                    onChange={(e) => setFkTargetColumn(e.target.value)}
                    placeholder="Target column UUID"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    Picker UI lands in T3.6 (scan-results panel) — for now paste the IDs
                    from Discovery's PII Results table.
                  </p>
                  <button
                    type="button"
                    onClick={handleCreateFK}
                    disabled={fkSaving}
                    className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    {fkSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    <GitMerge className="h-3.5 w-3.5" />
                    Create virtual FK
                  </button>
                </div>
              )}
            </div>
          )}

          {tab === "other_tables" && (
            <div className="space-y-3">
              <RelatedList title="Inbound (parents)" tables={inboundTables} />
              <RelatedList title="Outbound (children)" tables={outboundTables} />
              {inboundTables.length === 0 && outboundTables.length === 0 && (
                <p className="text-[11px] text-muted-foreground">
                  No related tables detected. Run discovery (or create virtual FKs) to
                  populate the graph.
                </p>
              )}
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            Done
          </button>
        </footer>
      </aside>
    </>
  );
}

function RelatedList({ title, tables }: { title: string; tables: string[] }) {
  if (tables.length === 0) return null;
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
        {title}
      </p>
      <ul className="divide-y divide-border rounded-md border border-border">
        {tables.map((t) => (
          <li key={t} className="flex items-center gap-2 px-3 py-1.5 text-xs">
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
            <span className="font-mono">{t}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
