"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Eye, FileText, Loader2, Plus, RefreshCw } from "lucide-react";

import { api } from "@/hooks/use-api";

import { FileLoaderWizard } from "@/components/file-loader/wizard/file-loader-wizard";
import type { FileSchemaSummary } from "@/components/file-loader/types";

/**
 * Files → Schemas — the canonical place to add a new file schema and to
 * see what already exists. Acts as the launchpad for the Microfocus-style
 * deep viewer (one click → /files/viewer?schema_id=…).
 */
export default function FilesSchemasPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [schemas, setSchemas] = useState<FileSchemaSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const fetchSchemas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.get<FileSchemaSummary[]>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas`,
      );
      setSchemas(list);
    } catch (e) {
      setError((e as Error).message || "Failed to load schemas");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void fetchSchemas();
  }, [fetchSchemas]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="grow text-xs text-muted-foreground">
          {schemas.length} file schema{schemas.length === 1 ? "" : "s"} in this
          project.
        </p>
        <button
          type="button"
          onClick={() => void fetchSchemas()}
          className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-[11px] hover:bg-muted/40"
        >
          <RefreshCw className="h-3 w-3" /> Refresh
        </button>
        <button
          type="button"
          onClick={() => setWizardOpen(true)}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
        >
          <Plus className="h-3 w-3" /> Add file schema
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
          {error}
        </div>
      ) : schemas.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground space-y-2">
          <div className="flex items-center gap-2 text-foreground">
            <FileText className="h-4 w-4" />
            <span className="font-medium">No file schemas yet</span>
          </div>
          <p>
            Import a COBOL copybook, upload an Excel data dictionary, or build a
            schema by hand. Multi-record layouts (Microfocus / File-AID style)
            and EBCDIC/VSAM are supported.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Format</th>
                <th className="px-3 py-2 font-medium">Encoding</th>
                <th className="px-3 py-2 text-right font-medium">Fields</th>
                <th className="px-3 py-2 text-right font-medium">Record bytes</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {schemas.map((s) => (
                <tr key={s.id} className="hover:bg-muted/20">
                  <td className="px-3 py-2 font-medium text-foreground">{s.name}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">
                    {s.file_format}
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">
                    {s.encoding}
                  </td>
                  <td className="px-3 py-2 text-right text-xs text-foreground">
                    {s.field_count}
                  </td>
                  <td className="px-3 py-2 text-right text-xs text-muted-foreground">
                    {s.record_length}
                  </td>
                  <td className="px-3 py-2 text-[11px] text-muted-foreground">
                    {s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/projects/${projectId}/files/viewer?schema_id=${s.id}`}
                      className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-[11px] hover:bg-muted/40"
                    >
                      <Eye className="h-3 w-3" /> Open viewer
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <FileLoaderWizard
        projectId={projectId}
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onSchemaCreated={() => {
          setWizardOpen(false);
          void fetchSchemas();
        }}
      />
    </div>
  );
}
