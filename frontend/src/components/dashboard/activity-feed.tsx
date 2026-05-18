"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Loader2,
  Pause,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { JobRow } from "./pipeline-health";

interface ActivityFeedProps {
  jobs: JobRow[];
  loading?: boolean;
  emptyHref?: string;
}

const STATUS_ICON: Record<string, LucideIcon> = {
  running: Loader2,
  pending: Loader2,
  completed: CheckCircle2,
  succeeded: CheckCircle2,
  failed: XCircle,
  cancelled: Pause,
};

const STATUS_STYLE: Record<string, string> = {
  running: "text-blue-500",
  pending: "text-blue-500/60",
  completed: "text-emerald-500",
  succeeded: "text-emerald-500",
  failed: "text-red-500",
  cancelled: "text-muted-foreground",
};

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

export function ActivityFeed({ jobs, loading, emptyHref = "/projects" }: ActivityFeedProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-12 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    );
  }

  const sorted = [...jobs]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 10);

  if (sorted.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        <Activity className="h-6 w-6 text-muted-foreground/60" aria-hidden />
        <p className="text-xs text-muted-foreground">
          No recent activity. Trigger a job from any project to start a stream.
        </p>
        <Link
          href={emptyHref}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          Go to projects
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    );
  }

  return (
    <ul className="-mx-1 divide-y divide-border" aria-label="Recent activity">
      {sorted.map((job) => {
        const Icon = STATUS_ICON[job.status] ?? Activity;
        const klass = STATUS_STYLE[job.status] ?? "text-muted-foreground";
        const isRunning = job.status === "running" || job.status === "pending";
        return (
          <li key={job.id}>
            <Link
              href={`/projects/${job.projectId}/jobs`}
              className="flex items-center gap-3 rounded-md px-1 py-2 hover:bg-muted/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              <Icon
                className={cn("h-4 w-4 shrink-0", klass, isRunning && "animate-spin")}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm capitalize text-foreground">
                  {job.job_type.replaceAll("_", " ")}
                </p>
                <p className="truncate text-[10px] text-muted-foreground">
                  {job.projectName ?? "—"}
                  {isRunning && typeof job.progress === "number" && ` · ${job.progress}%`}
                </p>
              </div>
              <span className="whitespace-nowrap text-[10px] text-muted-foreground tabular-nums">
                {formatRelative(job.created_at)}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
