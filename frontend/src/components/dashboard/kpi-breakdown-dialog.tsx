"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Lock,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { cn } from "@/lib/utils";
import type { ProjectBreakdownRow } from "@/hooks/use-dashboard-data";

export type KpiMetric = "compliance" | "risk" | "velocity" | "active";

interface KpiBreakdownDialogProps {
  open: boolean;
  onClose: () => void;
  metric: KpiMetric;
  rows: ProjectBreakdownRow[];
  globalLabel: string;
  globalSubLabel: string;
  /** Non-null when the aggregator failed; surfaces an inline error banner. */
  error?: string | null;
  /** Whether the aggregator is mid-fetch right now (silent or otherwise). */
  loading?: boolean;
  /** When set, dialog shows a "Showing N of M projects" caveat in the header. */
  projectsTruncated?: boolean;
  /** Optional retry handler — when present, the error banner gets a Retry button. */
  onRetry?: () => void;
}

interface MetricMeta {
  title: string;
  description: string;
  icon: LucideIcon;
  columnHeader: string;
  /** Supporting columns to show alongside the focused metric. */
  supporting: Array<"sensitive" | "unmasked" | "coverage" | "jobs7d" | "active" | "lastActivity">;
  /** Empty hint shown in dialog body when no projects exist. */
  emptyHint: string;
}

const METRICS: Record<KpiMetric, MetricMeta> = {
  compliance: {
    title: "Compliance score by project",
    description: "Coverage = protected / sensitive columns. Higher is better.",
    icon: ShieldCheck,
    columnHeader: "Coverage",
    supporting: ["sensitive", "unmasked"],
    emptyHint: "Create a project and run discovery to start scoring compliance.",
  },
  risk: {
    title: "Data at risk by project",
    description: "Unmasked sensitive columns — these need a masking policy.",
    icon: ShieldCheck,
    columnHeader: "Unmasked",
    supporting: ["sensitive", "coverage"],
    emptyHint: "Create a project and run discovery to start scanning for PII.",
  },
  velocity: {
    title: "Data velocity by project",
    description: "Jobs created in the last 7 days. Higher = more activity.",
    icon: Sparkles,
    columnHeader: "Jobs 7d",
    supporting: ["active", "lastActivity"],
    emptyHint: "Trigger a discovery, masking, or generation run to populate velocity.",
  },
  active: {
    title: "Pipeline activity by project",
    description: "Jobs currently running or pending across projects.",
    icon: Zap,
    columnHeader: "Active",
    supporting: ["jobs7d", "lastActivity"],
    emptyHint: "Run a job to see live activity here.",
  },
};

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
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

function sortRows(rows: ProjectBreakdownRow[], metric: KpiMetric): ProjectBreakdownRow[] {
  // Always desc on the focused metric; nulls (fetch failed) drop to the bottom.
  const score = (r: ProjectBreakdownRow): number | null => {
    switch (metric) {
      case "compliance":
        return r.coveragePct;
      case "risk":
        return r.unmasked;
      case "velocity":
        return r.jobs7d;
      case "active":
        return r.activeJobs;
    }
  };
  return [...rows].sort((a, b) => {
    const av = score(a);
    const bv = score(b);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return bv - av;
  });
}

function FocusedCell({ metric, row }: { metric: KpiMetric; row: ProjectBreakdownRow }) {
  switch (metric) {
    case "compliance":
      // coveragePct === null has two distinct meanings:
      //   1) sensitive === null  → privacy fetch failed; show "—"
      //   2) sensitive === 0     → no PII to cover; show "N/A"
      // These were previously collapsed into the same "—" badge.
      if (row.coveragePct === null) {
        if (row.sensitive === null) return <span className="text-muted-foreground" title="Privacy data unreachable">—</span>;
        return (
          <span className="inline-flex items-center gap-1 text-muted-foreground" title="No PII detected in this project">
            <span className="text-[10px] uppercase tracking-wide">N/A</span>
            <span className="text-[10px]">no PII</span>
          </span>
        );
      }
      return <CoverageBadge pct={row.coveragePct} />;
    case "risk":
      if (row.unmasked === null) return <span className="text-muted-foreground">—</span>;
      return row.unmasked > 0 ? (
        <span className="font-medium text-red-600 dark:text-red-400 tabular-nums">{row.unmasked}</span>
      ) : (
        <span className="font-medium text-emerald-600 dark:text-emerald-400 tabular-nums">0</span>
      );
    case "velocity":
      if (row.jobs7d === null) return <span className="text-muted-foreground">—</span>;
      return <span className="font-medium tabular-nums text-foreground">{row.jobs7d}</span>;
    case "active":
      if (row.activeJobs === null) return <span className="text-muted-foreground">—</span>;
      return row.activeJobs > 0 ? (
        <span className="inline-flex items-center gap-1 font-medium text-[hsl(var(--chart-7))] tabular-nums">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[hsl(var(--chart-7))]" />
          {row.activeJobs}
        </span>
      ) : (
        <span className="text-muted-foreground tabular-nums">0</span>
      );
  }
}

function SupportingCell({
  kind,
  row,
}: {
  kind: "sensitive" | "unmasked" | "coverage" | "jobs7d" | "active" | "lastActivity";
  row: ProjectBreakdownRow;
}) {
  switch (kind) {
    case "sensitive":
      return (
        <span className="tabular-nums text-foreground">
          {row.sensitive ?? <span className="text-muted-foreground">—</span>}
        </span>
      );
    case "unmasked":
      return row.unmasked === null ? (
        <span className="text-muted-foreground">—</span>
      ) : row.unmasked > 0 ? (
        <span className="text-red-600 dark:text-red-400 tabular-nums">{row.unmasked}</span>
      ) : (
        <span className="text-emerald-600 dark:text-emerald-400 tabular-nums">0</span>
      );
    case "coverage":
      if (row.coveragePct === null) {
        // Same distinction as the focused-cell variant.
        if (row.sensitive === null) return <span className="text-muted-foreground" title="Privacy data unreachable">—</span>;
        return <span className="text-muted-foreground text-[10px]" title="No PII detected in this project">N/A</span>;
      }
      return <CoverageBadge pct={row.coveragePct} compact />;
    case "jobs7d":
      return (
        <span className="tabular-nums text-foreground">
          {row.jobs7d ?? <span className="text-muted-foreground">—</span>}
        </span>
      );
    case "active":
      return row.activeJobs === null ? (
        <span className="text-muted-foreground">—</span>
      ) : row.activeJobs > 0 ? (
        <span className="inline-flex items-center gap-1 text-[hsl(var(--chart-7))] tabular-nums">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[hsl(var(--chart-7))]" />
          {row.activeJobs}
        </span>
      ) : (
        <span className="text-muted-foreground tabular-nums">0</span>
      );
    case "lastActivity":
      return <span className="text-muted-foreground tabular-nums">{formatRelative(row.lastJobAt)}</span>;
  }
}

const SUPPORTING_LABEL: Record<NonNullable<MetricMeta["supporting"][number]>, string> = {
  sensitive: "Sensitive",
  unmasked: "Unmasked",
  coverage: "Coverage",
  jobs7d: "Jobs 7d",
  active: "Active",
  lastActivity: "Last activity",
};

export function KpiBreakdownDialog({
  open,
  onClose,
  metric,
  rows,
  globalLabel,
  globalSubLabel,
  error = null,
  loading = false,
  projectsTruncated = false,
  onRetry,
}: KpiBreakdownDialogProps) {
  const meta = METRICS[metric];
  const sorted = useMemo(() => sortRows(rows, metric), [rows, metric]);
  const titleId = `kpi-breakdown-${metric}-title`;

  // Distinguish the empty body states. Critical: "every row's metric is null"
  // is fetch failure (the privacy/jobs API returned no data), NOT "user has no
  // activity yet" — a project with zero jobs returns an empty list (0), not null.
  type EmptyMode = "loading" | "error" | "no-projects" | "fetches-failed" | null;
  const emptyMode: EmptyMode = (() => {
    if (sorted.length > 0) {
      const allMetricNull = sorted.every((r) => {
        switch (metric) {
          case "compliance":
            // Coverage is also null when sensitive===0 (no PII detected) which is
            // legitimate, not a fetch failure. We only flag fetch failure when
            // privacy itself was unreachable (sensitive === null).
            return r.sensitive === null;
          case "risk":
            return r.unmasked === null;
          case "velocity":
            return r.jobs7d === null;
          case "active":
            return r.activeJobs === null;
        }
      });
      return allMetricNull ? "fetches-failed" : null;
    }
    if (loading) return "loading";
    if (error) return "error";
    return "no-projects";
  })();

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        className="fixed inset-0 z-[55] bg-black/50 transition-opacity"
        onClick={onClose}
      />
      <AccessibleDialog
        open={open}
        onClose={onClose}
        titleId={titleId}
        className="fixed inset-x-0 top-[8%] z-[60] mx-auto flex w-[92%] max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
      >
        <div style={{ maxHeight: "84vh" }} className="flex flex-col">
          {/* Header */}
          <header className="flex items-start justify-between border-b border-border px-5 py-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <meta.icon className="h-4 w-4 text-primary" aria-hidden />
              </div>
              <div>
                <h2 id={titleId} className="text-base font-semibold text-foreground">
                  {meta.title}
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">{meta.description}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close breakdown"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          {/* Global total summary */}
          <div className="flex items-baseline gap-3 border-b border-border bg-muted/20 px-5 py-3">
            <span className="text-2xl font-semibold tabular-nums text-foreground">{globalLabel}</span>
            <span className="text-xs text-muted-foreground">{globalSubLabel}</span>
          </div>

          {/* Error banner — visible whenever the aggregator reported an error,
              even if we still have stale data to show below. */}
          {error && (
            <div
              role="alert"
              className="flex items-center gap-2 border-b border-destructive/30 bg-destructive/5 px-5 py-2 text-xs text-destructive"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="flex-1">
                {sorted.length > 0
                  ? `Data may be stale — couldn't reach the API: ${error}`
                  : `Couldn't reach the API: ${error}`}
              </span>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="inline-flex items-center gap-1 rounded-md border border-destructive/30 bg-background px-2 py-0.5 text-[11px] font-medium hover:bg-destructive/10"
                >
                  <RefreshCw className="h-3 w-3" />
                  Retry
                </button>
              )}
            </div>
          )}

          {/* Truncation caveat — when only a subset of the fleet was aggregated */}
          {projectsTruncated && !error && (
            <div className="border-b border-border bg-amber-500/10 px-5 py-1.5 text-[11px] text-amber-700 dark:text-amber-300">
              Showing only the top {sorted.length} most-recently-updated projects. Other projects exist
              but aren&rsquo;t aggregated here.
            </div>
          )}

          {/* Body */}
          <div className="flex-1 overflow-y-auto">
            {emptyMode === "loading" ? (
              <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden />
                <p className="text-sm font-medium text-foreground">Loading projects…</p>
              </div>
            ) : emptyMode === "error" ? (
              <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
                <AlertTriangle className="h-6 w-6 text-destructive" aria-hidden />
                <p className="text-sm font-medium text-foreground">Couldn&rsquo;t load project data</p>
                <p className="max-w-sm text-xs text-muted-foreground">
                  The dashboard couldn&rsquo;t reach the API. Once it&rsquo;s back, this breakdown will
                  populate automatically.
                </p>
                {onRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted/50"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Retry now
                  </button>
                )}
              </div>
            ) : emptyMode === "no-projects" ? (
              <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
                <p className="text-sm font-medium text-foreground">No projects yet</p>
                <p className="max-w-sm text-xs text-muted-foreground">{meta.emptyHint}</p>
                <Link
                  href="/projects"
                  className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                  onClick={onClose}
                >
                  Create your first project
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            ) : emptyMode === "fetches-failed" ? (
              <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
                <AlertTriangle className="h-5 w-5 text-amber-500" aria-hidden />
                <p className="text-sm font-medium text-foreground">
                  Couldn&rsquo;t load {meta.columnHeader.toLowerCase()} data
                </p>
                <p className="max-w-sm text-xs text-muted-foreground">
                  {sorted.length} {sorted.length === 1 ? "project exists" : "projects exist"}, but the
                  {metric === "compliance" || metric === "risk" ? " privacy-hub" : " jobs"} endpoint
                  returned no data for any of them. This is usually transient —
                  retry, or check the API connectivity.
                </p>
                {onRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted/50"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Retry
                  </button>
                )}
              </div>
            ) : (
              <table className="w-full text-xs" aria-label={meta.title}>
                <thead className="sticky top-0 bg-card">
                  <tr className="border-b border-border text-left">
                    <th
                      scope="col"
                      className="px-5 py-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      Project
                    </th>
                    <th
                      scope="col"
                      aria-sort="descending"
                      className="px-3 py-2 text-right text-[10px] font-medium uppercase tracking-wide text-primary"
                    >
                      {meta.columnHeader}
                    </th>
                    {meta.supporting.map((s) => (
                      <th
                        key={s}
                        scope="col"
                        className="px-3 py-2 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
                      >
                        {SUPPORTING_LABEL[s]}
                      </th>
                    ))}
                    <th
                      scope="col"
                      className="px-5 py-2 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
                    >
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((r) => (
                    <tr
                      key={r.id}
                      className="border-b border-border/60 transition-colors hover:bg-muted/30"
                    >
                      <td className="px-5 py-2">
                        <Link
                          href={`/projects/${r.id}`}
                          onClick={onClose}
                          className="font-medium text-foreground hover:text-primary"
                        >
                          {r.name}
                        </Link>
                      </td>
                      <td className="bg-primary/[0.04] px-3 py-2 text-right">
                        <FocusedCell metric={metric} row={r} />
                      </td>
                      {meta.supporting.map((s) => (
                        <td key={s} className="px-3 py-2 text-right">
                          <SupportingCell kind={s} row={r} />
                        </td>
                      ))}
                      <td className="px-5 py-2 text-right">
                        <div className="inline-flex items-center gap-1">
                          <Link
                            href={`/projects/${r.id}/privacy-hub`}
                            onClick={onClose}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            title="Privacy Hub"
                            aria-label={`Open Privacy Hub for ${r.name}`}
                          >
                            <ShieldCheck className="h-3.5 w-3.5" />
                          </Link>
                          <Link
                            href={`/projects/${r.id}/masking`}
                            onClick={onClose}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            title="Masking policies"
                            aria-label={`Open masking for ${r.name}`}
                          >
                            <Lock className="h-3.5 w-3.5" />
                          </Link>
                          <Link
                            href={`/projects/${r.id}/jobs`}
                            onClick={onClose}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            title="Jobs"
                            aria-label={`Open jobs for ${r.name}`}
                          >
                            <Zap className="h-3.5 w-3.5" />
                          </Link>
                          <Link
                            href={`/projects/${r.id}/discovery`}
                            onClick={onClose}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            title="Run discovery"
                            aria-label={`Run discovery for ${r.name}`}
                          >
                            <Play className="h-3.5 w-3.5" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Footer */}
          <footer className="flex items-center justify-between border-t border-border bg-muted/10 px-5 py-3 text-xs">
            <span className="text-muted-foreground">
              {emptyMode === "loading"
                ? "Loading…"
                : emptyMode === "error"
                  ? "Unable to fetch"
                  : emptyMode === "no-projects"
                    ? "No projects to show"
                    : emptyMode === "fetches-failed"
                      ? `${sorted.length} ${sorted.length === 1 ? "project" : "projects"} · ${meta.columnHeader.toLowerCase()} data unreachable`
                      : `${sorted.length} ${sorted.length === 1 ? "project" : "projects"} shown · sorted by ${meta.columnHeader.toLowerCase()}`}
            </span>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border bg-background px-3 py-1 text-xs font-medium text-foreground hover:bg-muted/50"
            >
              Close
            </button>
          </footer>
        </div>
      </AccessibleDialog>
    </>
  );
}

function CoverageBadge({ pct, compact }: { pct: number; compact?: boolean }) {
  const tone =
    pct >= 95
      ? "text-emerald-600 dark:text-emerald-400"
      : pct >= 75
        ? "text-amber-600 dark:text-amber-400"
        : "text-red-600 dark:text-red-400";
  return (
    <span className={cn("inline-flex items-center gap-1.5", tone)}>
      <span
        className={cn(
          "relative inline-block overflow-hidden rounded-full bg-muted",
          compact ? "h-1.5 w-8" : "h-2 w-12",
        )}
      >
        <span
          className="absolute inset-y-0 left-0 rounded-full bg-current"
          style={{ width: `${pct}%`, opacity: 0.8 }}
        />
      </span>
      <span className="tabular-nums">{pct}%</span>
    </span>
  );
}
