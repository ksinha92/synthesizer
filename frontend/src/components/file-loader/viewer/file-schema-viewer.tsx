"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { api } from "@/hooks/use-api";

import { FieldDetailPanel } from "./field-detail-panel";
import { LayoutSwitcher } from "./layout-switcher";
import { SampleDataGrid } from "./sample-data-grid";
import { SchemaStructureTree } from "./schema-structure-tree";
import type { FileSchemaDetail, PreviewResponse } from "../types";

interface FileSchemaViewerProps {
  projectId: string;
  schemaId: string;
  /** Optional preloaded detail to skip the GET round-trip. */
  initialSchema?: FileSchemaDetail;
}

/**
 * Three-pane Microfocus-style viewer:
 *   ┌──────────────┬──────────────┬────────────┐
 *   │ structure    │ sample grid  │ field      │
 *   │ tree         │ (formatted   │ detail     │
 *   │              │  ↔ character)│            │
 *   └──────────────┴──────────────┴────────────┘
 *
 * A layout switcher above the structure tree picks which variant's
 * field list is on screen; the sample grid stays anchored to the full
 * schema so all parsed rows remain visible.
 */
export function FileSchemaViewer({
  projectId,
  schemaId,
  initialSchema,
}: FileSchemaViewerProps) {
  const [schema, setSchema] = useState<FileSchemaDetail | null>(
    initialSchema ?? null,
  );
  const [loading, setLoading] = useState(!initialSchema);
  const [error, setError] = useState<string | null>(null);
  const [layoutName, setLayoutName] = useState<string>("_base");
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);

  useEffect(() => {
    if (initialSchema) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const detail = await api.get<FileSchemaDetail>(
          `/api/v1/projects/${projectId}/synthetic/file-schemas/${schemaId}`,
        );
        if (!cancelled) setSchema(detail);
      } catch (e) {
        if (!cancelled) setError((e as Error).message || "Failed to load schema");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, schemaId, initialSchema]);

  // The list endpoint serves summaries; viewer needs the full detail
  // which lives on the upload responses + the layout-variants PATCH
  // response. When the parent only has a summary we fall back to the
  // upload-derived schema after a re-upload, or we can re-fetch via the
  // synthetic_file_schemas GET — added above for completeness.

  const activeFields = useMemo(() => {
    if (!schema) return [];
    if (layoutName === "_base") return schema.fields;
    const variant = schema.layout_variants.find((v) => v.name === layoutName);
    return variant?.fields ?? schema.fields;
  }, [schema, layoutName]);

  const selectedFieldDef = useMemo(() => {
    if (!selectedField) return null;
    return activeFields.find((f) => f.name === selectedField) ?? null;
  }, [activeFields, selectedField]);

  const sampleValuesForField = useMemo(() => {
    if (!preview || !selectedField) return [];
    return preview.rows
      .map((r) => r.fields[selectedField])
      .filter((v) => v !== undefined);
  }, [preview, selectedField]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-6 text-xs text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading schema…
      </div>
    );
  }
  if (error || !schema) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-xs text-destructive">
        {error ?? "Schema not found"}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-base font-semibold text-foreground">{schema.name}</h2>
        <span className="text-[11px] text-muted-foreground">
          <span className="font-mono">{schema.file_format}</span>
          {" • "}
          <span className="font-mono">{schema.encoding}</span>
          {" • "}
          {schema.field_count} field{schema.field_count === 1 ? "" : "s"}
          {" • "}
          record length {schema.record_length} bytes
          {schema.layout_variants.length > 0 && (
            <>
              {" "}
              • {schema.layout_variants.length} variant
              {schema.layout_variants.length === 1 ? "" : "s"}
            </>
          )}
        </span>
      </header>

      <LayoutSwitcher
        variants={schema.layout_variants}
        selected={layoutName}
        onSelect={(name) => {
          setLayoutName(name);
          setSelectedField(null);
        }}
      />

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)_minmax(0,1fr)]">
        <SchemaStructureTree
          fields={activeFields}
          selected={selectedField}
          onSelect={setSelectedField}
        />
        <SampleDataGrid
          projectId={projectId}
          schema={schema}
          onPreviewLoaded={setPreview}
        />
        <FieldDetailPanel
          field={selectedFieldDef}
          sampleValues={sampleValuesForField}
        />
      </div>
    </div>
  );
}
