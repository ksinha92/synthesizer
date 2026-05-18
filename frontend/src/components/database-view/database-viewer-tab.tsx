"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Loader2, RefreshCw, Search } from "lucide-react";

import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { Select } from "@/components/common/select";
import { Pagination } from "@/components/common/pagination";

import { ColumnInventoryTable } from "./column-inventory-table";
import { SchemaTree } from "./schema-tree";
import { useDebounced } from "./use-debounced";
import type {
  BulkRuleResponse,
  ColumnRow,
  DatabaseViewResponse,
  RuleAction,
} from "./types";

interface DatabaseViewerTabProps {
  projectId: string;
}

const PAGE_SIZE = 500;

/**
 * Database Viewer tab. Owns its own pagination + filter state so a heavy
 * project (thousands of columns) doesn't pin the entire response in
 * memory. Each fetch sends ``offset``/``limit`` and a connection filter so
 * the backend can scope the JOIN to one source when a tree node is picked.
 */
export function DatabaseViewerTab({ projectId }: DatabaseViewerTabProps) {
  const [data, setData] = useState<DatabaseViewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<
    { connection_id: string; schema_name: string; table_name: string } | null
  >(null);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput, 300);
  const [statusFilter, setStatusFilter] = useState<
    "all" | "protected" | "unprotected" | "not_sensitive"
  >("all");
  const [updating, setUpdating] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [connectionFilter, setConnectionFilter] = useState<string | null>(null);

  const fetchPage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String((page - 1) * PAGE_SIZE),
      });
      if (connectionFilter) params.set("connection_id", connectionFilter);
      const d = await api.get<DatabaseViewResponse>(
        `/api/v1/projects/${projectId}/database?${params.toString()}`,
      );
      setData(d);
    } catch (e) {
      setError((e as Error).message || "Failed to load Database View");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [projectId, page, connectionFilter]);

  useEffect(() => {
    void fetchPage();
  }, [fetchPage]);

  const filtered = useMemo<ColumnRow[]>(() => {
    if (!data) return [];
    let rows = data.columns;
    if (selectedTable) {
      rows = rows.filter(
        (c) =>
          c.connection_id === selectedTable.connection_id &&
          c.schema_name === selectedTable.schema_name &&
          c.table_name === selectedTable.table_name,
      );
    }
    if (statusFilter !== "all") {
      rows = rows.filter((c) => c.status === statusFilter);
    }
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (c) =>
          c.column_name.toLowerCase().includes(q) ||
          c.table_name.toLowerCase().includes(q) ||
          c.pii_type.toLowerCase().includes(q) ||
          c.connection_name.toLowerCase().includes(q),
      );
    }
    return rows;
  }, [data, selectedTable, statusFilter, search]);

  // Build the connection filter dropdown from whatever connections are
  // visible in the current page. Picking one re-fetches scoped to that
  // connection so the rest of the project's columns don't crowd the tree.
  const connectionOptions = useMemo(() => {
    if (!data) return [];
    const seen = new Map<string, { id: string; name: string; type: string }>();
    for (const c of data.columns) {
      if (!seen.has(c.connection_id)) {
        seen.set(c.connection_id, {
          id: c.connection_id,
          name: c.connection_name,
          type: c.connector_type,
        });
      }
    }
    return Array.from(seen.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [data]);

  const applyAction = async (col: ColumnRow, action: RuleAction) => {
    setUpdating(col.column_id);
    try {
      if (action.type === "clear") {
        await api.del(
          `/api/v1/projects/${projectId}/database/columns/${col.column_id}/rule`,
        );
        toast.success(`Cleared rule on ${col.column_name}`);
      } else if (action.type === "set_preset" && action.value) {
        await api.post(
          `/api/v1/projects/${projectId}/database/columns/${col.column_id}/rule`,
          { preset_id: action.value },
        );
        const name = data?.presets.find((p) => p.id === action.value)?.name || action.value;
        toast.success(`Set ${col.column_name} → preset ${name}`);
      } else if (action.type === "set_generator" && action.value) {
        await api.post(
          `/api/v1/projects/${projectId}/database/columns/${col.column_id}/rule`,
          { masking_type: action.value },
        );
        toast.success(`Set ${col.column_name} → ${action.value}`);
      }
      await fetchPage();
    } catch {
      toast.error("Update failed.");
    } finally {
      setUpdating(null);
    }
  };

  const bulkApply = async (
    ids: string[],
    payload: { masking_type?: string; preset_id?: string },
  ) => {
    try {
      const res = await api.post<BulkRuleResponse>(
        `/api/v1/projects/${projectId}/database/columns/bulk-rule`,
        { column_ids: ids, ...payload },
      );
      toast.success(
        `Applied to ${res.applied} column${res.applied === 1 ? "" : "s"}` +
          (res.skipped ? ` (${res.skipped} skipped)` : ""),
      );
      await fetchPage();
    } catch {
      toast.error("Bulk update failed.");
    }
  };

  if (loading && !data) {
    return <ViewerSkeleton />;
  }
  if (error) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
        <div className="flex items-center gap-2 text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
        <button
          type="button"
          onClick={() => void fetchPage()}
          className="mt-3 inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-xs hover:bg-muted/40"
        >
          <RefreshCw className="h-3 w-3" />
          Retry
        </button>
      </div>
    );
  }
  if (!data || data.total_count === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
        Database View unavailable — run discovery on a connection to populate.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="grow text-xs text-muted-foreground">
          Showing {data.columns.length} of {data.total_count} column
          {data.total_count === 1 ? "" : "s"}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Filter columns…"
            className="w-56 rounded-md border border-input bg-background pl-7 pr-2 py-1.5 text-xs"
          />
        </div>
        <Select
          aria-label="Filter by protection status"
          fullWidth={false}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          className="min-w-[160px]"
        >
          <option value="all">All statuses</option>
          <option value="protected">Protected</option>
          <option value="unprotected">Unprotected</option>
          <option value="not_sensitive">Not sensitive</option>
        </Select>
        {connectionOptions.length > 1 && (
          <Select
            aria-label="Filter by connection"
            fullWidth={false}
            value={connectionFilter ?? ""}
            onChange={(e) => {
              setConnectionFilter(e.target.value || null);
              setPage(1);
              setSelectedTable(null);
            }}
            className="min-w-[200px]"
          >
            <option value="">All connections</option>
            {connectionOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type})
              </option>
            ))}
          </Select>
        )}
        {loading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
        <SchemaTree
          columns={data.columns}
          selected={selectedTable}
          onSelect={setSelectedTable}
        />
        <ColumnInventoryTable
          rows={filtered}
          presets={data.presets}
          generatorChoices={data.generator_choices}
          updatingId={updating}
          onApply={applyAction}
          onBulkApply={bulkApply}
        />
      </div>

      {data.total_count > PAGE_SIZE && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          totalCount={data.total_count}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}

function ViewerSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 w-48 rounded bg-muted/40" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
        <div className="h-96 rounded-lg border border-border bg-muted/40" />
        <div className="h-96 rounded-lg border border-border bg-muted/40" />
      </div>
    </div>
  );
}
