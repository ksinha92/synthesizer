"use client";

import Link from "next/link";
import { ArrowRight, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export interface JobRow {
  id: string;
  projectId: string;
  projectName?: string;
  job_type: string;
  status: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  progress?: number;
}

interface PipelineHealthProps {
  recentJobs: JobRow[];
  loading?: boolean;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return `${m}m ${rem}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function PipelineHealth({ recentJobs, loading }: PipelineHealthProps) {
  const [showFailed, setShowFailed] = useState(false);

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="h-12 animate-pulse rounded-md bg-muted" />
        <div className="h-12 animate-pulse rounded-md bg-muted" />
        <div className="h-12 animate-pulse rounded-md bg-muted" />
      </div>
    );
  }

  // 7-day window only
  const cutoff = Date.now() - 7 * 86_400_000;
  const window = recentJobs.filter((j) => new Date(j.created_at).getTime() >= cutoff);

  // ``completed_with_warnings`` is terminal: the artifact exists but the
  // run dropped one or more requested operations. We count it toward
  // success for rate calculations (the bundle is downloadable) so a
  // run with skipped masking doesn't tank the dashboard's success
  // metric, but the warning surfaces via the status pill + per-job
  // ``error_message`` on the jobs surface.
  const terminal = window.filter((j) =>
    ["completed", "completed_with_warnings", "succeeded", "failed", "cancelled"].includes(j.status),
  );
  const success = terminal.filter(
    (j) =>
      j.status === "completed" ||
      j.status === "completed_with_warnings" ||
      j.status === "succeeded",
  ).length;
  const failed = terminal.filter((j) => j.status === "failed");
  const successRate = terminal.length > 0 ? Math.round((success / terminal.length) * 100) : null;

  const durations = window
    .filter((j) => j.started_at && j.completed_at)
    .map((j) => new Date(j.completed_at as string).getTime() - new Date(j.started_at as string).getTime())
    .filter((d) => d > 0);
  const avgMs = durations.length
    ? durations.reduce((s, d) => s + d, 0) / durations.length
    : null;

  if (window.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-muted-foreground">
        No jobs in the last 7 days. Start a discovery, masking, or generation run to populate pipeline metrics.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-3 gap-3">
        <div className="rounded-md border border-border bg-background p-3">
          <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">Success rate</dt>
          <dd
            className={cn(
              "mt-1 text-xl font-semibold tabular-nums",
              successRate === null
                ? "text-muted-foreground"
                : successRate >= 95
                  ? "text-emerald-600 dark:text-emerald-400"
                  : successRate >= 80
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-red-600 dark:text-red-400",
            )}
          >
            {successRate === null ? "—" : `${successRate}%`}
          </dd>
        </div>
        <div className="rounded-md border border-border bg-background p-3">
          <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">Avg duration</dt>
          <dd className="mt-1 text-xl font-semibold tabular-nums text-foreground">
            {avgMs === null ? "—" : formatDuration(avgMs)}
          </dd>
        </div>
        <div className="rounded-md border border-border bg-background p-3">
          <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">Failed (7d)</dt>
          <dd
            className={cn(
              "mt-1 text-xl font-semibold tabular-nums",
              failed.length > 0 ? "text-red-600 dark:text-red-400" : "text-foreground",
            )}
          >
            {failed.length}
          </dd>
        </div>
      </dl>

      {failed.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowFailed((v) => !v)}
            aria-expanded={showFailed}
            className="flex w-full items-center justify-between rounded-md border border-border bg-background px-3 py-2 text-xs font-medium hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <span className="text-foreground">
              {failed.length} failed {failed.length === 1 ? "job" : "jobs"} in the last 7 days
            </span>
            {showFailed ? (
              <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </button>
          {showFailed && (
            <ul className="mt-2 divide-y divide-border rounded-md border border-border bg-card">
              {failed.slice(0, 5).map((job) => (
                <li key={job.id} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
                  <div className="min-w-0">
                    <p className="truncate capitalize text-foreground">
                      {job.job_type.replaceAll("_", " ")}
                    </p>
                    {job.projectName && (
                      <p className="truncate text-[10px] text-muted-foreground">{job.projectName}</p>
                    )}
                  </div>
                  <span className="whitespace-nowrap text-[10px] text-muted-foreground">
                    {formatRelative(job.created_at)}
                  </span>
                  <Link
                    href={`/projects/${job.projectId}/jobs`}
                    className="inline-flex items-center gap-0.5 text-[11px] font-medium text-primary hover:underline"
                  >
                    Investigate
                    <ArrowRight className="h-2.5 w-2.5" />
                  </Link>
                </li>
              ))}
              {failed.length > 5 && (
                <li className="px-3 py-1.5 text-center text-[10px] text-muted-foreground">
                  + {failed.length - 5} more
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
