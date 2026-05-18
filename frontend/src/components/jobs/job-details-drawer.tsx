"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock,
  Download,
  Loader2,
  X,
  XCircle,
} from "lucide-react";

import { api } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

interface JobDetail {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  reference_id: string;
  created_by: string;
  cancelled_at: string | null;
  duration_seconds: number | null;
  result_summary: Record<string, unknown> | null;
  checkpoint: Record<string, unknown> | null;
}

interface JobDetailsDrawerProps {
  open: boolean;
  jobId: string | null;
  projectId: string;
  onClose: () => void;
}

/**
 * Tonic-style two-column job details surface (screenshots 11.33.56, 11.34.15):
 * - Left rail: static facts about the run (type, who started it, timing,
 *   duration, result summary, reference id).
 * - Right: synthetic activity log built from the job's status transitions
 *   and stored checkpoint events. Tonic ships a richer per-step log but we
 *   don't have per-step events yet — when those land, swap the synthetic
 *   timeline for the real one without touching the layout.
 */
export function JobDetailsDrawer({ open, jobId, projectId, onClose }: JobDetailsDrawerProps) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !jobId) {
      setJob(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .get<JobDetail>(`/api/v1/projects/${projectId}/jobs/${jobId}`)
      .then((d) => !cancelled && setJob(d))
      .catch(() => !cancelled && setJob(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [open, jobId, projectId]);

  // Escape closes.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div
        aria-hidden="true"
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={job ? `Job ${job.id.slice(0, 8)} details` : "Job details"}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-3xl flex-col border-l border-border bg-card shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              {job ? <>{titleCase(job.job_type)} job</> : "Job details"}
            </h2>
            {job && (
              <p className="text-[11px] text-muted-foreground font-mono">{job.id}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {job &&
              (job.status === "completed" ||
                job.status === "completed_with_warnings") &&
              isFileOutputJob(job.job_type) && (
                <DownloadResultsMenu projectId={projectId} jobId={job.id} />
              )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close job details"
              className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        {loading && (
          <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            Loading…
          </div>
        )}

        {!loading && !job && (
          <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
            Job not found.
          </div>
        )}

        {job && (
          <div className="flex flex-1 min-h-0 divide-x divide-border">
            {/* Left rail — facts */}
            <aside className="w-64 shrink-0 overflow-y-auto px-4 py-4 text-xs">
              <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Facts
              </h3>
              <dl className="mt-3 space-y-3">
                <Fact label="Type" value={titleCase(job.job_type)} />
                <Fact label="Status" value={<StatusPill status={job.status} />} />
                <Fact label="Progress" value={`${job.progress}%`} />
                <Fact
                  label="Started"
                  value={job.started_at ? new Date(job.started_at).toLocaleString() : "—"}
                />
                <Fact
                  label="Completed"
                  value={
                    job.completed_at
                      ? new Date(job.completed_at).toLocaleString()
                      : "—"
                  }
                />
                <Fact
                  label="Duration"
                  value={
                    job.duration_seconds != null ? formatDuration(job.duration_seconds) : "—"
                  }
                />
                <Fact
                  label="Started by"
                  value={
                    <span className="font-mono text-[10px]">
                      {job.created_by.slice(0, 8)}
                    </span>
                  }
                />
                <Fact
                  label="Reference"
                  value={
                    <span className="font-mono text-[10px]">
                      {job.reference_id.slice(0, 8)}
                    </span>
                  }
                />
              </dl>

              {job.result_summary && Object.keys(job.result_summary).length > 0 && (
                <>
                  <h3 className="mt-5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Result
                  </h3>
                  <ul className="mt-2 space-y-1.5">
                    {Object.entries(job.result_summary).map(([k, v]) => (
                      <li key={k} className="flex items-baseline justify-between gap-2">
                        <span className="text-muted-foreground">{k}</span>
                        <span className="text-right font-medium text-foreground">
                          {formatResultValue(v)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </aside>

            {/* Right column — activity log */}
            <section className="flex-1 overflow-y-auto px-5 py-4">
              <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Activity
              </h3>
              <ol className="mt-3 space-y-3 text-sm">
                {buildTimeline(job).map((entry, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="mt-0.5">{entry.icon}</span>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-foreground">{entry.label}</p>
                      {entry.timestamp && (
                        <p className="text-[11px] text-muted-foreground">
                          {new Date(entry.timestamp).toLocaleString()}
                        </p>
                      )}
                      {entry.detail && (
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {entry.detail}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>

              {job.error_message && (
                <div className="mt-5 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                  <p className="font-medium">Error</p>
                  <p className="mt-1 font-mono text-[11px]">{job.error_message}</p>
                </div>
              )}
            </section>
          </div>
        )}
      </aside>
    </>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 text-foreground">{value}</dd>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const cls = {
    pending: "bg-yellow-500/10 text-yellow-700 dark:text-yellow-300",
    running: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
    completed: "bg-green-500/10 text-green-700 dark:text-green-300",
    // Amber: the bundle is downloadable but some requested masking
    // didn't apply. Distinct from green-completed so a compliance
    // reviewer scanning the jobs list sees runs that need attention.
    completed_with_warnings:
      "bg-amber-500/10 text-amber-700 dark:text-amber-300",
    failed: "bg-red-500/10 text-red-700 dark:text-red-300",
    cancelled: "bg-gray-500/10 text-gray-700 dark:text-gray-300",
  }[status] || "bg-muted text-muted-foreground";

  // Render the new status with a friendlier label than the raw enum
  // string. The pill colour already carries the meaning.
  const label = status === "completed_with_warnings" ? "completed with warnings" : status;
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium", cls)}>
      {label}
    </span>
  );
}

interface TimelineEntry {
  label: string;
  icon: React.ReactNode;
  timestamp: string | null;
  detail?: string;
}

function buildTimeline(job: JobDetail): TimelineEntry[] {
  // Synthesize a step log from the available transitions. When the worker
  // starts emitting per-step events into job.checkpoint, expand this with
  // those entries; the surface stays identical.
  const entries: TimelineEntry[] = [
    {
      label: "Queued",
      icon: <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />,
      timestamp: job.created_at,
    },
    job.started_at
      ? {
          label: "Started",
          icon: <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />,
          timestamp: job.started_at,
        }
      : {
          label: "Waiting to start",
          icon: <Clock className="h-3.5 w-3.5 text-muted-foreground" />,
          timestamp: null,
        },
  ];

  if (job.status === "running") {
    entries.push({
      label: `In progress — ${job.progress}%`,
      icon: <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />,
      timestamp: null,
    });
  }

  if (job.completed_at) {
    entries.push({
      label:
        job.status === "completed"
          ? "Completed successfully"
          : job.status === "completed_with_warnings"
            ? "Completed with warnings"
            : job.status === "failed"
              ? "Failed"
              : job.status === "cancelled"
                ? "Cancelled"
                : "Finished",
      icon:
        job.status === "completed" ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
        ) : job.status === "completed_with_warnings" ? (
          <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
        ) : job.status === "failed" ? (
          <AlertCircle className="h-3.5 w-3.5 text-red-600" />
        ) : (
          <XCircle className="h-3.5 w-3.5 text-muted-foreground" />
        ),
      timestamp: job.completed_at,
      detail:
        job.duration_seconds != null
          ? `Ran for ${formatDuration(job.duration_seconds)}`
          : undefined,
    });
  } else if (job.status === "pending") {
    entries.push({
      label: "Waiting in queue",
      icon: <Circle className="h-3.5 w-3.5 text-muted-foreground" />,
      timestamp: null,
    });
  }

  return entries;
}

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function formatResultValue(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return v.toLocaleString();
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// ── Download Results dropdown (T3.3, Tonic 11.34.15) ───────────────────────
/**
 * Whether the job's output is downloadable. Today only file-set generation
 * has a results endpoint at
 * GET /api/v1/projects/{id}/synthetic/jobs/{job_id}/file-output. Other job
 * types (discovery, masking, subsetting) write into the source DB / storage
 * directly and don't expose a single artifact, so the menu stays hidden.
 */
function isFileOutputJob(jobType: string): boolean {
  return jobType === "file_set_generation" || jobType === "generation";
}

interface DownloadFormat {
  label: string;
  href: (projectId: string, jobId: string) => string;
  description?: string;
}

const DOWNLOAD_FORMATS: DownloadFormat[] = [
  {
    label: "ZIP bundle",
    href: (p, j) => `/api/v1/projects/${p}/synthetic/jobs/${j}/file-output`,
    description: "All generated files plus the manifest.",
  },
];

function DownloadResultsMenu({
  projectId,
  jobId,
}: {
  projectId: string;
  jobId: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2.5 py-1 text-xs font-medium hover:bg-muted"
      >
        <Download className="h-3 w-3" />
        Download results
        <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ul
          role="menu"
          className="absolute right-0 top-full z-50 mt-1 w-64 rounded-md border border-border bg-popover py-1 shadow-lg"
        >
          {DOWNLOAD_FORMATS.map((f) => (
            <li key={f.label} role="none">
              <a
                role="menuitem"
                href={f.href(projectId, jobId)}
                onClick={() => setOpen(false)}
                className="block px-3 py-2 text-xs text-foreground hover:bg-muted"
              >
                <span className="font-medium">{f.label}</span>
                {f.description && (
                  <span className="block text-[10px] text-muted-foreground">
                    {f.description}
                  </span>
                )}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
