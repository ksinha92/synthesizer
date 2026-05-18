"use client";

import { useEffect, useState } from "react";
import { Download, Loader2, Play, Plus, Trash2 } from "lucide-react";

import { useFileOutputStore } from "@/stores/file-output-store";

const FORMAT_CHOICES = [
  { value: "csv", label: "CSV" },
  { value: "fixed_width", label: "Fixed-width" },
  { value: "vsam_fixed", label: "VSAM Fixed" },
  { value: "vsam_variable", label: "VSAM Variable" },
  { value: "parquet", label: "Parquet" },
  { value: "orc", label: "ORC" },
];

interface FileOutputPanelProps {
  projectId: string;
}

export function FileOutputPanel({ projectId }: FileOutputPanelProps) {
  const {
    schemas,
    schemasLoading,
    selectedSchemaIds,
    formats,
    rowCounts,
    foreignKeys,
    currentJob,
    generating,
    fetchSchemas,
    toggleSchema,
    setFormat,
    setRowCount,
    addFk,
    removeFk,
    generate,
    pollJob,
    downloadUrl,
  } = useFileOutputStore();

  const [fileSetName, setFileSetName] = useState("file-set");
  const [fk, setFk] = useState({
    source_file: "", source_field: "", target_file: "", target_field: "",
  });

  useEffect(() => {
    fetchSchemas(projectId);
  }, [projectId, fetchSchemas]);

  // Poll the job while it's running. ``completed_with_warnings`` is a
  // terminal state (bundle exists, some masking was dropped) — stop
  // polling there too or the builder spins forever for any run with
  // skipped rules.
  useEffect(() => {
    if (
      !currentJob ||
      ["completed", "completed_with_warnings", "failed", "cancelled"].includes(
        currentJob.status,
      )
    ) {
      return;
    }
    const id = setInterval(() => pollJob(projectId, currentJob.job_id), 2000);
    return () => clearInterval(id);
  }, [currentJob, projectId, pollJob]);

  const handleGenerate = async () => {
    await generate(projectId, fileSetName);
  };

  const handleAddFk = () => {
    if (!fk.source_file || !fk.source_field || !fk.target_file || !fk.target_field) return;
    addFk({ ...fk });
    setFk({ source_file: "", source_field: "", target_file: "", target_field: "" });
  };

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">File-Set Builder</h3>
          <input
            type="text"
            value={fileSetName}
            onChange={(e) => setFileSetName(e.target.value)}
            placeholder="file-set name"
            className="w-48 rounded-md border border-input bg-background px-2 py-1 text-sm"
          />
        </div>

        {schemasLoading ? (
          <p className="text-xs text-muted-foreground">Loading file schemas...</p>
        ) : schemas.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No file schemas yet. Upload a copybook or Excel dictionary first.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3"></th>
                <th className="py-2 pr-3">Schema</th>
                <th className="py-2 pr-3">Format</th>
                <th className="py-2 pr-3 text-right">Row count</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {schemas.map((s) => {
                const selected = selectedSchemaIds.has(s.id);
                return (
                  <tr key={s.id} className={selected ? "bg-muted/30" : ""}>
                    <td className="py-2 pr-3">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleSchema(s.id)}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <p className="font-medium text-foreground">{s.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {s.field_count} fields · {s.record_length}B record
                      </p>
                    </td>
                    <td className="py-2 pr-3">
                      <select
                        value={formats[s.id] || s.file_format}
                        onChange={(e) => setFormat(s.id, e.target.value)}
                        disabled={!selected}
                        className="rounded-md border border-input bg-background px-2 py-1 text-xs disabled:opacity-50"
                      >
                        {FORMAT_CHOICES.map((f) => (
                          <option key={f.value} value={f.value}>{f.label}</option>
                        ))}
                      </select>
                    </td>
                    <td className="py-2 pr-3 text-right">
                      <input
                        type="number"
                        value={rowCounts[s.id] || 100}
                        onChange={(e) => setRowCount(s.id, parseInt(e.target.value, 10) || 1)}
                        disabled={!selected}
                        min={1}
                        className="w-24 rounded-md border border-input bg-background px-2 py-1 text-xs text-right disabled:opacity-50"
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card p-5 space-y-3">
        <h3 className="text-sm font-semibold text-foreground">Cross-file Foreign Keys</h3>
        {foreignKeys.length === 0 ? (
          <p className="text-xs text-muted-foreground">No FKs declared.</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {foreignKeys.map((f, i) => (
              <li key={i} className="flex items-center gap-2 font-mono">
                <span>{f.source_file}.{f.source_field}</span>
                <span>→</span>
                <span>{f.target_file}.{f.target_field}</span>
                <button onClick={() => removeFk(i)} className="ml-auto text-muted-foreground hover:text-destructive">
                  <Trash2 className="h-3 w-3" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="grid grid-cols-4 gap-2 text-xs">
          <input className="rounded-md border border-input bg-background px-2 py-1" placeholder="source file"
            value={fk.source_file} onChange={(e) => setFk({ ...fk, source_file: e.target.value })} />
          <input className="rounded-md border border-input bg-background px-2 py-1" placeholder="source field"
            value={fk.source_field} onChange={(e) => setFk({ ...fk, source_field: e.target.value })} />
          <input className="rounded-md border border-input bg-background px-2 py-1" placeholder="target file"
            value={fk.target_file} onChange={(e) => setFk({ ...fk, target_file: e.target.value })} />
          <input className="rounded-md border border-input bg-background px-2 py-1" placeholder="target field"
            value={fk.target_field} onChange={(e) => setFk({ ...fk, target_field: e.target.value })} />
        </div>
        <button
          onClick={handleAddFk}
          className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
        >
          <Plus className="h-3 w-3" /> Add FK
        </button>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleGenerate}
          disabled={generating || selectedSchemaIds.size === 0}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          Generate File Set
        </button>

        {currentJob && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">Job {currentJob.job_id.slice(0, 8)}…</span>
            <span className={`font-medium ${
              currentJob.status === "completed" ? "text-emerald-600" :
              currentJob.status === "completed_with_warnings" ? "text-amber-600" :
              currentJob.status === "failed" ? "text-red-600" :
              "text-sky-600"
            }`}>
              {currentJob.status === "completed_with_warnings"
                ? "completed with warnings"
                : currentJob.status}
            </span>
            {(currentJob.status === "completed" ||
              currentJob.status === "completed_with_warnings") && (
              <a
                href={downloadUrl(projectId, currentJob.job_id)}
                download
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
              >
                <Download className="h-3 w-3" /> Download zip
              </a>
            )}
            {currentJob.error_message && (
              <span
                className={`text-xs ${
                  currentJob.status === "completed_with_warnings"
                    ? "text-amber-600"
                    : "text-red-600"
                }`}
              >
                {currentJob.error_message}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
