"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Database,
  Network,
  Plug,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Zap,
} from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { CoverageBreakdown } from "@/components/dashboard/coverage-breakdown";
import { InsightCards } from "@/components/dashboard/insight-cards";
import { PipelineHealth } from "@/components/dashboard/pipeline-health";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { PIIHeatmap } from "@/components/dashboard/pii-heatmap";
import { ActivityTimelineChart } from "@/components/dashboard/activity-timeline-chart";
import { ComplianceRadial } from "@/components/dashboard/compliance-radial";
import { JobTypeBreakdown } from "@/components/dashboard/job-type-breakdown";
import {
  ProjectsBreakdown,
  type BreakdownSortKey,
} from "@/components/dashboard/projects-breakdown";
import {
  KpiBreakdownDialog,
  type KpiMetric,
} from "@/components/dashboard/kpi-breakdown-dialog";
import {
  ProjectActionDialog,
  type ProjectAction,
} from "@/components/dashboard/project-action-dialog";
import { SkeletonStatCard } from "@/components/common/skeleton-card";
import { EmptyState } from "@/components/common/empty-state";
import { DASHBOARD_JOB_PAGE_SIZE, useDashboardData } from "@/hooks/use-dashboard-data";
import { useAuthStore } from "@/stores/auth-store";

function formatRelative(d: Date | null): string {
  if (!d) return "—";
  const diffMs = Date.now() - d.getTime();
  const s = Math.floor(diffMs / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return d.toLocaleDateString();
}

const BREAKDOWN_ANCHOR = "projects-breakdown";

export default function DashboardPage() {
  const { data, refresh } = useDashboardData();
  const user = useAuthStore((s) => s.user);
  const loadUser = useAuthStore((s) => s.loadUser);

  // Sort state for the inline per-project leaderboard (shown only when there
  // are 2+ projects). The KPI breakdown POPUP is the primary drilldown affordance
  // and works regardless of project count.
  const [breakdownSort, setBreakdownSort] = useState<{ key: BreakdownSortKey; dir: "asc" | "desc" }>(
    { key: "unmasked", dir: "desc" },
  );

  // Which KPI breakdown dialog is open, if any. One dialog handles all four
  // metrics by switching on this state.
  const [openMetric, setOpenMetric] = useState<KpiMetric | null>(null);
  // Hero CTA project picker (Run discovery / Generate report).
  const [openAction, setOpenAction] = useState<ProjectAction | null>(null);

  useEffect(() => {
    if (!user) loadUser();
  }, [user, loadUser]);

  const handleSortChange = useCallback((key: BreakdownSortKey) => {
    setBreakdownSort((prev) =>
      prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" },
    );
  }, []);

  // Inline leaderboard only renders below 2+ projects; the popup is always available.
  const multiProject = data.aggregatedProjects > 1;

  const attentionCount = useMemo(
    () => data.insights.filter((i) => i.severity === "danger" || i.severity === "warn").length,
    [data.insights],
  );

  // Smart deep-link targets. If the metric has no relevant project, fall back to
  // /projects so the user can pick. Avoids the "everything → /projects" dead end.
  const link = useMemo(() => {
    const p = data.primaryProjects;
    const projectsHref = "/projects";
    const project = (id: string | null, sub = "") =>
      id ? `/projects/${id}${sub}` : projectsHref;
    return {
      projects: projectsHref,
      privacy: project(p.byCompliance, "/privacy-hub"),
      risk: project(p.byRisk, "/privacy-hub"),
      jobs: project(p.byActivity, "/jobs"),
      discovery: project(p.byMostRecent, "/discovery"),
      compliance: project(p.byMostRecent, "/compliance"),
      mostRecent: project(p.byMostRecent),
    };
  }, [data.primaryProjects]);

  const complianceTone =
    data.compliancePct === null
      ? "neutral"
      : data.compliancePct >= 95
        ? "good"
        : data.compliancePct >= 75
          ? "warn"
          : "danger";

  const riskTone =
    data.compliancePct === null
      ? "neutral"
      : data.totalUnprotected === 0
        ? "good"
        : data.totalUnprotected > 10
          ? "danger"
          : "warn";

  // First-run onboarding — no projects exist yet AND the API actually responded
  // successfully. If the API errored, totalProjects is 0 by default and we'd
  // mistakenly show onboarding instead of the real error.
  const isFirstRun = !data.loading && data.totalProjects === 0 && !data.error;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* HERO */}
        <DashboardHero
          name={user?.full_name ?? null}
          compliancePct={data.compliancePct}
          attentionCount={attentionCount}
          loading={data.loading}
          newProjectHref={link.projects}
          onRunDiscovery={() => setOpenAction("discovery")}
          onOpenReports={() => setOpenAction("reports")}
        />

        {/* Refresh + last updated meta row */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span
              className="relative inline-flex h-2 w-2 items-center justify-center"
              aria-hidden
            >
              <span
                className={`absolute inline-flex h-full w-full rounded-full ${
                  data.loading ? "animate-ping bg-[hsl(var(--chart-7))] opacity-75" : ""
                }`}
              />
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${
                  data.error
                    ? "bg-[hsl(var(--chart-6))]"
                    : data.loading
                      ? "bg-[hsl(var(--chart-7))]"
                      : "bg-[hsl(var(--chart-4))]"
                }`}
              />
            </span>
            <span aria-live="polite">
              {data.loading ? "Syncing…" : data.error ? "Disconnected" : "Live"} ·
              Last updated {formatRelative(data.lastUpdated)}
              {data.aggregatedProjects > 0 && data.totalProjects > data.aggregatedProjects && (
                <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-[10px]">
                  Showing {data.aggregatedProjects} of {data.totalProjects} projects
                </span>
              )}
            </span>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={data.loading}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-xs font-medium text-foreground hover:bg-muted/50 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            aria-label="Refresh dashboard data"
          >
            <RefreshCw className={`h-3 w-3 ${data.loading ? "animate-spin" : ""}`} aria-hidden />
            Refresh
          </button>
        </div>

        {/* GLOBAL ERROR (always visible above content when present) */}
        {data.error && !data.loading && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          >
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span className="flex-1">
              Couldn&rsquo;t reach the API: {data.error}. Showing the last successful snapshot where available.
            </span>
            <button
              type="button"
              onClick={refresh}
              className="rounded-md border border-destructive/40 bg-background px-2 py-0.5 text-xs hover:bg-destructive/10"
            >
              Retry
            </button>
          </div>
        )}

        {isFirstRun ? (
          <OnboardingPanel />
        ) : (
          <>

            {/* EXECUTIVE KPI ROW — F-pattern, most important top-left */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {data.loading ? (
                <>
                  <SkeletonStatCard />
                  <SkeletonStatCard />
                  <SkeletonStatCard />
                  <SkeletonStatCard />
                </>
              ) : (
                <>
                  <KpiCard
                    label="Compliance score"
                    value={
                      !data.privacyDataAvailable && data.aggregatedProjects > 0
                        ? "—"
                        : data.compliancePct === null
                          ? "—"
                          : `${data.compliancePct}%`
                    }
                    icon={ShieldCheck}
                    tone={complianceTone}
                    onClick={() => setOpenMetric("compliance")}
                    actionLabel="Show coverage breakdown by project"
                    hint={
                      !data.privacyDataAvailable && data.aggregatedProjects > 0
                        ? "Privacy data unreachable · click for details"
                        : data.compliancePct === null
                          ? data.aggregatedProjects === 0
                            ? "No projects yet · click to itemize"
                            : "Run discovery to begin · click to itemize"
                          : `${data.totalProtected.toLocaleString()} of ${data.totalSensitive.toLocaleString()} sensitive cols${data.projectsTruncated ? ` (top ${data.aggregatedProjects})` : ""} · click to itemize`
                    }
                  />
                  <KpiCard
                    label="Data at risk"
                    value={
                      !data.privacyDataAvailable && data.aggregatedProjects > 0
                        ? "—"
                        : data.compliancePct === null
                          ? "—"
                          : data.totalUnprotected.toLocaleString()
                    }
                    icon={ShieldAlert}
                    tone={riskTone}
                    onClick={() => setOpenMetric("risk")}
                    actionLabel="Show unmasked columns breakdown by project"
                    hint={
                      !data.privacyDataAvailable && data.aggregatedProjects > 0
                        ? "Privacy data unreachable · click for details"
                        : data.compliancePct === null
                          ? data.aggregatedProjects === 0
                            ? "No projects yet · click to itemize"
                            : "Run discovery to scan for PII · click to itemize"
                          : (data.totalUnprotected === 0
                              ? "All sensitive columns covered"
                              : `${data.totalUnprotected} unmasked sensitive ${data.totalUnprotected === 1 ? "column" : "columns"}`) +
                            (data.projectsTruncated ? ` (top ${data.aggregatedProjects} of ${data.totalProjects})` : "") +
                            " · click to itemize"
                    }
                  />
                  <KpiCard
                    label="Data velocity"
                    value={data.jobsDataAvailable ? data.velocity7d : "—"}
                    icon={Sparkles}
                    tone="accent"
                    spark={data.jobsDataAvailable ? data.velocitySpark : undefined}
                    hint={
                      data.jobsDataAvailable
                        ? `Successful runs in 7d · ${data.jobsToday} today${data.projectsTruncated ? ` (top ${data.aggregatedProjects} of ${data.totalProjects})` : ""} · click to itemize`
                        : data.aggregatedProjects === 0
                          ? "No projects yet · click to itemize"
                          : "Job data unreachable · click for details"
                    }
                    onClick={() => setOpenMetric("velocity")}
                    actionLabel="Show jobs breakdown by project"
                  />
                  <KpiCard
                    label="Pipeline activity"
                    value={data.jobsDataAvailable ? data.activeJobs.length : "—"}
                    icon={Activity}
                    tone="info"
                    spark={data.jobsDataAvailable ? data.jobsSpark : undefined}
                    hint={
                      data.jobsDataAvailable
                        ? (data.activeJobs.length === 0
                            ? `${data.jobs7d.length} jobs in last 7d`
                            : `${data.activeJobs.length} running now`) +
                          (data.projectsTruncated ? ` (top ${data.aggregatedProjects} of ${data.totalProjects})` : "") +
                          " · click to itemize"
                        : data.aggregatedProjects === 0
                          ? "No projects yet · click to itemize"
                          : "Job data unreachable · click for details"
                    }
                    onClick={() => setOpenMetric("active")}
                    actionLabel="Show active jobs breakdown by project"
                  />
                </>
              )}
            </div>

            {/* CHARTS ROW — Grafana-style live multi-series timeline + gauge + donut */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-6">
              <section
                aria-labelledby="timeline-heading"
                className="rounded-lg border border-border bg-card p-5 shadow-sm lg:col-span-4"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h2 id="timeline-heading" className="text-sm font-semibold text-foreground">
                      Job activity (14d)
                    </h2>
                    <p className="text-[11px] text-muted-foreground">
                      Stacked daily runs by status · click legend to toggle
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setOpenMetric("velocity")}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    Compare by project
                    <ArrowRight className="h-3 w-3" />
                  </button>
                </div>
                {data.loading ? (
                  <div className="h-64 animate-pulse rounded-md bg-muted" />
                ) : (
                  <>
                    {(data.jobsTruncated || data.projectsTruncated) && (
                      <div className="mb-2 inline-flex items-center gap-1.5 rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                        <AlertTriangle className="h-3 w-3" aria-hidden />
                        Partial data:
                        {data.projectsTruncated && ` showing ${data.aggregatedProjects} of ${data.totalProjects} projects`}
                        {data.jobsTruncated &&
                          (data.projectsTruncated ? "; " : " ") +
                            `some projects exceed ${DASHBOARD_JOB_PAGE_SIZE} jobs/page — older runs not included`}
                      </div>
                    )}
                    <ActivityTimelineChart
                      jobs={data.jobsHistory}
                      windowDays={data.historyWindowDays}
                    />
                  </>
                )}
              </section>

              <section
                aria-labelledby="gauge-heading"
                className="rounded-lg border border-border bg-card p-5 shadow-sm lg:col-span-2"
              >
                <div className="mb-3 flex items-center justify-between">
                  <h2 id="gauge-heading" className="text-sm font-semibold text-foreground">
                    Compliance gauge
                  </h2>
                </div>
                {data.loading ? (
                  <div className="h-48 animate-pulse rounded-md bg-muted" />
                ) : (
                  <ComplianceRadial
                    pct={data.compliancePct}
                    protectedCount={data.totalProtected}
                    sensitiveCount={data.totalSensitive}
                  />
                )}
              </section>
            </div>

            {/* CONSOLIDATED PER-PROJECT BREAKDOWN — sortable leaderboard.
                Drives the multi-project drilldown story: KPIs above show totals,
                this table shows the per-project distribution. Clicking a KPI
                scrolls here and re-sorts by that metric. */}
            {multiProject && (
              <section
                aria-labelledby="projects-breakdown-heading"
                className="rounded-lg border border-border bg-card p-5 shadow-sm"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <h2
                      id="projects-breakdown-heading"
                      className="text-sm font-semibold text-foreground"
                    >
                      Projects breakdown
                    </h2>
                    <p className="text-[11px] text-muted-foreground">
                      Per-project metrics across {data.aggregatedProjects} projects · click a column header to sort
                    </p>
                  </div>
                  <Link
                    href="/projects"
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    All projects
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
                {data.loading ? (
                  <div className="h-40 animate-pulse rounded-md bg-muted" />
                ) : (
                  <ProjectsBreakdown
                    rows={data.projectsBreakdown}
                    sortKey={breakdownSort.key}
                    sortDir={breakdownSort.dir}
                    onSortChange={handleSortChange}
                    anchorId={BREAKDOWN_ANCHOR}
                  />
                )}
              </section>
            )}

            {/* JOB TYPE BREAKDOWN — separate row so it gets full width on narrow screens */}
            <section
              aria-labelledby="breakdown-heading"
              className="rounded-lg border border-border bg-card p-5 shadow-sm"
            >
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h2 id="breakdown-heading" className="text-sm font-semibold text-foreground">
                    Job mix (7d)
                  </h2>
                  <p className="text-[11px] text-muted-foreground">
                    Distribution of work types · hover a slice or row to highlight
                  </p>
                </div>
              </div>
              {data.loading ? (
                <div className="h-48 animate-pulse rounded-md bg-muted" />
              ) : (
                <JobTypeBreakdown jobs={data.jobs7d} />
              )}
            </section>

            {/* ACTIONABLE INSIGHTS */}
            <section aria-labelledby="insights-heading" className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 id="insights-heading" className="text-sm font-semibold text-foreground">
                  What needs your attention
                </h2>
                {data.insights.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {data.insights.length} {data.insights.length === 1 ? "item" : "items"}
                  </span>
                )}
              </div>
              {data.loading ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-28 animate-pulse rounded-lg bg-muted" />
                  ))}
                </div>
              ) : (
                <InsightCards insights={data.insights} />
              )}
            </section>

            {/* COVERAGE BREAKDOWN + PII HEATMAP */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
              <section
                aria-labelledby="coverage-heading"
                className="rounded-lg border border-border bg-card p-5 shadow-sm lg:col-span-2"
              >
                <div className="mb-4 flex items-center justify-between">
                  <h2 id="coverage-heading" className="text-sm font-semibold text-foreground">
                    Coverage by table
                  </h2>
                  <button
                    type="button"
                    onClick={() => setOpenMetric("compliance")}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    Compare by project
                    <ArrowRight className="h-3 w-3" />
                  </button>
                </div>
                {data.loading ? (
                  <div className="space-y-3">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="h-8 animate-pulse rounded-md bg-muted" />
                    ))}
                  </div>
                ) : (
                  <CoverageBreakdown rows={data.coverageRows} />
                )}
              </section>

              <section
                aria-labelledby="heatmap-heading"
                className="rounded-lg border border-border bg-card p-5 shadow-sm lg:col-span-3"
              >
                <div className="mb-4 flex items-center justify-between">
                  <h2 id="heatmap-heading" className="text-sm font-semibold text-foreground">
                    PII density heatmap
                  </h2>
                  <span className="text-xs text-muted-foreground">
                    {data.heatmapTables.length > 0
                      ? `Top ${Math.min(20, data.heatmapTables.length)} tables`
                      : ""}
                  </span>
                </div>
                {data.loading ? (
                  <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5 md:grid-cols-6">
                    {Array.from({ length: 12 }).map((_, i) => (
                      <div key={i} className="h-12 animate-pulse rounded-md bg-muted" />
                    ))}
                  </div>
                ) : data.heatmapTables.length > 0 ? (
                  <PIIHeatmap tables={data.heatmapTables.slice(0, 20)} />
                ) : (
                  <EmptyState
                    icon={Database}
                    title="No discovery data"
                    description="Run discovery on a connection to map PII density across your tables."
                  />
                )}
              </section>
            </div>

            {/* PIPELINE HEALTH + ACTIVITY */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <section
                aria-labelledby="pipeline-heading"
                className="rounded-lg border border-border bg-card p-5 shadow-sm"
              >
                <div className="mb-4 flex items-center justify-between">
                  <h2 id="pipeline-heading" className="text-sm font-semibold text-foreground">
                    Pipeline health (7d)
                  </h2>
                  <button
                    type="button"
                    onClick={() => setOpenMetric("velocity")}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    Compare by project
                    <ArrowRight className="h-3 w-3" />
                  </button>
                </div>
                <PipelineHealth recentJobs={data.jobs7d} loading={data.loading} />
              </section>

              <section
                aria-labelledby="activity-heading"
                className="rounded-lg border border-border bg-card p-5 shadow-sm"
              >
                <div className="mb-4 flex items-center justify-between">
                  <h2 id="activity-heading" className="text-sm font-semibold text-foreground">
                    Recent activity
                  </h2>
                  <span className="text-xs text-muted-foreground">Auto-refreshes every 15s</span>
                </div>
                <ActivityFeed jobs={data.jobs7d} loading={data.loading} />
              </section>
            </div>
          </>
        )}
      </div>

      {/* Project picker — opened by "Run discovery" / "Reports" in the hero.
          Uses the FULL project list (not the aggregated subset) so projects
          beyond the deep-fan-out cap remain selectable. */}
      {openAction && (
        <ProjectActionDialog
          open={openAction !== null}
          onClose={() => setOpenAction(null)}
          action={openAction}
          projects={data.projectsList}
          breakdown={data.projectsBreakdown}
          totalProjects={data.totalProjects}
          error={data.error}
          loading={data.loading}
          onRetry={refresh}
        />
      )}

      {/* KPI breakdown popup — opened by clicking any of the 4 KPI cards or
          any "Compare by project" button. Works regardless of project count. */}
      {openMetric && (
        <KpiBreakdownDialog
          open={openMetric !== null}
          onClose={() => setOpenMetric(null)}
          metric={openMetric}
          rows={data.projectsBreakdown}
          globalLabel={kpiDialogLabel(openMetric, data)}
          globalSubLabel={kpiDialogSubLabel(openMetric, data)}
          error={data.error}
          loading={data.loading}
          projectsTruncated={data.projectsTruncated}
          onRetry={refresh}
        />
      )}
    </AppShell>
  );
}

function kpiDialogLabel(metric: KpiMetric, data: ReturnType<typeof useDashboardData>["data"]): string {
  switch (metric) {
    case "compliance":
      if (!data.privacyDataAvailable && data.aggregatedProjects > 0) return "—";
      return data.compliancePct === null ? "—" : `${data.compliancePct}%`;
    case "risk":
      if (!data.privacyDataAvailable && data.aggregatedProjects > 0) return "—";
      return data.compliancePct === null ? "—" : data.totalUnprotected.toLocaleString();
    case "velocity":
      if (!data.jobsDataAvailable && data.aggregatedProjects > 0) return "—";
      return data.aggregatedProjects === 0 ? "—" : String(data.velocity7d);
    case "active":
      if (!data.jobsDataAvailable && data.aggregatedProjects > 0) return "—";
      return data.aggregatedProjects === 0 ? "—" : String(data.activeJobs.length);
  }
}

function kpiDialogSubLabel(metric: KpiMetric, data: ReturnType<typeof useDashboardData>["data"]): string {
  const acrossN = `across ${data.aggregatedProjects} ${data.aggregatedProjects === 1 ? "project" : "projects"}`;
  const truncationNote = data.projectsTruncated
    ? ` (top ${data.aggregatedProjects} of ${data.totalProjects})`
    : "";
  switch (metric) {
    case "compliance":
      return data.compliancePct === null
        ? "No PII detected yet"
        : `${data.totalProtected.toLocaleString()} of ${data.totalSensitive.toLocaleString()} sensitive cols protected · ${acrossN}${truncationNote}`;
    case "risk":
      return data.compliancePct === null
        ? "Run discovery to scan for PII"
        : `unmasked sensitive columns · ${acrossN}${truncationNote}`;
    case "velocity":
      return `successful runs in last 7d · ${acrossN}${truncationNote}`;
    case "active":
      return `currently running or pending · ${acrossN}${truncationNote}`;
  }
}

function OnboardingPanel() {
  return (
    <section
      aria-labelledby="onboarding-heading"
      className="rounded-xl border border-border bg-card p-8 shadow-sm"
    >
      <div className="mx-auto max-w-2xl text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Sparkles className="h-6 w-6 text-primary" aria-hidden />
        </div>
        <h2 id="onboarding-heading" className="text-xl font-semibold text-foreground">
          Get started with Synthia in three steps
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Synthia turns sensitive production data into safe, high-fidelity test data — automatically classified,
          masked, and ready for development pipelines.
        </p>
      </div>

      <ol className="mx-auto mt-8 grid max-w-3xl gap-4 sm:grid-cols-3">
        <OnboardingStep
          n={1}
          icon={Database}
          title="Create a project"
          body="Group your connections, policies, and runs by application or environment."
        />
        <OnboardingStep
          n={2}
          icon={Plug}
          title="Connect a data source"
          body="Postgres, MySQL, SQL Server, files, and more. Test the connection, then run discovery."
        />
        <OnboardingStep
          n={3}
          icon={Network}
          title="Run discovery + mask"
          body="Synthia classifies PII and recommends masking. Promote test data into your pipeline."
        />
      </ol>

      <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
        <Link
          href="/projects"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90"
        >
          Create your first project
          <ArrowRight className="h-4 w-4" />
        </Link>
        <Link
          href="/projects"
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
        >
          <Zap className="h-4 w-4" />
          Browse templates
        </Link>
      </div>
    </section>
  );
}

function OnboardingStep({
  n,
  icon: Icon,
  title,
  body,
}: {
  n: number;
  icon: typeof Database;
  title: string;
  body: string;
}) {
  return (
    <li className="relative rounded-lg border border-border bg-background p-4 text-left">
      <div className="flex items-center gap-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary tabular-nums">
          {n}
        </span>
        <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
      </div>
      <h3 className="mt-3 text-sm font-medium text-foreground">{title}</h3>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{body}</p>
    </li>
  );
}
