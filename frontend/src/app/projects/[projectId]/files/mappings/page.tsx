"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, Plus, Workflow } from "lucide-react";

import { api } from "@/hooks/use-api";

import { DictionaryMapperModal } from "@/components/file-loader/dictionary/dictionary-mapper-modal";
import type { FileSchemaSummary } from "@/components/file-loader/types";

interface DerivedSchemaSummary extends FileSchemaSummary {
  derived_from?: string | null;
  derived_from_name?: string | null;
}

/**
 * Files → Mappings — lists every schema produced by the dictionary
 * mapper (those that carry ``metadata.derived_from``). The "+ New
 * mapping" button launches the modal; clicking an existing derived
 * schema opens it for edit, with the original source preselected.
 */
export default function FilesMappingsPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [allSchemas, setAllSchemas] = useState<DerivedSchemaSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mapperOpen, setMapperOpen] = useState(false);
  const [preselectSourceId, setPreselectSourceId] = useState<string | undefined>(
    undefined,
  );
  // When set, the modal hydrates the existing derived schema and PATCHes
  // it on save (versus the "New mapping" path which preselects a source
  // and POSTs a brand-new derived schema).
  const [editDerivedId, setEditDerivedId] = useState<string | undefined>(undefined);

  // The list endpoint only returns FileSchemaSummary; ``derived_from`` lives
  // in metadata which isn't on the summary. We fetch the detail for each
  // schema once on load and stash the metadata.derived_from value.
  const fetchSchemas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.get<FileSchemaSummary[]>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas`,
      );
      const enriched = await Promise.all(
        list.map(async (s) => {
          try {
            const detail = await api.get<{
              metadata?: Record<string, unknown> | null;
            }>(
              `/api/v1/projects/${projectId}/synthetic/file-schemas/${s.id}`,
            );
            const md = detail.metadata ?? {};
            return {
              ...s,
              derived_from: (md.derived_from as string | undefined) ?? null,
              derived_from_name:
                (md.derived_from_name as string | undefined) ?? null,
            };
          } catch {
            return { ...s, derived_from: null };
          }
        }),
      );
      setAllSchemas(enriched);
    } catch (e) {
      setError((e as Error).message || "Failed to load schemas");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void fetchSchemas();
  }, [fetchSchemas]);

  const derived = useMemo(
    () => allSchemas.filter((s) => !!s.derived_from),
    [allSchemas],
  );
  const sources = useMemo(
    () => allSchemas.filter((s) => !s.derived_from),
    [allSchemas],
  );

  const openNew = () => {
    setEditDerivedId(undefined);
    setPreselectSourceId(undefined);
    setMapperOpen(true);
  };

  const openWithSource = (sourceId: string) => {
    setEditDerivedId(undefined);
    setPreselectSourceId(sourceId);
    setMapperOpen(true);
  };

  const openForEdit = (derivedId: string) => {
    // Edit mode: the modal will hydrate from /file-schemas/{id}/mappings
    // and PATCH on save. preselectSourceId is intentionally cleared —
    // the source comes from the persisted derived_from, not the UI.
    setPreselectSourceId(undefined);
    setEditDerivedId(derivedId);
    setMapperOpen(true);
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-2">
        <p className="grow text-xs text-muted-foreground">
          Transform one file schema into another with the dictionary mapper. Each
          derived schema remembers its source + mapping for re-edit.
        </p>
        <button
          type="button"
          onClick={openNew}
          disabled={sources.length === 0}
          title={
            sources.length === 0
              ? "Add a source file schema first"
              : "Start a new mapping"
          }
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
        >
          <Plus className="h-3 w-3" /> New mapping
        </button>
      </header>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      ) : (
        <>
          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-foreground">
              Derived schemas ({derived.length})
            </h2>
            {derived.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground space-y-2">
                <div className="flex items-center gap-2 text-foreground">
                  <Workflow className="h-4 w-4" />
                  <span className="font-medium">No mappings yet</span>
                </div>
                <p>
                  Map fields from one schema to another with optional transforms
                  (trim, pad, upper, lower, substring, date-format). The result
                  is a brand-new file schema that you can browse, generate, and
                  re-edit.
                </p>
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-border bg-card">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">Target</th>
                      <th className="px-3 py-2 font-medium">Derived from</th>
                      <th className="px-3 py-2 font-medium">Format</th>
                      <th className="px-3 py-2 text-right font-medium">Fields</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {derived.map((d) => (
                      <tr key={d.id} className="hover:bg-muted/20">
                        <td className="px-3 py-2 font-medium text-foreground">
                          {d.name}
                        </td>
                        <td className="px-3 py-2 text-[11px] text-muted-foreground">
                          {d.derived_from_name ?? d.derived_from}
                        </td>
                        <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">
                          {d.file_format}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">{d.field_count}</td>
                        <td className="px-3 py-2 text-right">
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => openForEdit(d.id)}
                              className="rounded-md border border-input bg-background px-2 py-1 text-[11px] hover:bg-muted/40"
                              title="Update this derived schema in place"
                            >
                              Re-edit
                            </button>
                            {d.derived_from && (
                              <button
                                type="button"
                                onClick={() => openWithSource(d.derived_from!)}
                                className="rounded-md border border-input bg-background px-2 py-1 text-[11px] hover:bg-muted/40"
                                title="Start a new mapping from the same source"
                              >
                                Duplicate
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {sources.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-foreground">
                Map from a source ({sources.length} available)
              </h2>
              <div className="flex flex-wrap gap-2">
                {sources.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => openWithSource(s.id)}
                    className="rounded-md border border-input bg-background px-2 py-1 text-xs hover:bg-muted/40"
                  >
                    {s.name}{" "}
                    <span className="ml-1 font-mono text-[10px] text-muted-foreground">
                      {s.file_format}
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <DictionaryMapperModal
        projectId={projectId}
        open={mapperOpen}
        onClose={() => {
          setMapperOpen(false);
          setEditDerivedId(undefined);
          setPreselectSourceId(undefined);
          void fetchSchemas();
        }}
        sourceSchemaId={preselectSourceId}
        derivedSchemaId={editDerivedId}
      />
    </div>
  );
}
