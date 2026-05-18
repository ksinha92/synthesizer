"use client";

import { useState } from "react";
import { Loader2, Upload } from "lucide-react";

import { uploadFile } from "../upload-file";
import type { FileSchemaDetail, PreviewResponse } from "../types";

interface StepSampleProps {
  projectId: string;
  schema: FileSchemaDetail;
  onDone: () => void;
  onSkip: () => void;
  onBack: () => void;
}

/**
 * The "data loader" step — upload a real data file and see how it parses
 * against the schema we just saved. Skipping is fine for greenfield
 * schemas; the wizard moves on to confirm. When the schema is
 * multi-record, the preview tags each row with the variant that matched.
 */
export function StepSample({
  projectId,
  schema,
  onDone,
  onSkip,
  onBack,
}: StepSampleProps) {
  const [dataFile, setDataFile] = useState<File | null>(null);
  const [limit, setLimit] = useState(100);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runPreview = async () => {
    if (!dataFile) return;
    setBusy(true);
    setError(null);
    try {
      const res = await uploadFile<PreviewResponse>(
        `/api/v1/projects/${projectId}/file-schemas/${schema.id}/preview`,
        { file: dataFile, extras: { limit } },
      );
      if (!res) throw new Error("Empty response");
      setResult(res);
    } catch (e) {
      setError((e as Error).message || "Preview failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Optional: drop a real data file ({describeFormats(schema.file_format)}) to
        validate it against the schema. The file is parsed and discarded — it&apos;s
        never stored.
      </p>

      <label className="flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-input bg-background px-3 py-3 text-xs hover:border-primary">
        <Upload className="h-4 w-4 text-muted-foreground" />
        <div className="flex-1">
          <p className="font-medium text-foreground">Sample data file</p>
          <p className="text-[11px] text-muted-foreground">
            {dataFile
              ? `${dataFile.name} (${dataFile.size} bytes)`
              : "Click to choose a file — CSV, fixed-width, VSAM, or Parquet"}
          </p>
        </div>
        <input
          type="file"
          className="sr-only"
          onChange={(e) => setDataFile(e.target.files?.[0] ?? null)}
        />
      </label>

      <div className="flex items-center gap-2 text-xs">
        <label>
          Rows to parse:
          <input
            type="number"
            min={1}
            max={1000}
            value={limit}
            onChange={(e) => setLimit(Math.max(1, Math.min(1000, parseInt(e.target.value, 10) || 100)))}
            className="ml-2 w-20 rounded border border-input bg-background px-2 py-1"
          />
        </label>
        <button
          type="button"
          onClick={runPreview}
          disabled={!dataFile || busy}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-[11px] text-primary-foreground disabled:opacity-50"
        >
          {busy && <Loader2 className="h-3 w-3 animate-spin" />}
          Preview
        </button>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {result && (
        <div className="rounded-md border border-border bg-card">
          <div className="border-b border-border bg-muted/30 px-3 py-2 text-[11px]">
            <p className="font-medium text-foreground">
              Parsed {result.summary.total_rows} row
              {result.summary.total_rows === 1 ? "" : "s"}
            </p>
            <p className="text-muted-foreground">
              {Object.entries(result.summary.matched)
                .map(([k, v]) => `${k}: ${v}`)
                .join(" • ")}
            </p>
          </div>
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-[11px]">
              <thead className="bg-muted/20">
                <tr>
                  <th className="px-2 py-1 text-left font-medium text-muted-foreground">
                    Row
                  </th>
                  <th className="px-2 py-1 text-left font-medium text-muted-foreground">
                    Layout
                  </th>
                  <th className="px-2 py-1 text-left font-medium text-muted-foreground">
                    Fields
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.rows.slice(0, 25).map((r) => (
                  <tr key={r.row_index} className="border-t border-border">
                    <td className="px-2 py-1 text-muted-foreground">{r.row_index}</td>
                    <td className="px-2 py-1 font-mono text-foreground">{r.layout}</td>
                    <td className="px-2 py-1 font-mono text-muted-foreground">
                      {Object.entries(r.fields)
                        .slice(0, 5)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(" • ")}
                      {Object.keys(r.fields).length > 5 && " …"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.rows.length > 25 && (
              <p className="px-2 py-1 text-[10px] text-muted-foreground">
                Showing first 25 of {result.rows.length} parsed rows.
              </p>
            )}
          </div>
        </div>
      )}

      <div className="flex justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-input bg-background px-3 py-1.5 text-xs hover:bg-muted/40"
        >
          Back
        </button>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSkip}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-xs hover:bg-muted/40"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={onDone}
            className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

function describeFormats(format: string): string {
  if (format.startsWith("vsam")) return "VSAM EBCDIC";
  if (format === "csv") return "CSV";
  if (format === "fixed_width") return "fixed-width";
  if (format === "parquet") return "Parquet";
  if (format === "orc") return "ORC";
  return format;
}
