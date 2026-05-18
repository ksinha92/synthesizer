"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/hooks/use-api";
import type { JobRow } from "@/components/dashboard/pipeline-health";
import type { Insight } from "@/components/dashboard/insight-cards";
import type { CoverageRow } from "@/components/dashboard/coverage-breakdown";

export const DASHBOARD_JOB_PAGE_SIZE = 200;

const MAX_PROJECTS_TO_AGGREGATE = 20;
const JOB_PAGE_SIZE = DASHBOARD_JOB_PAGE_SIZE;
const PROJECT_PAGE_SIZE = 100;
const POLL_INTERVAL_MS = 15_000;
const STALE_CONNECTION_DAYS = 14;
const HISTORY_WINDOW_DAYS = 14;

interface ProjectSummary {
  id: string;
  name: string;
  description: string | null;
  updated_at: string;
  created_at: string;
}

interface ProjectsResponse {
  items: ProjectSummary[];
  total_count: number;
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

interface JobListResponse {
  items: Array<{
    id: string;
    job_type: string;
    status: string;
    progress: number;
    started_at: string | null;
    completed_at?: string | null;
    created_at: string;
  }>;
  total_count: number;
}

interface ConnectionSummary {
  id: string;
  name: string;
  last_tested_at?: string | null;
  updated_at?: string;
}

interface ConnectionsResponse {
  items: ConnectionSummary[];
}

interface HeatmapTable {
  id: string;
  projectId: string;
  table_name: string;
  total_columns: number;
  pii_columns: number;
  unmasked_count: number;
}

export interface ProjectBreakdownRow {
  id: string;
  name: string;
  /** Sensitive columns detected (across all tables). null when privacy fetch failed. */
  sensitive: number | null;
  /** Protected (masked) sensitive columns. null when privacy fetch failed. */
  protected: number | null;
  /** Unmasked sensitive columns = sensitive - protected. null when unknown. */
  unmasked: number | null;
  /** Coverage % = protected / sensitive. null when sensitive is 0 or unknown. */
  coveragePct: number | null;
  /** Total jobs created in the last 7 days. null when jobs fetch failed. */
  jobs7d: number | null;
  /** Currently-running / pending jobs. null when jobs fetch failed. */
  activeJobs: number | null;
  /** Most recent job timestamp. null when no jobs. */
  lastJobAt: string | null;
  updatedAt: string;
}

export interface PrimaryProjects {
  /** Project with the most sensitive columns — best target for compliance/coverage drilldowns. */
  byCompliance: string | null;
  /** Project with the most unmasked sensitive columns — best target for "data at risk". */
  byRisk: string | null;
  /** Project with the most job activity in the last 7 days — best target for velocity/pipeline drilldowns. */
  byActivity: string | null;
  /** Most recently updated project — generic fallback for "drill into the app". */
  byMostRecent: string | null;
}

export interface DashboardData {
  projectCount: number;
  totalSensitive: number;
  totalProtected: number;
  totalUnprotected: number;
  compliancePct: number | null;
  jobs7d: JobRow[];
  jobsHistory: JobRow[]; // last HISTORY_WINDOW_DAYS days — used by the timeline chart
  historyWindowDays: number;
  jobsToday: number;
  activeJobs: JobRow[];
  velocity7d: number;
  velocitySpark: number[];
  jobsSpark: number[];
  heatmapTables: HeatmapTable[];
  coverageRows: CoverageRow[];
  insights: Insight[];
  totalProjects: number;
  aggregatedProjects: number;
  /** True when at least one project returned exactly JOB_PAGE_SIZE — older jobs may exist beyond the page. */
  jobsTruncated: boolean;
  /** True when totalProjects > aggregatedProjects. */
  projectsTruncated: boolean;
  /** True when at least one project's privacy-hub fetch succeeded. False = every
   *  project's privacy data is unreachable, so compliance/risk numbers are
   *  unknown rather than "zero". */
  privacyDataAvailable: boolean;
  /** True when at least one project's jobs fetch succeeded. False = every
   *  project's jobs are unreachable, so velocity/active numbers are unknown
   *  rather than "zero". */
  jobsDataAvailable: boolean;
  /** Per-metric "best project to drill into" for top-level KPI/CTA links. */
  primaryProjects: PrimaryProjects;
  /** Per-project metrics for the consolidated leaderboard below the KPI row.
   *  Capped at MAX_PROJECTS_TO_AGGREGATE for fan-out cost. */
  projectsBreakdown: ProjectBreakdownRow[];
  /** Lightweight ALL-projects list (id+name+timestamps only). Used by the project
   *  picker so it never drops projects beyond the aggregated subset. */
  projectsList: Array<{ id: string; name: string; updated_at: string; created_at: string }>;
  lastUpdated: Date | null;
  loading: boolean;
  error: string | null;
}

function dayKey(iso: string): string {
  return iso.slice(0, 10);
}

function buildDailyBuckets(days: number, jobs: JobRow[], predicate?: (j: JobRow) => boolean): number[] {
  const buckets: number[] = new Array(days).fill(0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  for (const job of jobs) {
    if (predicate && !predicate(job)) continue;
    const t = new Date(job.created_at);
    if (Number.isNaN(t.getTime())) continue;
    t.setHours(0, 0, 0, 0);
    const diffDays = Math.floor((today.getTime() - t.getTime()) / 86_400_000);
    if (diffDays >= 0 && diffDays < days) {
      buckets[days - 1 - diffDays]++;
    }
  }
  return buckets;
}

function deriveInsights(args: {
  projects: ProjectSummary[];
  perProject: Map<
    string,
    {
      privacy: PrivacyHubResponse | null;
      connections: ConnectionSummary[] | null;
      jobs: JobRow[] | null;
    }
  >;
}): Insight[] {
  const insights: Insight[] = [];
  const now = Date.now();
  const cutoff = now - STALE_CONNECTION_DAYS * 86_400_000;

  // ── Stale connections ──────────────────────────────────────────────────
  let staleConnections = 0;
  let staleProjectId: string | null = null;
  for (const project of args.projects) {
    const cs = args.perProject.get(project.id)?.connections;
    if (!cs) continue;
    for (const c of cs) {
      const ts = c.last_tested_at ?? c.updated_at ?? null;
      if (!ts || new Date(ts).getTime() < cutoff) {
        staleConnections++;
        if (!staleProjectId) staleProjectId = project.id;
      }
    }
  }
  if (staleConnections > 0 && staleProjectId) {
    insights.push({
      id: "stale-connections",
      severity: "warn",
      title: `${staleConnections} ${staleConnections === 1 ? "connection" : "connections"} need rescanning`,
      body: `Discovery hasn't run in over ${STALE_CONNECTION_DAYS} days. Schemas may have drifted — rerun to surface new PII.`,
      ctaLabel: "Open Connections",
      ctaHref: `/projects/${staleProjectId}/connections`,
    });
  }

  // ── Unmasked sensitive columns ─────────────────────────────────────────
  let topUnmaskedProject: { id: string; name: string; count: number } | null = null;
  let totalUnmasked = 0;
  for (const project of args.projects) {
    const p = args.perProject.get(project.id)?.privacy;
    if (!p) continue;
    totalUnmasked += p.unprotected_count;
    if (!topUnmaskedProject || p.unprotected_count > topUnmaskedProject.count) {
      if (p.unprotected_count > 0) {
        topUnmaskedProject = { id: project.id, name: project.name, count: p.unprotected_count };
      }
    }
  }
  if (totalUnmasked > 0 && topUnmaskedProject) {
    insights.push({
      id: "unmasked-sensitive",
      severity: totalUnmasked > 10 ? "danger" : "warn",
      title: `${totalUnmasked} sensitive ${totalUnmasked === 1 ? "column is" : "columns are"} unmasked`,
      body: `Highest concentration in “${topUnmaskedProject.name}” (${topUnmaskedProject.count}). Create or extend a masking policy to bring coverage to 100%.`,
      ctaLabel: "Open Privacy Hub",
      ctaHref: `/projects/${topUnmaskedProject.id}/privacy-hub`,
    });
  }

  // ── Failed jobs in last 24h ────────────────────────────────────────────
  const dayCutoff = now - 86_400_000;
  const allRecent: JobRow[] = [];
  for (const project of args.projects) {
    const js = args.perProject.get(project.id)?.jobs;
    if (js) allRecent.push(...js);
  }
  const failed24h = allRecent.filter(
    (j) => j.status === "failed" && new Date(j.created_at).getTime() >= dayCutoff,
  );
  if (failed24h.length > 0) {
    const top = failed24h[0];
    insights.push({
      id: "failed-jobs",
      severity: "danger",
      title: `${failed24h.length} ${failed24h.length === 1 ? "job" : "jobs"} failed in the last 24h`,
      body: `Most recent: ${top.job_type.replaceAll("_", " ")}${top.projectName ? ` in ${top.projectName}` : ""}. Review logs to diagnose.`,
      ctaLabel: "Investigate failures",
      ctaHref: `/projects/${top.projectId}/jobs`,
    });
  }

  // ── No projects yet (onboarding hint) ──────────────────────────────────
  if (args.projects.length === 0) {
    insights.push({
      id: "no-projects",
      severity: "info",
      title: "No projects yet",
      body: "Create your first project to connect a data source and run discovery.",
      ctaLabel: "Create project",
      ctaHref: "/projects",
    });
  }

  // ── Projects without any connection ────────────────────────────────────
  let needsConnection: ProjectSummary | null = null;
  for (const project of args.projects) {
    const cs = args.perProject.get(project.id)?.connections;
    if (cs !== null && cs !== undefined && cs.length === 0) {
      needsConnection = project;
      break;
    }
  }
  if (needsConnection) {
    insights.push({
      id: `no-connection-${needsConnection.id}`,
      severity: "info",
      title: `“${needsConnection.name}” has no connections`,
      body: "Connect a database to start discovering tables and classifying PII.",
      ctaLabel: "Add connection",
      ctaHref: `/projects/${needsConnection.id}/connections`,
    });
  }

  return insights;
}

export function useDashboardData() {
  const [data, setData] = useState<DashboardData>({
    projectCount: 0,
    totalSensitive: 0,
    totalProtected: 0,
    totalUnprotected: 0,
    compliancePct: null,
    jobs7d: [],
    jobsHistory: [],
    historyWindowDays: HISTORY_WINDOW_DAYS,
    jobsToday: 0,
    activeJobs: [],
    velocity7d: 0,
    velocitySpark: [],
    jobsSpark: [],
    heatmapTables: [],
    coverageRows: [],
    insights: [],
    totalProjects: 0,
    aggregatedProjects: 0,
    jobsTruncated: false,
    projectsTruncated: false,
    privacyDataAvailable: false,
    jobsDataAvailable: false,
    primaryProjects: {
      byCompliance: null,
      byRisk: null,
      byActivity: null,
      byMostRecent: null,
    },
    projectsBreakdown: [],
    projectsList: [],
    lastUpdated: null,
    loading: true,
    error: null,
  });

  const inFlightRef = useRef<AbortController | null>(null);

  const aggregate = useCallback(async (silent = false) => {
    // Cancel any in-flight refresh to avoid stale writes
    inFlightRef.current?.abort();
    const ctrl = new AbortController();
    inFlightRef.current = ctrl;

    if (!silent) setData((d) => ({ ...d, loading: true, error: null }));

    try {
      // 1) Projects
      const projectsRes = await api.get<ProjectsResponse>(
        `/api/v1/projects?page=1&page_size=${PROJECT_PAGE_SIZE}`,
      );
      if (ctrl.signal.aborted) return;
      const projects = projectsRes.items;
      const totalProjects = projectsRes.total_count ?? projects.length;
      const toAggregate = projects.slice(0, MAX_PROJECTS_TO_AGGREGATE);

      // 2) Per-project fan-out: privacy + jobs + connections in parallel
      const perProject = new Map<
        string,
        {
          privacy: PrivacyHubResponse | null;
          connections: ConnectionSummary[] | null;
          jobs: JobRow[] | null;
          /** True when the jobs response returned exactly JOB_PAGE_SIZE rows — there may be more. */
          jobsTruncated: boolean;
        }
      >();

      await Promise.all(
        toAggregate.map(async (project) => {
          const [privacy, conns, jobsRaw] = await Promise.all([
            api
              .get<PrivacyHubResponse>(`/api/v1/projects/${project.id}/privacy-hub`)
              .catch(() => null),
            api
              .get<ConnectionsResponse>(
                `/api/v1/projects/${project.id}/connections?page=1&page_size=50`,
              )
              .then((r) => r.items ?? [])
              .catch(() => null),
            api
              .get<JobListResponse>(
                `/api/v1/projects/${project.id}/jobs?page=1&page_size=${JOB_PAGE_SIZE}`,
              )
              .catch(() => null),
          ]);
          if (ctrl.signal.aborted) return;
          const jobs = jobsRaw
            ? jobsRaw.items.map<JobRow>((j) => ({
                id: j.id,
                projectId: project.id,
                projectName: project.name,
                job_type: j.job_type,
                status: j.status,
                progress: j.progress,
                started_at: j.started_at,
                completed_at: j.completed_at ?? null,
                created_at: j.created_at,
              }))
            : null;
          const jobsTruncated = jobsRaw ? jobsRaw.items.length >= JOB_PAGE_SIZE : false;
          perProject.set(project.id, { privacy, connections: conns, jobs, jobsTruncated });
        }),
      );
      if (ctrl.signal.aborted) return;

      // 3) Aggregate metrics
      let totalSensitive = 0;
      let totalProtected = 0;
      let totalUnprotected = 0;
      const heatmapTables: HeatmapTable[] = [];
      const coverageRows: CoverageRow[] = [];

      for (const project of toAggregate) {
        const entry = perProject.get(project.id);
        const p = entry?.privacy;
        if (!p) continue;
        totalSensitive += p.sensitive_count;
        totalProtected += p.protected_count;
        totalUnprotected += p.unprotected_count;
        for (const t of p.tables ?? []) {
          coverageRows.push({
            projectId: project.id,
            tableLabel: t.schema_name ? `${t.schema_name}.${t.table_name}` : t.table_name,
            total: t.total_columns,
            sensitive: t.sensitive_columns,
            protected: t.protected_columns,
          });
          if (t.total_columns > 0) {
            heatmapTables.push({
              id: `${project.id}-${t.schema_name}-${t.table_name}`,
              projectId: project.id,
              table_name: t.table_name,
              total_columns: t.total_columns,
              pii_columns: t.sensitive_columns,
              unmasked_count: Math.max(0, t.sensitive_columns - t.protected_columns),
            });
          }
        }
      }

      const allJobs: JobRow[] = [];
      for (const project of toAggregate) {
        const js = perProject.get(project.id)?.jobs;
        if (js) allJobs.push(...js);
      }

      const cutoff7d = Date.now() - 7 * 86_400_000;
      const cutoffHistory = Date.now() - HISTORY_WINDOW_DAYS * 86_400_000;
      const jobs7d = allJobs.filter((j) => new Date(j.created_at).getTime() >= cutoff7d);
      const jobsHistory = allJobs.filter(
        (j) => new Date(j.created_at).getTime() >= cutoffHistory,
      );
      const today = new Date().toISOString().slice(0, 10);
      const jobsToday = allJobs.filter((j) => dayKey(j.created_at) === today).length;
      const activeJobs = allJobs.filter(
        (j) => j.status === "running" || j.status === "pending",
      );

      const jobsTruncated = Array.from(perProject.values()).some((p) => p.jobsTruncated);
      const projectsTruncated = totalProjects > toAggregate.length;
      const privacyDataAvailable = Array.from(perProject.values()).some(
        (p) => p.privacy !== null,
      );
      const jobsDataAvailable = Array.from(perProject.values()).some((p) => p.jobs !== null);

      // ── Per-project breakdown rows ───────────────────────────────────────
      // One row per aggregated project, with the metrics needed by the
      // consolidated leaderboard table. Nulls distinguish "fetch failed" from
      // legitimate zeros so the UI can show "—" instead of a false "0".
      const projectsBreakdown: ProjectBreakdownRow[] = toAggregate.map((project) => {
        const entry = perProject.get(project.id);
        const privacy = entry?.privacy ?? null;
        const jobs = entry?.jobs ?? null;
        const sensitive = privacy ? privacy.sensitive_count : null;
        const protectedCount = privacy ? privacy.protected_count : null;
        const unmasked =
          privacy != null ? Math.max(0, privacy.sensitive_count - privacy.protected_count) : null;
        const coveragePct =
          privacy && privacy.sensitive_count > 0
            ? Math.round((privacy.protected_count / privacy.sensitive_count) * 100)
            : privacy
              ? null // sensitive == 0; coverage isn't a useful number
              : null;
        const jobs7dCount = jobs
          ? jobs.filter((j) => new Date(j.created_at).getTime() >= cutoff7d).length
          : null;
        const activeCount = jobs
          ? jobs.filter((j) => j.status === "running" || j.status === "pending").length
          : null;
        const lastJobAt = jobs && jobs.length > 0
          ? jobs.reduce((latest, j) =>
              new Date(j.created_at).getTime() > new Date(latest).getTime() ? j.created_at : latest,
            jobs[0].created_at)
          : null;
        return {
          id: project.id,
          name: project.name,
          sensitive,
          protected: protectedCount,
          unmasked,
          coveragePct,
          jobs7d: jobs7dCount,
          activeJobs: activeCount,
          lastJobAt,
          updatedAt: project.updated_at,
        };
      });

      // ── Smart drilldown targets ──────────────────────────────────────────
      // Pick the project most relevant to each metric so top-level links
      // jump to the right detail page instead of dumping users on /projects.
      const cutoff7dPrimary = Date.now() - 7 * 86_400_000;
      const primaryProjects: PrimaryProjects = (() => {
        let bestCompliance: { id: string; score: number } | null = null;
        let bestRisk: { id: string; score: number } | null = null;
        let bestActivity: { id: string; score: number } | null = null;
        for (const project of toAggregate) {
          const entry = perProject.get(project.id);
          const p = entry?.privacy;
          if (p) {
            // Compliance drilldown: where the most sensitive data lives — that's where
            // policy decisions matter most.
            if (!bestCompliance || p.sensitive_count > bestCompliance.score) {
              if (p.sensitive_count > 0)
                bestCompliance = { id: project.id, score: p.sensitive_count };
            }
            // Risk drilldown: where the most UNMASKED sensitive cols live.
            if (!bestRisk || p.unprotected_count > bestRisk.score) {
              if (p.unprotected_count > 0)
                bestRisk = { id: project.id, score: p.unprotected_count };
            }
          }
          const recent = (entry?.jobs ?? []).filter(
            (j) => new Date(j.created_at).getTime() >= cutoff7dPrimary,
          ).length;
          if (recent > 0 && (!bestActivity || recent > bestActivity.score)) {
            bestActivity = { id: project.id, score: recent };
          }
        }
        // Fallback: most-recently-updated project across the full project list,
        // not just the aggregated subset.
        const byMostRecent =
          [...projects].sort(
            (a, b) =>
              new Date(b.updated_at ?? 0).getTime() - new Date(a.updated_at ?? 0).getTime(),
          )[0]?.id ?? null;
        return {
          byCompliance: bestCompliance?.id ?? byMostRecent,
          byRisk: bestRisk?.id ?? byMostRecent,
          byActivity: bestActivity?.id ?? byMostRecent,
          byMostRecent,
        };
      })();

      // ``completed_with_warnings`` is terminal-completed (artifact
      // exists); count it toward velocity so a run with skipped
      // masking doesn't disappear from the dashboard's throughput
      // metrics. The warning surfaces via the per-job status pill.
      const isCompletedLike = (j: { status: string }) =>
        j.status === "completed" ||
        j.status === "completed_with_warnings" ||
        j.status === "succeeded";
      const velocity7d = jobs7d.filter(isCompletedLike).length;
      const velocitySpark = buildDailyBuckets(7, allJobs, isCompletedLike);
      const jobsSpark = buildDailyBuckets(7, allJobs);

      const compliancePct =
        totalSensitive > 0 ? Math.round((totalProtected / totalSensitive) * 100) : null;

      const insights = deriveInsights({ projects: toAggregate, perProject });

      if (ctrl.signal.aborted) return;

      setData({
        projectCount: projects.length,
        totalSensitive,
        totalProtected,
        totalUnprotected,
        compliancePct,
        jobs7d,
        jobsHistory,
        historyWindowDays: HISTORY_WINDOW_DAYS,
        jobsToday,
        activeJobs,
        velocity7d,
        velocitySpark,
        jobsSpark,
        heatmapTables,
        coverageRows,
        insights,
        totalProjects,
        aggregatedProjects: toAggregate.length,
        jobsTruncated,
        projectsTruncated,
        privacyDataAvailable,
        jobsDataAvailable,
        primaryProjects,
        projectsBreakdown,
        projectsList: projects.map((p) => ({
          id: p.id,
          name: p.name,
          updated_at: p.updated_at,
          created_at: p.created_at,
        })),
        lastUpdated: new Date(),
        loading: false,
        error: null,
      });
    } catch (err) {
      if (ctrl.signal.aborted) return;
      const message = err instanceof Error ? err.message : "Failed to load dashboard";
      if (message === "Unauthorized") return; // redirect handled by apiFetch
      setData((d) => ({ ...d, loading: false, error: message }));
    }
  }, []);

  // Initial load + polling
  useEffect(() => {
    aggregate(false);
    const id = window.setInterval(() => aggregate(true), POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(id);
      inFlightRef.current?.abort();
    };
  }, [aggregate]);

  // Refresh when tab regains focus
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") aggregate(true);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [aggregate]);

  const refresh = useCallback(() => aggregate(false), [aggregate]);

  return { data, refresh };
}
