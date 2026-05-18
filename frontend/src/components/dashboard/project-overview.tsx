"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Database,
  FileSearch,
  FileText,
  Loader2,
  Play,
  Shield,
  ShieldAlert,
  Table as TableIcon,
  Zap,
} from "lucide-react";

import { StatCard } from "@/components/dashboard/stat-card";
import { SkeletonStatCard } from "@/components/common/skeleton-card";
import { EmptyState } from "@/components/common/empty-state";
import { api } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

/**
 * Per-project overview dashboard mounted at /projects/[projectId].
 *
 * Stitches the project header, four headline stats, a privacy snapshot,
 * an active-jobs tile, and a recent-activity tile. All data comes from
 * endpoints that already exist in backend/app/api/v1/:
 *   GET /api/v1/projects/{id}                 — header
 *   GET /api/v1/projects/{id}/privacy-hub     — sensitive/protected counts + tables[]
 *   GET /api/v1/projects/{id}/jobs            — recent + active + today's count
 *
 * No /discovery/summary endpoint exists, so "tables discovered" and
 * "columns classified" are derived from the privacy-hub `tables[]` payload
 * which already aggregates per-table column counts across the project.
 */

interface ProjectResponse {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  settings: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

interface PrivacyHubTable {
  schema_name: string;
  table_name: string;
  total_columns: number;
  sensitive_columns: number;
  protected_columns: number;
  privacy_rating: number;
}

interface PrivacyHubResponse {
  sensitive_count: number;
  protected_count: number;
  unprotected_count: number;
  tables?: PrivacyHubTable[];
}

interface JobRow {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  started_at: string | null;
  created_at: string;
}

interface JobListResponse {
  items: JobRow[];
  total_count: number;
}

interface ProjectOverviewProps {
  projectId: string;
}

function formatRelative(iso: string): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffMs = Date.now() - then;
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function jobStatusClasses(status: string): string {
  switch (status) {
    case "running":
      return "bg-blue-500/10 text-blue-600 dark:text-blue-400";
    case "completed":
    case "succeeded":
      return "bg-green-500/10 text-green-600 dark:text-green-400";
    case "completed_with_warnings":
      // Amber: bundle ready, but some requested masking was skipped.
      return "bg-amber-500/10 text-amber-700 dark:text-amber-400";
    case "failed":
      return "bg-red-500/10 text-red-600 dark:text-red-400";
    case "cancelled":
      return "bg-muted text-muted-foreground";
    default:
      return "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400";
  }
}

export function ProjectOverview({ projectId }: ProjectOverviewProps) {
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [privacy, setPrivacy] = useState<PrivacyHubResponse | null>(null);
  // null = fetch failed (unknown), [] = fetch succeeded with no rows.
  const [activeJobs, setActiveJobs] = useState<JobRow[] | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobRow[] | null>(null);
  const [totalJobs, setTotalJobs] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // Track the projectId we have data for, so we can detect a prop change
  // and discard stale data DURING render. Resetting in useEffect leaves
  // one committed render where the previous project's data sits under the
  // new project's URL. Setting state during a render conditionally is the
  // supported React pattern for prop-driven state resets — React discards
  // the current render and re-renders with the new state before paint.
  // See: https://react.dev/reference/react/useState#storing-information-from-previous-renders
  const [activeProjectId, setActiveProjectId] = useState(projectId);
  if (projectId !== activeProjectId) {
    setActiveProjectId(projectId);
    setProject(null);
    setPrivacy(null);
    setActiveJobs(null);
    setRecentJobs(null);
    setTotalJobs(null);
    setLoading(true);
  }

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      // Each fetch is independent — failure of one tile must not blank the page.
      const [proj, hub, active, recent] = await Promise.all([
        api.get<ProjectResponse>(`/api/v1/projects/${projectId}`).catch(() => null),
        api
          .get<PrivacyHubResponse>(`/api/v1/projects/${projectId}/privacy-hub`)
          .catch(() => null),
        api
          .get<JobListResponse>(
            `/api/v1/projects/${projectId}/jobs?status=running&page_size=5`,
          )
          .catch(() => null),
        api
          .get<JobListResponse>(
            `/api/v1/projects/${projectId}/jobs?page=1&page_size=10`,
          )
          .catch(() => null),
      ]);

      if (cancelled) return;

      setProject(proj);
      setPrivacy(hub);
      // Null active/recent → fetch failed; preserve null so the tile can
      // render an error state instead of a false-empty state.
      setActiveJobs(active ? active.items : null);
      setRecentJobs(recent ? recent.items : null);

      // Differentiate "API returned 0" from "API failed" — null means unknown
      // and the stat card renders an em-dash instead of a false zero.
      setTotalJobs(recent ? recent.total_count : null);

      setLoading(false);
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Derived stats from the privacy-hub tables[] payload — no extra fetch.
  // null when the privacy fetch failed (renders as "—"), distinct from real 0.
  const tablesDiscovered: number | null = privacy ? privacy.tables?.length ?? 0 : null;
  const columnsClassified: number | null = privacy
    ? privacy.tables?.reduce((sum, t) => sum + (t.total_columns ?? 0), 0) ?? 0
    : null;
  const maskingCoverage: number | null = privacy
    ? privacy.sensitive_count > 0
      ? Math.round((privacy.protected_count / privacy.sensitive_count) * 100)
      : 0
    : null;

  // Environment is stored under settings — the projects API has no dedicated
  // column for it. Treat its absence as "—".
  const environment =
    (project?.settings?.environment as string | undefined) ?? null;

  return (
    <div className="space-y-6">
      {/* Project header */}
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            {project?.name ?? (loading ? "Loading..." : "Project unavailable")}
          </h1>
          {project?.description && (
            <p className="mt-1 text-sm text-muted-foreground">
              {project.description}
            </p>
          )}
        </div>
        <dl className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {environment && (
            <div className="flex items-center gap-1">
              <dt className="font-medium text-foreground/80">Environment</dt>
              <dd className="rounded-full border border-border bg-muted/40 px-2 py-0.5 capitalize">
                {environment}
              </dd>
            </div>
          )}
          <div className="flex items-center gap-1">
            <dt className="font-medium text-foreground/80">Owner</dt>
            <dd className="font-mono">
              {project?.owner_id ? project.owner_id.slice(0, 8) : "—"}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="font-medium text-foreground/80">Last modified</dt>
            <dd>{project?.updated_at ? formatRelative(project.updated_at) : "—"}</dd>
          </div>
        </dl>
      </header>

      {/* Stat row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          <>
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
          </>
        ) : (
          <>
            <StatCard
              label="Tables discovered"
              value={tablesDiscovered ?? "—"}
              icon={TableIcon}
              href={`/projects/${projectId}/discovery`}
            />
            <StatCard
              label="Columns classified"
              value={columnsClassified ?? "—"}
              icon={FileSearch}
              href={`/projects/${projectId}/discovery`}
            />
            <StatCard
              label="Masking coverage"
              value={maskingCoverage !== null ? `${maskingCoverage}%` : "—"}
              icon={Shield}
              href={`/projects/${projectId}/privacy-hub`}
            />
            <StatCard
              label="Total jobs"
              value={totalJobs ?? "—"}
              icon={Zap}
              href={`/projects/${projectId}/jobs`}
            />
          </>
        )}
      </div>

      {/* Two-column row: privacy snapshot + active jobs */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Privacy snapshot */}
        <section
          aria-labelledby="privacy-snapshot-title"
          className="rounded-lg border border-border bg-card p-5 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <h2
              id="privacy-snapshot-title"
              className="text-sm font-semibold text-foreground"
            >
              Privacy snapshot
            </h2>
            <Link
              href={`/projects/${projectId}/privacy-hub`}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              Review in Privacy Hub
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {loading ? (
            <div className="mt-4 py-2 text-xs text-muted-foreground">Loading…</div>
          ) : privacy ? (
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded-md border border-border bg-background p-3">
                <p className="text-xs text-muted-foreground">Sensitive</p>
                <p className="mt-1 text-xl font-semibold text-foreground">
                  {privacy.sensitive_count}
                </p>
              </div>
              <div className="rounded-md border border-border bg-background p-3">
                <p className="text-xs text-muted-foreground">Protected</p>
                <p className="mt-1 text-xl font-semibold text-green-600 dark:text-green-400">
                  {privacy.protected_count}
                </p>
              </div>
              <div className="rounded-md border border-border bg-background p-3">
                <p className="text-xs text-muted-foreground">Unprotected</p>
                <p
                  className={cn(
                    "mt-1 text-xl font-semibold",
                    privacy.unprotected_count > 0
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-foreground",
                  )}
                >
                  {privacy.unprotected_count}
                </p>
              </div>
            </div>
          ) : (
            // privacy === null means the fetch failed (run discovery still
            // returns a 200 with zero counts, not null), so this is an error,
            // not "no data yet".
            <EmptyState
              icon={ShieldAlert}
              title="Couldn't load privacy snapshot"
              description="The Privacy Hub data wasn't available. Refresh the page or check the Privacy Hub tab for details."
            />
          )}
        </section>

        {/* Active jobs */}
        <section
          aria-labelledby="active-jobs-title"
          className="rounded-lg border border-border bg-card p-5 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <h2
              id="active-jobs-title"
              className="text-sm font-semibold text-foreground"
            >
              Active jobs
            </h2>
            <Link
              href={`/projects/${projectId}/jobs`}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              View all
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {loading ? (
            <div className="mt-4 py-2 text-xs text-muted-foreground">Loading…</div>
          ) : activeJobs === null ? (
            <EmptyState
              icon={Activity}
              title="Couldn't load active jobs"
              description="The jobs service didn't respond. Refresh or visit the Jobs tab."
            />
          ) : activeJobs.length === 0 ? (
            <EmptyState
              icon={Activity}
              title="No active jobs"
              description="Jobs in flight will appear here while they run."
            />
          ) : (
            <ul className="mt-4 space-y-3">
              {activeJobs.map((job) => (
                <li key={job.id} className="flex items-center gap-3">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs text-foreground capitalize">
                      {job.job_type.replaceAll("_", " ")}
                    </p>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-blue-500 transition-all"
                        style={{ width: `${Math.min(100, Math.max(0, job.progress))}%` }}
                      />
                    </div>
                  </div>
                  <span className="whitespace-nowrap text-xs text-muted-foreground">
                    {job.progress}%
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* Recent activity */}
      <section
        aria-labelledby="recent-activity-title"
        className="rounded-lg border border-border bg-card p-5 shadow-sm"
      >
        <div className="flex items-center justify-between">
          <h2
            id="recent-activity-title"
            className="text-sm font-semibold text-foreground"
          >
            Recent activity
          </h2>
          <Link
            href={`/projects/${projectId}/jobs`}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            All jobs
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        {loading ? (
          <div className="mt-4 py-2 text-xs text-muted-foreground">Loading…</div>
        ) : recentJobs === null ? (
          <EmptyState
            icon={Activity}
            title="Couldn't load recent activity"
            description="The jobs service didn't respond. Refresh or visit the Jobs tab."
          />
        ) : recentJobs.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No jobs yet"
            description="Run discovery, masking, or generation and the last 10 jobs will land here."
          />
        ) : (
          <ul className="mt-4 divide-y divide-border">
            {recentJobs.map((job) => (
              <li
                key={job.id}
                className="flex items-center justify-between gap-3 py-2 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium capitalize text-foreground">
                    {job.job_type.replaceAll("_", " ")}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {formatRelative(job.created_at)}
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-medium capitalize",
                    jobStatusClasses(job.status),
                  )}
                >
                  {job.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Quick actions */}
      <section
        aria-labelledby="quick-actions-title"
        className="rounded-lg border border-border bg-card p-5 shadow-sm"
      >
        <h2
          id="quick-actions-title"
          className="text-sm font-semibold text-foreground"
        >
          Quick actions
        </h2>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Link
            href={`/projects/${projectId}/discovery`}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Play className="h-4 w-4" />
            Run discovery
          </Link>
          <Link
            href={`/projects/${projectId}/compliance`}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
          >
            <FileText className="h-4 w-4" />
            Generate compliance report
          </Link>
          <Link
            href={`/projects/${projectId}/privacy-hub`}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
          >
            <Database className="h-4 w-4" />
            Open Privacy Hub
          </Link>
        </div>
      </section>
    </div>
  );
}
