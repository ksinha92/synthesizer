"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { List, GanttChart } from "lucide-react";
import { JobList } from "@/components/jobs/job-list";
import { JobGantt } from "@/components/jobs/job-gantt";
import { Pagination } from "@/components/common/pagination";
import { Select } from "@/components/common/select";
import { useJobStore } from "@/stores/job-store";
import { useNotificationStore } from "@/stores/notification-store";

export default function JobsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [viewMode, setViewMode] = useState<"list" | "timeline">("list");
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const { fetchJobs, jobs, totalCount } = useJobStore();
  const addNotification = useNotificationStore((s) => s.addNotification);
  const prevJobStatuses = useRef<Record<string, string>>({});

  useEffect(() => {
    fetchJobs(projectId, {
      type: typeFilter || undefined,
      status: statusFilter || undefined,
      page,
    });
    const interval = setInterval(() => {
      fetchJobs(projectId, { type: typeFilter || undefined, status: statusFilter || undefined, page });
    }, 10000);
    return () => clearInterval(interval);
  }, [projectId, typeFilter, statusFilter, page, fetchJobs]);

  // Detect job status changes → send notifications
  useEffect(() => {
    for (const job of jobs) {
      const prev = prevJobStatuses.current[job.id];
      if (prev && prev !== job.status) {
        if (job.status === "completed") {
          addNotification({ type: "completed", message: `${job.job_type} job completed successfully`, projectId, jobId: job.id });
        } else if (job.status === "completed_with_warnings") {
          // Notify on the warning-completed terminal state so operators
          // who navigate away mid-run still get a ping that requested
          // masking was skipped. ``type: "warning"`` (not "failed") —
          // the bundle is downloadable, the operator just needs to
          // review skipped rules. A red failure cue here would be a
          // false alarm.
          addNotification({
            type: "warning",
            message: `${job.job_type} job completed with warnings${
              job.error_message ? `: ${job.error_message}` : ""
            }`,
            projectId,
            jobId: job.id,
          });
        } else if (job.status === "failed") {
          addNotification({ type: "failed", message: `${job.job_type} job failed${job.error_message ? `: ${job.error_message}` : ""}`, projectId, jobId: job.id });
        }
      }
      prevJobStatuses.current[job.id] = job.status;
    }
  }, [jobs, projectId, addNotification]);

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); }, [typeFilter, statusFilter]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Jobs</h1>
        <div className="flex items-center rounded-lg border border-border bg-muted/30 p-0.5">
          <button
            onClick={() => setViewMode("list")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${viewMode === "list" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
          >
            <List className="h-3.5 w-3.5" />
            List
          </button>
          <button
            onClick={() => setViewMode("timeline")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${viewMode === "timeline" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
          >
            <GanttChart className="h-3.5 w-3.5" />
            Timeline
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <Select
          aria-label="Filter by job type"
          fullWidth={false}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="min-w-[140px]"
        >
          <option value="">All Types</option>
          <option value="discovery">Discovery</option>
          <option value="generation">Generation</option>
          <option value="masking">Masking</option>
          <option value="subsetting">Subsetting</option>
        </Select>
        <Select
          aria-label="Filter by job status"
          fullWidth={false}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="min-w-[140px]"
        >
          <option value="">All Status</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="completed_with_warnings">Completed (warnings)</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
        </Select>
      </div>

      {viewMode === "list" ? (
        <>
          <JobList projectId={projectId} />
          <Pagination page={page} pageSize={20} totalCount={totalCount} onPageChange={setPage} />
        </>
      ) : (
        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <JobGantt jobs={useJobStore.getState().jobs} />
        </div>
      )}
    </div>
  );
}
