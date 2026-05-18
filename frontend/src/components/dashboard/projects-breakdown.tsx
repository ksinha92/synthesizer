"use client";

import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, Lock, Play, ShieldCheck, Zap } from "lucide-react";
import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { ProjectBreakdownRow } from "@/hooks/use-dashboard-data";

export type BreakdownSortKey =
  | "name"
  | "sensitive"
  | "unmasked"
  | "coverage"
  | "jobs7d"
  | "active"
  | "lastActivity";

interface ProjectsBreakdownProps {
  rows: ProjectBreakdownRow[];
  sortKey: BreakdownSortKey;
  sortDir: "asc" | "desc";
  onSortChange: (key: BreakdownSortKey) => void;
  /** Used by the page to scroll the section into view from KPI clicks. */
  anchorId?: string;
}

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

function compareRows(a: ProjectBreakdownRow, b: ProjectBreakdownRow, key: BreakdownSortKey): number {
  // Push nulls to the bottom regardless of direction. They're "no data", not zeros.
  const aVal = readMetric(a, key);
  const bVal = readMetric(b, key);
  if (aVal === null && bVal === null) return 0;
  if (aVal === null) return 1;
  if (bVal === null) return -1;
  if (typeof aVal === "string" && typeof bVal === "string") {
    return aVal.localeCompare(bVal);
  }
  return (aVal as number) - (bVal as number);
}

function readMetric(r: ProjectBreakdownRow, key: BreakdownSortKey): number | string | null {
  switch (key) {
    case "name":
      return r.name;
    case "sensitive":
      return r.sensitive;
    case "unmasked":
      return r.unmasked;
    case "coverage":
      return r.coveragePct;
    case "jobs7d":
      return r.jobs7d;
    case "active":
      return r.activeJobs;
    case "lastActivity":
      return r.lastJobAt ? new Date(r.lastJobAt).getTime() : null;
  }
}

interface ColumnDef {
  key: BreakdownSortKey;
  label: string;
  align: "left" | "right";
  className?: string;
}

const COLUMNS: ColumnDef[] = [
  { key: "name", label: "Project", align: "left", className: "min-w-[140px]" },
  { key: "sensitive", label: "Sensitive", align: "right" },
  { key: "unmasked", label: "Unmasked", align: "right" },
  { key: "coverage", label: "Coverage", align: "right" },
  { key: "jobs7d", label: "Jobs 7d", align: "right" },
  { key: "active", label: "Active", align: "right" },
  { key: "lastActivity", label: "Last activity", align: "right" },
];

function SortIcon({ active, dir }: { active: boolean; dir: "asc" | "desc" }) {
  if (!active) return <ArrowUpDown className="h-3 w-3 opacity-40" aria-hidden />;
  return dir === "asc" ? (
    <ArrowUp className="h-3 w-3" aria-hidden />
  ) : (
    <ArrowDown className="h-3 w-3" aria-hidden />
  );
}

export function ProjectsBreakdown({
  rows,
  sortKey,
  sortDir,
  onSortChange,
  anchorId,
}: ProjectsBreakdownProps) {
  const sorted = useMemo(() => {
    const out = [...rows].sort((a, b) => compareRows(a, b, sortKey));
    return sortDir === "desc" ? out.reverse() : out;
  }, [rows, sortKey, sortDir]);

  if (rows.length === 0) {
    return (
      <div id={anchorId} className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        No projects to break down yet. Create a project to begin.
      </div>
    );
  }

  return (
    <div id={anchorId} className="overflow-x-auto">
      <table className="w-full text-xs" role="table" aria-label="Per-project metrics breakdown">
        <thead>
          <tr className="border-b border-border text-left">
            {COLUMNS.map((col) => {
              const isActive = sortKey === col.key;
              return (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    "py-2 font-medium uppercase tracking-wide text-[10px] text-muted-foreground",
                    col.align === "right" ? "text-right" : "text-left",
                    col.className,
                  )}
                  aria-sort={
                    isActive ? (sortDir === "asc" ? "ascending" : "descending") : "none"
                  }
                >
                  <button
                    type="button"
                    onClick={() => onSortChange(col.key)}
                    className={cn(
                      "inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                      col.align === "right" && "ml-auto flex-row-reverse",
                      isActive && "text-foreground",
                    )}
                  >
                    <span>{col.label}</span>
                    <SortIcon active={isActive} dir={sortDir} />
                  </button>
                </th>
              );
            })}
            <th scope="col" className="py-2 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const projectHref = `/projects/${r.id}`;
            return (
              <tr key={r.id} className="border-b border-border/60 transition-colors hover:bg-muted/30">
                <td className="py-2 pr-2">
                  <Link
                    href={projectHref}
                    className="font-medium text-foreground hover:text-primary"
                  >
                    {r.name}
                  </Link>
                </td>
                <td className="py-2 pr-2 text-right tabular-nums">
                  {r.sensitive ?? <span className="text-muted-foreground">—</span>}
                </td>
                <td className="py-2 pr-2 text-right tabular-nums">
                  {r.unmasked === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : r.unmasked > 0 ? (
                    <span className="text-red-600 dark:text-red-400">{r.unmasked}</span>
                  ) : (
                    <span className="text-emerald-600 dark:text-emerald-400">0</span>
                  )}
                </td>
                <td className="py-2 pr-2 text-right tabular-nums">
                  {r.coveragePct === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <CoverageBadge pct={r.coveragePct} />
                  )}
                </td>
                <td className="py-2 pr-2 text-right tabular-nums">
                  {r.jobs7d ?? <span className="text-muted-foreground">—</span>}
                </td>
                <td className="py-2 pr-2 text-right tabular-nums">
                  {r.activeJobs === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : r.activeJobs > 0 ? (
                    <span className="inline-flex items-center gap-1 text-[hsl(var(--chart-7))]">
                      <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[hsl(var(--chart-7))]" />
                      {r.activeJobs}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">0</span>
                  )}
                </td>
                <td className="py-2 pr-2 text-right text-muted-foreground">
                  {formatRelative(r.lastJobAt)}
                </td>
                <td className="py-2 text-right">
                  <div className="inline-flex items-center gap-1">
                    <Link
                      href={`${projectHref}/privacy-hub`}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Privacy Hub"
                      aria-label={`Open Privacy Hub for ${r.name}`}
                    >
                      <ShieldCheck className="h-3.5 w-3.5" />
                    </Link>
                    <Link
                      href={`${projectHref}/masking`}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Masking policies"
                      aria-label={`Open masking for ${r.name}`}
                    >
                      <Lock className="h-3.5 w-3.5" />
                    </Link>
                    <Link
                      href={`${projectHref}/jobs`}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Jobs"
                      aria-label={`Open jobs for ${r.name}`}
                    >
                      <Zap className="h-3.5 w-3.5" />
                    </Link>
                    <Link
                      href={`${projectHref}/discovery`}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Run discovery"
                      aria-label={`Run discovery for ${r.name}`}
                    >
                      <Play className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CoverageBadge({ pct }: { pct: number }) {
  const tone =
    pct >= 95
      ? "text-emerald-600 dark:text-emerald-400"
      : pct >= 75
        ? "text-amber-600 dark:text-amber-400"
        : "text-red-600 dark:text-red-400";
  return (
    <span className={cn("inline-flex items-center gap-1.5", tone)}>
      <span className="relative inline-block h-1.5 w-10 overflow-hidden rounded-full bg-muted">
        <span
          className="absolute inset-y-0 left-0 rounded-full bg-current"
          style={{ width: `${pct}%`, opacity: 0.8 }}
        />
      </span>
      <span className="tabular-nums">{pct}%</span>
    </span>
  );
}
