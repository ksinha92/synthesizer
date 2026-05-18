"use client";

import { useState } from "react";
import { Code, Eye, Loader2, Play } from "lucide-react";
import { api } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

interface GenerationPlanEditorProps {
  plan: Record<string, unknown>;
  projectId: string;
  connectionId: string;
}

export function GenerationPlanEditor({ plan, projectId, connectionId }: GenerationPlanEditorProps) {
  const [jsonText, setJsonText] = useState(JSON.stringify(plan, null, 2));
  const [viewMode, setViewMode] = useState<"code" | "visual">("visual");
  const [jsonError, setJsonError] = useState("");
  const [executing, setExecuting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const meta = (plan as any)?._meta || {};
  const tables = (plan as any)?.tables || [];

  const handleJsonChange = (text: string) => {
    setJsonText(text);
    try {
      JSON.parse(text);
      setJsonError("");
    } catch {
      setJsonError("Invalid JSON");
    }
  };

  const handleExecute = async () => {
    let parsedPlan: Record<string, unknown>;
    try {
      parsedPlan = JSON.parse(jsonText);
    } catch {
      setJsonError("Invalid JSON — fix before executing");
      return;
    }

    setExecuting(true);
    try {
      const data = await api.post<{ job_id: string }>(
        `/api/v1/projects/${projectId}/synthetic/nlp-execute`,
        { plan: parsedPlan, connection_id: connectionId, name: "NLP Generation" }
      );
      setJobId(data.job_id);
    } catch { /* */ }
    setExecuting(false);
  };

  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Generation Plan</h3>
        <div className="flex items-center gap-0.5 rounded-lg border border-border p-0.5">
          <button
            onClick={() => setViewMode("visual")}
            className={cn("rounded-md p-1.5 text-xs", viewMode === "visual" ? "bg-muted" : "")}
          >
            <Eye className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setViewMode("code")}
            className={cn("rounded-md p-1.5 text-xs", viewMode === "code" ? "bg-muted" : "")}
          >
            <Code className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Cost/time estimate */}
      {meta.estimated_time_seconds && (
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span>Est. time: ~{Math.ceil(meta.estimated_time_seconds)}s</span>
          {meta.tokens?.call_count > 0 && <span>LLM calls: {meta.tokens.call_count}</span>}
        </div>
      )}

      {viewMode === "visual" ? (
        <div className="space-y-3">
          {tables.map((table: any, i: number) => (
            <div key={i} className="rounded-md border border-border p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-foreground">{table.table_name}</span>
                <span className="text-xs text-muted-foreground">{table.row_count} rows</span>
              </div>
              <div className="space-y-1">
                {(table.columns || []).map((col: any, j: number) => (
                  <div key={j} className="flex items-center gap-2 text-xs">
                    <span className="text-foreground font-mono w-32 truncate">{col.name}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">{col.strategy}</span>
                    {col.distribution && (
                      <span className="text-muted-foreground">
                        {typeof col.distribution === "object"
                          ? Object.entries(col.distribution).map(([k, v]) => `${k}:${(Number(v) * 100).toFixed(0)}%`).join(", ")
                          : col.distribution}
                      </span>
                    )}
                    {col.min !== undefined && <span className="text-muted-foreground">{col.min}-{col.max}</span>}
                    {col.true_pct !== undefined && <span className="text-muted-foreground">{(col.true_pct * 100).toFixed(0)}% true</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div>
          <textarea
            value={jsonText}
            onChange={(e) => handleJsonChange(e.target.value)}
            rows={15}
            className="w-full rounded-lg border border-input bg-background px-4 py-3 text-xs font-mono text-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
          />
          {jsonError && <p className="mt-1 text-xs text-destructive">{jsonError}</p>}
        </div>
      )}

      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={handleExecute}
          disabled={executing || !!jsonError}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {executing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          Execute Plan
        </button>
        {jobId && <span className="text-xs text-muted-foreground">Job: {jobId.slice(0, 8)}...</span>}
      </div>
    </div>
  );
}
