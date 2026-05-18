"use client";

import { useState } from "react";
import { Activity, RefreshCw, XCircle } from "lucide-react";
import { useJobStore } from "@/stores/job-store";
import { EmptyState } from "@/components/common/empty-state";
import { SkeletonRow } from "@/components/common/skeleton-card";
import { JobDetailsDrawer } from "@/components/jobs/job-details-drawer";
import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  pending: { color: "bg-yellow-500", label: "Pending" },
  running: { color: "bg-blue-500 animate-pulse", label: "Running" },
  completed: { color: "bg-green-500", label: "Completed" },
  // Amber dot — bundle exists, but some requested masking didn't apply.
  // Distinct from green so compliance scans this row as "needs review".
  completed_with_warnings: { color: "bg-amber-500", label: "Completed (warnings)" },
  failed: { color: "bg-red-500", label: "Failed" },
  cancelled: { color: "bg-gray-400", label: "Cancelled" },
};

interface JobListProps {
  projectId: string;
}

export function JobList({ projectId }: JobListProps) {
  const { jobs, loading, cancelJob, retryJob } = useJobStore();
  const [openJobId, setOpenJobId] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No jobs yet"
        description="Jobs appear when you run discovery, generation, or masking operations."
      />
    );
  }

  return (
    <div className="space-y-2">
      {jobs.map((job) => {
        const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.pending;
        const isRunning = job.status === "running";
        const canRetry = job.status === "failed" || job.status === "cancelled";

        return (
          <div
            key={job.id}
            onClick={() => setOpenJobId(job.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setOpenJobId(job.id);
              }
            }}
            role="button"
            tabIndex={0}
            aria-label={`Open details for ${job.job_type} job`}
            className="rounded-lg border border-border bg-card p-4 cursor-pointer transition-colors hover:bg-muted/30 focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <div className="flex items-center gap-3">
              {/* Status dot */}
              <span className={cn("h-2.5 w-2.5 rounded-full shrink-0", cfg.color)} />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground capitalize">{job.job_type}</span>
                  <span className="text-xs text-muted-foreground">{cfg.label}</span>
                </div>

                {/* Progress bar */}
                {(isRunning || job.status === "pending") && (
                  <div className="mt-1.5 h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all duration-500", isRunning ? "bg-blue-500" : "bg-yellow-500")}
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                )}

                {job.error_message && (
                  <p className="mt-1 text-xs text-destructive truncate">{job.error_message}</p>
                )}
              </div>

              {/* Progress % */}
              {isRunning && <span className="text-sm font-mono text-muted-foreground">{job.progress}%</span>}

              {/* Timestamps */}
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {job.started_at ? new Date(job.started_at).toLocaleTimeString() : "—"}
              </span>

              {/* Actions — stop click propagation so the row's open-drawer
                  handler doesn't fire when you cancel/retry. */}
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                {isRunning && (
                  <button onClick={() => cancelJob(projectId, job.id)} className="p-1 text-muted-foreground hover:text-destructive" title="Cancel">
                    <XCircle className="h-4 w-4" />
                  </button>
                )}
                {canRetry && (
                  <button onClick={() => retryJob(projectId, job.id)} className="p-1 text-muted-foreground hover:text-primary" title="Retry">
                    <RefreshCw className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <JobDetailsDrawer
        open={openJobId !== null}
        jobId={openJobId}
        projectId={projectId}
        onClose={() => setOpenJobId(null)}
      />
    </div>
  );
}
