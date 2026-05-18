"use client";

import { useState } from "react";
import { Loader2, Upload } from "lucide-react";

import { cn } from "@/lib/utils";
import { uploadFile } from "../upload-file";
import type { FileSchemaDetail, PreviewResponse } from "../types";

interface SampleDataGridProps {
  projectId: string;
  schema: FileSchemaDetail;
  /** Notifies the parent whenever we get a fresh preview so the right
   * pane can derive sample values from the same rows. */
  onPreviewLoaded: (rows: PreviewResponse) => void;
}

/**
 * Two-mode grid (File-AID / Microfocus idiom):
 *  - "formatted": one column per discovered field, values typed
 *  - "character": single column showing the raw record string
 *
 * Multi-record schemas color each row by the variant that matched, so
 * analysts can spot misclassified records at a glance.
 */
export function SampleDataGrid({
  projectId,
  schema,
  onPreviewLoaded,
}: SampleDataGridProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [mode, setMode] = useState<"formatted" | "character">("formatted");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (f?: File | null) => {
    const target = f ?? file;
    if (!target) return;
    setFile(target);
    setBusy(true);
    setError(null);
    try {
      const res = await uploadFile<PreviewResponse>(
        `/api/v1/projects/${projectId}/file-schemas/${schema.id}/preview`,
        { file: target, extras: { limit: 100 } },
      );
      if (!res) throw new Error("Empty response");
      setPreview(res);
      onPreviewLoaded(res);
    } catch (e) {
      setError((e as Error).message || "Preview failed");
    } finally {
      setBusy(false);
    }
  };

  const columns =
    preview && mode === "formatted"
      ? Array.from(
          new Set(preview.rows.flatMap((r) => Object.keys(r.fields))),
        ).slice(0, 16)
      : [];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-input bg-background px-3 py-1.5 text-xs hover:border-primary">
          <Upload className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-foreground">
            {file ? file.name : "Drop or pick a data file"}
          </span>
          <input
            type="file"
            className="sr-only"
            onChange={(e) => run(e.target.files?.[0] ?? null)}
          />
        </label>
        <button
          type="button"
          onClick={() => run()}
          disabled={!file || busy}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-[11px] text-primary-foreground disabled:opacity-50"
        >
          {busy && <Loader2 className="h-3 w-3 animate-spin" />}
          Reload
        </button>
        <div className="ml-auto inline-flex overflow-hidden rounded-md border border-input text-[11px]">
          <button
            type="button"
            onClick={() => setMode("formatted")}
            className={cn(
              "px-2 py-1",
              mode === "formatted" ? "bg-primary text-primary-foreground" : "bg-background",
            )}
          >
            Formatted
          </button>
          <button
            type="button"
            onClick={() => setMode("character")}
            className={cn(
              "px-2 py-1",
              mode === "character" ? "bg-primary text-primary-foreground" : "bg-background",
            )}
          >
            Character
          </button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {preview && (
        <div className="rounded-md border border-border bg-card">
          <div className="border-b border-border bg-muted/20 px-3 py-1 text-[11px] text-muted-foreground">
            {preview.summary.total_rows} row{preview.summary.total_rows === 1 ? "" : "s"} •
            {" "}
            {Object.entries(preview.summary.matched)
              .map(([k, v]) => `${k}: ${v}`)
              .join(" · ")}
          </div>
          <div className="max-h-[420px] overflow-auto">
            {mode === "formatted" ? (
              <table className="w-full text-[11px]">
                <thead className="bg-muted/30 sticky top-0">
                  <tr>
                    <th className="px-2 py-1 text-left font-medium text-muted-foreground">#</th>
                    <th className="px-2 py-1 text-left font-medium text-muted-foreground">
                      Layout
                    </th>
                    {columns.map((c) => (
                      <th
                        key={c}
                        className="px-2 py-1 text-left font-mono font-medium text-muted-foreground"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((r) => (
                    <tr
                      key={r.row_index}
                      className={cn(
                        "border-t border-border",
                        r.layout !== "_base" && layoutTint(r.layout),
                      )}
                    >
                      <td className="px-2 py-1 text-muted-foreground">{r.row_index}</td>
                      <td className="px-2 py-1 font-mono text-muted-foreground">
                        {r.layout}
                      </td>
                      {columns.map((c) => (
                        <td key={c} className="px-2 py-1 font-mono text-foreground">
                          {r.fields[c] === null || r.fields[c] === undefined
                            ? ""
                            : String(r.fields[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <pre className="overflow-x-auto px-3 py-2 font-mono text-[11px] text-foreground">
                {preview.rows
                  .map((r) =>
                    `[${String(r.row_index).padStart(4, " ")}] ${r.layout.padEnd(12, " ")} ` +
                    Object.entries(r.fields)
                      .map(([k, v]) => `${k}=${v}`)
                      .join("|"),
                  )
                  .join("\n")}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const _TINTS = [
  "bg-emerald-500/5",
  "bg-blue-500/5",
  "bg-violet-500/5",
  "bg-amber-500/5",
  "bg-rose-500/5",
];

const _layoutTintMap = new Map<string, string>();

function layoutTint(name: string): string {
  if (!_layoutTintMap.has(name)) {
    _layoutTintMap.set(name, _TINTS[_layoutTintMap.size % _TINTS.length]);
  }
  return _layoutTintMap.get(name)!;
}
