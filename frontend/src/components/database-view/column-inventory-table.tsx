"use client";

import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronRight,
  Download,
  Loader2,
  ShieldCheck,
  ShieldOff,
} from "lucide-react";

import { Select } from "@/components/common/select";
import { cn } from "@/lib/utils";
import type { ColumnRow, PresetChoice, RuleAction, SortKey } from "./types";

const NONE_OPTION = "__none__";
const PRESET_PREFIX = "preset:";

interface ColumnInventoryTableProps {
  rows: ColumnRow[];
  presets: PresetChoice[];
  generatorChoices: string[];
  updatingId: string | null;
  /** Per-row apply — translates the dropdown value into a RuleAction. */
  onApply: (col: ColumnRow, action: RuleAction) => Promise<void> | void;
  /** Bulk apply called with the selected column ids + chosen generator. */
  onBulkApply?: (
    columnIds: string[],
    action: { masking_type?: string; preset_id?: string },
  ) => Promise<void> | void;
  /** When true (default), renders the connector-type column. */
  showConnectorColumn?: boolean;
  /** Optional: tells the table what label to use for the bulk button. */
  bulkButtonLabel?: string;
}

/**
 * Shared column inventory: sortable headers, bulk select via checkbox column,
 * per-row generator dropdown, CSV export. Used by both the Database Viewer
 * and File Viewer tabs so changes to row rendering ship once.
 */
export function ColumnInventoryTable({
  rows,
  presets,
  generatorChoices,
  updatingId,
  onApply,
  onBulkApply,
  showConnectorColumn = true,
  bulkButtonLabel = "Apply to selected",
}: ColumnInventoryTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("column");
  const [sortDesc, setSortDesc] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkValue, setBulkValue] = useState<string>(NONE_OPTION);
  const [bulkBusy, setBulkBusy] = useState(false);

  const sortedRows = useMemo(() => {
    const sorted = [...rows];
    const dir = sortDesc ? -1 : 1;
    sorted.sort((a, b) => dir * compareRows(a, b, sortKey));
    return sorted;
  }, [rows, sortKey, sortDesc]);

  const allVisibleSelected =
    sortedRows.length > 0 && sortedRows.every((r) => selected.has(r.column_id));

  const toggleAll = (checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const r of sortedRows) {
        if (checked) next.add(r.column_id);
        else next.delete(r.column_id);
      }
      return next;
    });
  };

  const toggleOne = (id: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(key);
      setSortDesc(false);
    }
  };

  const handleBulkApply = async () => {
    if (!onBulkApply || selected.size === 0 || bulkValue === NONE_OPTION) return;
    const ids = Array.from(selected);
    setBulkBusy(true);
    try {
      if (bulkValue.startsWith(PRESET_PREFIX)) {
        await onBulkApply(ids, { preset_id: bulkValue.slice(PRESET_PREFIX.length) });
      } else {
        await onBulkApply(ids, { masking_type: bulkValue });
      }
      setSelected(new Set());
      setBulkValue(NONE_OPTION);
    } finally {
      setBulkBusy(false);
    }
  };

  const exportCsv = () => {
    const header = [
      "connection_type",
      "connection_name",
      "schema",
      "table",
      "column",
      "data_type",
      "pii_type",
      "pii_confidence",
      "status",
      "generator",
    ].join(",");
    const lines = sortedRows.map((r) =>
      [
        r.connector_type,
        r.connection_name,
        r.schema_name,
        r.table_name,
        r.column_name,
        r.data_type,
        r.pii_type,
        r.pii_confidence ?? "",
        r.status,
        r.current_generator ?? "",
      ]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(","),
    );
    const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "column-inventory.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const showBulkBar = !!onBulkApply && selected.size > 0;

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {showBulkBar && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/30 px-4 py-2 text-xs">
          <span className="text-muted-foreground">
            {selected.size} column{selected.size === 1 ? "" : "s"} selected
          </span>
          <Select
            aria-label="Bulk generator selection"
            fullWidth={false}
            value={bulkValue}
            onChange={(e) => setBulkValue(e.target.value)}
            className="min-w-[180px]"
          >
            <option value={NONE_OPTION}>— Choose generator —</option>
            {presets.length > 0 && (
              <optgroup label="Presets">
                {presets.map((p) => (
                  <option key={p.id} value={`${PRESET_PREFIX}${p.id}`}>
                    {p.name} ({p.generator_type})
                  </option>
                ))}
              </optgroup>
            )}
            <optgroup label="Generators">
              {generatorChoices.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </optgroup>
          </Select>
          <button
            type="button"
            disabled={bulkValue === NONE_OPTION || bulkBusy}
            onClick={handleBulkApply}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-[11px] font-medium text-primary-foreground disabled:opacity-50"
          >
            {bulkBusy && <Loader2 className="h-3 w-3 animate-spin" />}
            {bulkButtonLabel}
          </button>
          <button
            type="button"
            onClick={() => setSelected(new Set())}
            className="text-[11px] text-muted-foreground hover:text-foreground"
          >
            Clear selection
          </button>
        </div>
      )}
      <div className="flex items-center justify-between border-b border-border bg-muted/20 px-4 py-1.5 text-[11px] text-muted-foreground">
        <span>
          {sortedRows.length} row{sortedRows.length === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          onClick={exportCsv}
          className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 hover:bg-muted/40"
          aria-label="Export current view as CSV"
        >
          <Download className="h-3 w-3" />
          Export CSV
        </button>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-muted/40">
          <tr className="text-left text-xs text-muted-foreground">
            {onBulkApply && (
              <th className="w-8 px-2 py-2">
                <input
                  type="checkbox"
                  aria-label="Select all visible columns"
                  checked={allVisibleSelected}
                  onChange={(e) => toggleAll(e.target.checked)}
                />
              </th>
            )}
            <SortableHeader
              label="Column"
              active={sortKey === "column"}
              desc={sortDesc}
              onClick={() => handleSort("column")}
            />
            <SortableHeader
              label="Type"
              active={sortKey === "type"}
              desc={sortDesc}
              onClick={() => handleSort("type")}
            />
            <SortableHeader
              label="Sensitivity"
              active={sortKey === "pii"}
              desc={sortDesc}
              onClick={() => handleSort("pii")}
            />
            <SortableHeader
              label="Status"
              active={sortKey === "status"}
              desc={sortDesc}
              onClick={() => handleSort("status")}
            />
            {showConnectorColumn && (
              <th className="px-4 py-2 font-medium">Source</th>
            )}
            <th className="px-4 py-2 font-medium">Generator</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sortedRows.map((col) => (
            <tr key={col.column_id} className="hover:bg-muted/20">
              {onBulkApply && (
                <td className="px-2 py-2">
                  <input
                    type="checkbox"
                    aria-label={`Select ${col.column_name}`}
                    checked={selected.has(col.column_id)}
                    onChange={(e) => toggleOne(col.column_id, e.target.checked)}
                  />
                </td>
              )}
              <td className="px-4 py-2">
                <p className="font-mono text-[12px] text-foreground">{col.column_name}</p>
                <p className="text-[10px] text-muted-foreground">
                  {col.schema_name} / {col.table_name}
                </p>
              </td>
              <td className="px-4 py-2 font-mono text-[11px] text-muted-foreground">
                {col.data_type}
                {col.mixed_types && col.mixed_types.length > 1 && (
                  <span
                    className="ml-1 inline-flex items-center rounded bg-amber-500/10 px-1 py-px text-[9px] uppercase text-amber-700 dark:text-amber-300"
                    title={`Sampled types: ${col.mixed_types.join(", ")}`}
                  >
                    mixed
                  </span>
                )}
              </td>
              <td className="px-4 py-2 text-xs">
                {col.pii_type === "none" ? (
                  <span className="text-muted-foreground">—</span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-700 dark:text-amber-300">
                    {col.pii_type}
                    {col.pii_confidence !== null && col.pii_confidence !== undefined && (
                      <span className="opacity-70 text-[10px]">
                        ({Math.round(col.pii_confidence * 100)}%)
                      </span>
                    )}
                  </span>
                )}
              </td>
              <td className="px-4 py-2 text-xs">
                <StatusPill status={col.status} />
              </td>
              {showConnectorColumn && (
                <td className="px-4 py-2 text-[11px] text-muted-foreground" title={col.connection_name}>
                  <p className="font-mono text-[10px] uppercase">{col.connector_type}</p>
                  <p className="truncate max-w-[140px]">{col.connection_name}</p>
                </td>
              )}
              <td className="px-4 py-2">
                <div className="flex items-center gap-2">
                  <Select
                    aria-label={`Generator for ${col.column_name}`}
                    fullWidth={false}
                    disabled={updatingId === col.column_id}
                    value={
                      col.current_preset_id
                        ? `${PRESET_PREFIX}${col.current_preset_id}`
                        : col.current_generator || NONE_OPTION
                    }
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === NONE_OPTION) {
                        void onApply(col, { type: "clear" });
                      } else if (v.startsWith(PRESET_PREFIX)) {
                        void onApply(col, {
                          type: "set_preset",
                          value: v.slice(PRESET_PREFIX.length),
                        });
                      } else {
                        void onApply(col, { type: "set_generator", value: v });
                      }
                    }}
                    className="min-w-[180px]"
                  >
                    <option value={NONE_OPTION}>— No rule —</option>
                    {presets.length > 0 && (
                      <optgroup label="Presets">
                        {presets.map((p) => (
                          <option key={p.id} value={`${PRESET_PREFIX}${p.id}`}>
                            {p.name} ({p.generator_type})
                          </option>
                        ))}
                      </optgroup>
                    )}
                    <optgroup label="Generators">
                      {generatorChoices.map((g) => (
                        <option key={g} value={g}>
                          {g}
                        </option>
                      ))}
                    </optgroup>
                  </Select>
                  {updatingId === col.column_id && (
                    <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  )}
                </div>
              </td>
            </tr>
          ))}
          {sortedRows.length === 0 && (
            <tr>
              <td
                colSpan={showConnectorColumn ? 7 : 6}
                className="px-4 py-6 text-center text-xs text-muted-foreground"
              >
                No columns match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function compareRows(a: ColumnRow, b: ColumnRow, key: SortKey) {
  switch (key) {
    case "column":
      return (
        a.connection_name.localeCompare(b.connection_name) ||
        a.schema_name.localeCompare(b.schema_name) ||
        a.table_name.localeCompare(b.table_name) ||
        a.column_name.localeCompare(b.column_name)
      );
    case "type":
      return a.data_type.localeCompare(b.data_type);
    case "pii":
      return (b.pii_confidence ?? 0) - (a.pii_confidence ?? 0);
    case "status": {
      const order = { protected: 0, unprotected: 1, not_sensitive: 2 } as const;
      return order[a.status] - order[b.status];
    }
    default:
      return 0;
  }
}

function SortableHeader({
  label,
  active,
  desc,
  onClick,
}: {
  label: string;
  active: boolean;
  desc: boolean;
  onClick: () => void;
}) {
  return (
    <th className="px-4 py-2 font-medium">
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1",
          active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
        )}
      >
        {label}
        {active ? (
          desc ? (
            <ArrowDown className="h-3 w-3" />
          ) : (
            <ArrowUp className="h-3 w-3" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-50" />
        )}
      </button>
    </th>
  );
}

function StatusPill({ status }: { status: ColumnRow["status"] }) {
  if (status === "protected") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-[hsl(var(--dw-pill-success)/0.15)] px-2 py-0.5 text-[hsl(var(--dw-pill-success))]">
        <ShieldCheck className="h-3 w-3" />
        Protected
      </span>
    );
  }
  if (status === "unprotected") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-[hsl(var(--dw-pill-warning)/0.15)] px-2 py-0.5 text-[hsl(var(--dw-pill-warning))]">
        <ShieldOff className="h-3 w-3" />
        Unprotected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
      <ChevronRight className="h-3 w-3" />
      Not sensitive
    </span>
  );
}
