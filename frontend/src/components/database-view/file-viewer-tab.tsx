"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Eye,
  FileText,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Workflow,
} from "lucide-react";

import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

import { ColumnInventoryTable } from "./column-inventory-table";
import { SchemaTree } from "./schema-tree";
import { useDebounced } from "./use-debounced";
import type {
  BulkRuleResponse,
  ColumnRow,
  DatabaseViewResponse,
  RuleAction,
} from "./types";

import { DictionaryMapperModal } from "@/components/file-loader/dictionary/dictionary-mapper-modal";
import { SuggestRelationshipsModal } from "@/components/file-loader/relationships/suggest-relationships-modal";
import { FileSchemaViewer } from "@/components/file-loader/viewer/file-schema-viewer";
import { FileLoaderWizard } from "@/components/file-loader/wizard/file-loader-wizard";

interface FileViewerTabProps {
  projectId: string;
}

const PAGE_SIZE = 500;

/**
 * File Viewer tab — surfaces the project's uploaded file schemas (CSV,
 * COBOL copybook, Excel data dictionary, Parquet, VSAM) through the same
 * column inventory used by the Database Viewer tab. Masking rules persist
 * via the file-schema-specific endpoints so they're carried into synthetic
 * file generation.
 */
export function FileViewerTab({ projectId }: FileViewerTabProps) {
  const [data, setData] = useState<DatabaseViewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput, 300);
  const [selectedTable, setSelectedTable] = useState<
    { connection_id: string; schema_name: string; table_name: string } | null
  >(null);
  // Modal + viewer state for the enterprise file-loader add-ons.
  const [wizardOpen, setWizardOpen] = useState(false);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [mapperOpen, setMapperOpen] = useState(false);
  const [viewerSchemaId, setViewerSchemaId] = useState<string | null>(null);

  const fetchPage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.get<DatabaseViewResponse>(
        `/api/v1/projects/${projectId}/file-schemas/columns?limit=${PAGE_SIZE}`,
      );
      setData(d);
    } catch (e) {
      setError((e as Error).message || "Failed to load file schemas");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

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
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (c) =>
          c.column_name.toLowerCase().includes(q) ||
          c.connection_name.toLowerCase().includes(q) ||
          (c.pii_type ?? "").toLowerCase().includes(q),
      );
    }
    return rows;
  }, [data, selectedTable, search]);

  const applyAction = async (col: ColumnRow, action: RuleAction) => {
    setUpdating(col.column_id);
    try {
      // For file fields, the column_id is a synthesized uuid5 — the
      // canonical identity is (file_schema_id, field_name). The endpoints
      // accept that pair so re-edits to the schema preserve rules.
      const fileSchemaId = col.connection_id; // we stash the schema id here
      const fieldName = col.column_name;
      if (action.type === "clear") {
        const params = new URLSearchParams({
          file_schema_id: fileSchemaId,
          field_name: fieldName,
        });
        await api.del(
          `/api/v1/projects/${projectId}/file-schemas/columns/rule?${params}`,
        );
        toast.success(`Cleared rule on ${fieldName}`);
      } else if (action.type === "set_preset" && action.value) {
        await api.post(
          `/api/v1/projects/${projectId}/file-schemas/columns/rule`,
          {
            file_schema_id: fileSchemaId,
            field_name: fieldName,
            preset_id: action.value,
          },
        );
        const name = data?.presets.find((p) => p.id === action.value)?.name || action.value;
        toast.success(`Set ${fieldName} → preset ${name}`);
      } else if (action.type === "set_generator" && action.value) {
        await api.post(
          `/api/v1/projects/${projectId}/file-schemas/columns/rule`,
          {
            file_schema_id: fileSchemaId,
            field_name: fieldName,
            masking_type: action.value,
          },
        );
        toast.success(`Set ${fieldName} → ${action.value}`);
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
    if (!data) return;
    const byId = new Map(data.columns.map((c) => [c.column_id, c]));
    const fields = ids
      .map((id) => byId.get(id))
      .filter((c): c is ColumnRow => !!c)
      .map((c) => ({
        file_schema_id: c.connection_id,
        field_name: c.column_name,
      }));
    if (fields.length === 0) return;
    try {
      const res = await api.post<BulkRuleResponse>(
        `/api/v1/projects/${projectId}/file-schemas/columns/bulk-rule`,
        { fields, ...payload },
      );
      toast.success(
        `Applied to ${res.applied} field${res.applied === 1 ? "" : "s"}` +
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
      <>
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground space-y-3">
          <div className="flex items-center gap-2 text-foreground">
            <FileText className="h-4 w-4" />
            <span className="font-medium">No file schemas yet</span>
          </div>
          <p>
            Import a COBOL copybook, upload an Excel data dictionary, or build a
            schema manually. Multi-record layouts and EBCDIC/VSAM are supported.
          </p>
          <button
            type="button"
            onClick={() => setWizardOpen(true)}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
          >
            <Plus className="h-3 w-3" /> Add file schema
          </button>
        </div>
        <FileLoaderWizard
          projectId={projectId}
          open={wizardOpen}
          onClose={() => setWizardOpen(false)}
          onSchemaCreated={() => {
            setWizardOpen(false);
            void fetchPage();
          }}
        />
      </>
    );
  }

  const distinctSchemaIds = new Set(data.columns.map((c) => c.connection_id));

  // Translate the selected "table" (which the column inventory uses) into a
  // file_schema_id we can hand to the viewer. The File Viewer back end stores
  // the schema id as the row's connection_id.
  const selectedSchemaId = selectedTable?.connection_id ?? null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="grow text-xs text-muted-foreground">
          {data.total_count} field{data.total_count === 1 ? "" : "s"} across
          {" "}
          {distinctSchemaIds.size} file schema(s)
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Filter fields…"
            className="w-56 rounded-md border border-input bg-background pl-7 pr-2 py-1.5 text-xs"
          />
        </div>
        <button
          type="button"
          onClick={() => setWizardOpen(true)}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-[11px] font-medium text-primary-foreground"
        >
          <Plus className="h-3 w-3" /> Add file schema
        </button>
        <button
          type="button"
          onClick={() => setSuggestOpen(true)}
          disabled={distinctSchemaIds.size < 2}
          title={
            distinctSchemaIds.size < 2
              ? "Need at least two file schemas to suggest relationships"
              : "Suggest cross-file relationships"
          }
          className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-[11px] hover:bg-muted/40 disabled:opacity-50"
        >
          <Link2 className="h-3 w-3" /> Suggest relationships
        </button>
        <button
          type="button"
          onClick={() => setMapperOpen(true)}
          disabled={distinctSchemaIds.size === 0}
          className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-[11px] hover:bg-muted/40 disabled:opacity-50"
        >
          <Workflow className="h-3 w-3" /> Map to dictionary
        </button>
        <button
          type="button"
          onClick={() => setViewerSchemaId(selectedSchemaId)}
          disabled={!selectedSchemaId}
          title={
            selectedSchemaId
              ? "Open the selected schema in the structured viewer"
              : "Pick a schema in the tree to open its viewer"
          }
          className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-[11px] hover:bg-muted/40 disabled:opacity-50"
        >
          <Eye className="h-3 w-3" /> Open in viewer
        </button>
        {loading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
      </div>

      {viewerSchemaId && (
        <div className="space-y-2">
          <FileSchemaViewer projectId={projectId} schemaId={viewerSchemaId} />
          <div className="text-right">
            <button
              type="button"
              onClick={() => setViewerSchemaId(null)}
              className="text-[11px] text-muted-foreground hover:text-foreground"
            >
              Close viewer
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
        <SchemaTree
          columns={data.columns}
          selected={selectedTable}
          onSelect={setSelectedTable}
          groupByConnection={false}
          allLabel="All file schemas"
        />
        <ColumnInventoryTable
          rows={filtered}
          presets={data.presets}
          generatorChoices={data.generator_choices}
          updatingId={updating}
          onApply={applyAction}
          onBulkApply={bulkApply}
          bulkButtonLabel="Apply to selected fields"
        />
      </div>

      <FileLoaderWizard
        projectId={projectId}
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onSchemaCreated={() => {
          setWizardOpen(false);
          void fetchPage();
        }}
      />
      <SuggestRelationshipsModal
        projectId={projectId}
        open={suggestOpen}
        onClose={() => setSuggestOpen(false)}
      />
      <DictionaryMapperModal
        projectId={projectId}
        open={mapperOpen}
        onClose={() => {
          setMapperOpen(false);
          void fetchPage();
        }}
        sourceSchemaId={selectedSchemaId ?? undefined}
      />
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
