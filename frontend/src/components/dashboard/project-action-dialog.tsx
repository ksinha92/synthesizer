"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  AlertTriangle,
  ArrowRight,
  FileText,
  Plus,
  RefreshCw,
  Sparkles,
  X,
  type LucideIcon,
} from "lucide-react";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import type { ProjectBreakdownRow } from "@/hooks/use-dashboard-data";

export type ProjectAction = "discovery" | "reports";

export interface PickerProject {
  id: string;
  name: string;
  updated_at: string;
}

interface ProjectActionDialogProps {
  open: boolean;
  onClose: () => void;
  action: ProjectAction;
  /** Full list of every fetched project (id+name+updated_at). Source of truth
   *  for the picker so it never drops projects beyond the aggregated subset. */
  projects: PickerProject[];
  /** Breakdown rows for the subset that was deeply aggregated. Used to enrich
   *  the picker rows that overlap (e.g. last-activity, sensitive-col count). */
  breakdown: ProjectBreakdownRow[];
  /** Total number of projects across the whole fleet (may exceed projects.length
   *  if the projects endpoint paginates beyond what the dashboard pulls). */
  totalProjects: number;
  error?: string | null;
  loading?: boolean;
  onRetry?: () => void;
}

interface PickerRow {
  id: string;
  name: string;
  updated_at: string;
  enriched: boolean;
  lastJobAt: string | null;
  sensitive: number | null;
  coveragePct: number | null;
}

interface ActionMeta {
  title: string;
  description: string;
  icon: LucideIcon;
  ctaLabel: string;
  ctaIcon: LucideIcon;
  /** Builder for the per-row primary action href. */
  hrefBuilder: (projectId: string) => string;
  /** Sort order for the project list (descending). */
  scoreFor: (r: PickerRow) => number;
}

const ACTIONS: Record<ProjectAction, ActionMeta> = {
  discovery: {
    title: "Run discovery — choose a project",
    description:
      "Discovery scans a project's connections for tables and classifies sensitive columns. Pick a project below to launch a run.",
    icon: Sparkles,
    ctaLabel: "Run discovery",
    ctaIcon: Sparkles,
    hrefBuilder: (id) => `/projects/${id}/discovery`,
    // Surface projects that haven't been scanned recently first. Non-enriched
    // projects (no breakdown data) fall back to updated_at.
    scoreFor: (r) => {
      const t = r.lastJobAt
        ? new Date(r.lastJobAt).getTime()
        : new Date(r.updated_at).getTime();
      return -t; // older first → sorted descending = older on top
    },
  },
  reports: {
    title: "Generate report — choose a project",
    description:
      "Compliance reports summarize PII coverage, masking policies, and audit history for a project. Pick one to view or export.",
    icon: FileText,
    ctaLabel: "Open compliance",
    ctaIcon: FileText,
    hrefBuilder: (id) => `/projects/${id}/compliance`,
    // Surface projects with the most sensitive data first — those are the most
    // valuable to report on. Unaggregated projects sink to the bottom but stay
    // visible (selecting them is still valid).
    scoreFor: (r) => r.sensitive ?? -1,
  },
};

function formatRelative(iso: string | null): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "never";
  const diff = Date.now() - then;
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function ProjectActionDialog({
  open,
  onClose,
  action,
  projects,
  breakdown,
  totalProjects,
  error,
  loading,
  onRetry,
}: ProjectActionDialogProps) {
  const meta = ACTIONS[action];
  const titleId = `project-action-${action}-title`;

  const sorted = useMemo(() => {
    const byId = new Map<string, ProjectBreakdownRow>();
    for (const r of breakdown) byId.set(r.id, r);
    const enriched: PickerRow[] = projects.map((p) => {
      const b = byId.get(p.id);
      return {
        id: p.id,
        name: p.name,
        updated_at: p.updated_at,
        enriched: !!b,
        lastJobAt: b?.lastJobAt ?? null,
        sensitive: b?.sensitive ?? null,
        coveragePct: b?.coveragePct ?? null,
      };
    });
    return enriched.sort((a, b) => meta.scoreFor(b) - meta.scoreFor(a));
  }, [projects, breakdown, meta]);

  // Did the projects API paginate beyond what the dashboard pulled?
  const hasUnshownProjects = totalProjects > projects.length;

  if (!open) return null;

  return (
    <>
      <div aria-hidden="true" className="fixed inset-0 z-[55] bg-black/50" onClick={onClose} />
      <AccessibleDialog
        open={open}
        onClose={onClose}
        titleId={titleId}
        className="fixed inset-x-0 top-[10%] z-[60] mx-auto flex w-[92%] max-w-2xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
      >
        <div style={{ maxHeight: "80vh" }} className="flex flex-col">
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
                <p className="mt-0.5 max-w-md text-xs text-muted-foreground">{meta.description}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close project picker"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          {/* Error banner */}
          {error && (
            <div
              role="alert"
              className="flex items-center gap-2 border-b border-destructive/30 bg-destructive/5 px-5 py-2 text-xs text-destructive"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="flex-1">
                {sorted.length > 0
                  ? `Project list may be stale — couldn't reach the API: ${error}`
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

          {/* Body */}
          <div className="flex-1 overflow-y-auto">
            {loading && sorted.length === 0 ? (
              <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden />
                <p className="text-sm font-medium text-foreground">Loading projects…</p>
              </div>
            ) : sorted.length === 0 ? (
              <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
                {error ? (
                  <>
                    <AlertTriangle className="h-6 w-6 text-destructive" aria-hidden />
                    <p className="text-sm font-medium text-foreground">Couldn&rsquo;t load projects</p>
                    <p className="max-w-sm text-xs text-muted-foreground">
                      The API didn&rsquo;t respond. Once it&rsquo;s back, the list will populate.
                    </p>
                    {onRetry && (
                      <button
                        type="button"
                        onClick={onRetry}
                        className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-muted/50"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Retry
                      </button>
                    )}
                  </>
                ) : (
                  <>
                    <p className="text-sm font-medium text-foreground">No projects yet</p>
                    <p className="max-w-sm text-xs text-muted-foreground">
                      Create a project first, then connect a data source — discovery and reports
                      operate on a project&rsquo;s connections.
                    </p>
                    <Link
                      href="/projects"
                      onClick={onClose}
                      className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      <Plus className="h-3 w-3" />
                      Create a project
                    </Link>
                  </>
                )}
              </div>
            ) : (
              <ul className="divide-y divide-border" aria-label={meta.title}>
                {sorted.map((r) => {
                  // Project may be unenriched (outside the deeply-aggregated subset).
                  // Show whatever metadata we have without inventing zeros.
                  const lastLabel =
                    action === "discovery"
                      ? r.lastJobAt
                        ? `Last activity: ${formatRelative(r.lastJobAt)}`
                        : r.enriched
                          ? "No jobs run yet"
                          : `Updated ${formatRelative(r.updated_at)}`
                      : r.enriched
                        ? r.sensitive !== null
                          ? `${r.sensitive} sensitive ${r.sensitive === 1 ? "column" : "columns"}${r.coveragePct !== null ? ` · ${r.coveragePct}% covered` : ""}`
                          : "Privacy data unreachable"
                        : `Updated ${formatRelative(r.updated_at)} · metrics not aggregated`;
                  return (
                    <li key={r.id} className="flex items-center gap-3 px-5 py-3 hover:bg-muted/30">
                      <div className="min-w-0 flex-1">
                        <Link
                          href={`/projects/${r.id}`}
                          onClick={onClose}
                          className="block truncate text-sm font-medium text-foreground hover:text-primary"
                        >
                          {r.name}
                        </Link>
                        <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                          {lastLabel}
                        </p>
                      </div>
                      <Link
                        href={meta.hrefBuilder(r.id)}
                        onClick={onClose}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                      >
                        <meta.ctaIcon className="h-3.5 w-3.5" aria-hidden />
                        {meta.ctaLabel}
                        <ArrowRight className="h-3 w-3 opacity-80" aria-hidden />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Footer */}
          <footer className="flex items-center justify-between border-t border-border bg-muted/10 px-5 py-3 text-xs">
            <span className="text-muted-foreground">
              {sorted.length === 0
                ? error
                  ? "Unable to fetch"
                  : "No projects to show"
                : hasUnshownProjects
                  ? `${sorted.length} of ${totalProjects} projects · narrow your search to load more`
                  : `${sorted.length} ${sorted.length === 1 ? "project" : "projects"} available`}
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
