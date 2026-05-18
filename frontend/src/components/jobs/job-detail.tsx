"use client";

import { useSSE } from "@/hooks/use-sse";
import { cn } from "@/lib/utils";

interface JobDetailProps {
  jobId: string;
  projectId: string;
  status: string;
  progress: number;
  errorMessage: string | null;
}

interface SSEData {
  progress: number;
  status: string;
  message: string;
}

export function JobDetail({ jobId, projectId, status, progress, errorMessage }: JobDetailProps) {
  const isLive = status === "running" || status === "pending";
  const { data: sseData } = useSSE<SSEData>(
    `/api/v1/projects/${projectId}/jobs/${jobId}/stream`,
    isLive
  );

  const currentProgress = sseData?.progress ?? progress;
  const currentStatus = sseData?.status ?? status;
  const currentMessage = sseData?.message ?? "";

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">Job {jobId.slice(0, 8)}...</span>
        <span className={cn(
          "text-xs font-medium px-2 py-0.5 rounded-full",
          currentStatus === "running" ? "bg-blue-500/10 text-blue-600" :
          currentStatus === "completed" ? "bg-green-500/10 text-green-600" :
          currentStatus === "completed_with_warnings" ? "bg-amber-500/10 text-amber-700" :
          currentStatus === "failed" ? "bg-red-500/10 text-red-600" :
          "bg-muted text-muted-foreground"
        )}>
          {currentStatus === "completed_with_warnings" ? "completed with warnings" : currentStatus}
        </span>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-1">
          <span>{currentMessage || "Processing..."}</span>
          <span>{currentProgress}%</span>
        </div>
        <div className="h-2 rounded-full bg-muted overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              currentStatus === "running"
                ? "bg-blue-500"
                : currentStatus === "completed"
                  ? "bg-green-500"
                  : currentStatus === "completed_with_warnings"
                    ? "bg-amber-500"
                    : "bg-red-500"
            )}
            style={{ width: `${currentProgress}%` }}
          />
        </div>
      </div>

      {errorMessage && (
        // For ``completed_with_warnings`` runs the worker stores the
        // skip summary in error_message. Render in amber rather than
        // red so the operator sees "needs attention" not "the job
        // exploded" — the bundle is still downloadable.
        <div
          className={cn(
            "rounded-md px-3 py-2 text-xs",
            currentStatus === "completed_with_warnings"
              ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
              : "bg-red-500/10 text-red-700 dark:text-red-400"
          )}
        >
          {errorMessage}
        </div>
      )}
    </div>
  );
}
