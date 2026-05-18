"use client";

import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";

export interface CoverageRow {
  projectId: string;
  tableLabel: string;
  total: number;
  sensitive: number;
  protected: number;
}

interface CoverageBreakdownProps {
  rows: CoverageRow[];
}

export function CoverageBreakdown({ rows }: CoverageBreakdownProps) {
  if (rows.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-center text-sm text-muted-foreground">
        Run discovery on a connection to see coverage by table.
      </div>
    );
  }

  const top = [...rows]
    .sort((a, b) => b.sensitive - a.sensitive)
    .slice(0, 10);

  const max = Math.max(1, ...top.map((r) => r.total));

  return (
    <div className="space-y-3" role="list" aria-label="Coverage by top sensitive tables">
      {top.map((r) => {
        const unprotected = Math.max(0, r.sensitive - r.protected);
        const safe = Math.max(0, r.total - r.sensitive);
        const widthPct = (n: number) => `${(n / max) * 100}%`;
        const coveragePct = r.sensitive > 0 ? Math.round((r.protected / r.sensitive) * 100) : 100;
        return (
          <div key={`${r.projectId}-${r.tableLabel}`} role="listitem" className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <Link
                href={`/projects/${r.projectId}/privacy-hub`}
                className="truncate font-medium text-foreground hover:text-primary"
                title={r.tableLabel}
              >
                {r.tableLabel}
              </Link>
              <span className="ml-2 inline-flex items-center gap-1 whitespace-nowrap text-muted-foreground">
                <ShieldCheck className="h-3 w-3" aria-hidden />
                {coveragePct}% covered
              </span>
            </div>
            <div
              className="flex h-3 overflow-hidden rounded-md bg-muted"
              role="img"
              aria-label={`${r.tableLabel}: ${r.protected} protected, ${unprotected} unmasked sensitive, ${safe} non-sensitive of ${r.total} columns`}
            >
              <div
                className="bg-emerald-500/80 transition-all"
                style={{ width: widthPct(r.protected) }}
                title={`${r.protected} protected`}
              />
              <div
                className="bg-amber-500/80 transition-all"
                style={{ width: widthPct(unprotected) }}
                title={`${unprotected} unmasked sensitive`}
              />
              <div
                className="bg-foreground/10 transition-all"
                style={{ width: widthPct(safe) }}
                title={`${safe} non-sensitive`}
              />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground tabular-nums">
              <span>{r.protected} protected · {unprotected} unmasked</span>
              <span>{r.total} cols</span>
            </div>
          </div>
        );
      })}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-emerald-500/80" />
            Protected
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-amber-500/80" />
            Unmasked sensitive
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-foreground/10" />
            Non-sensitive
          </span>
        </div>
        {rows.length > 10 && (
          <Link
            href="/projects"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            View all {rows.length} tables
            <ArrowRight className="h-3 w-3" />
          </Link>
        )}
      </div>
    </div>
  );
}
