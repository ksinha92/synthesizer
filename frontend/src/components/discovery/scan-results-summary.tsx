"use client";

import { useMemo } from "react";
import { AlertTriangle, CheckCircle2, Search, ShieldQuestion } from "lucide-react";

import { cn } from "@/lib/utils";

interface PIIColumnRow {
  pii_type: string;
  confidence: number;
  detector: string;
  classification: string;
}

interface ScanResultsSummaryProps {
  columns: PIIColumnRow[];
}

/**
 * Tonic-style "Automatic sensitivity scan" summary panel (screenshot
 * 11.26.14). Surfaces the per-column scan output's totals — detector
 * breakdown, classification buckets, and confidence band counts — above
 * the PII Results table so users can scan the dataset at a glance before
 * diving into row-level overrides.
 */
export function ScanResultsSummary({ columns }: ScanResultsSummaryProps) {
  const stats = useMemo(() => {
    const total = columns.length;
    const byDetector = new Map<string, number>();
    const byClassification = { auto: 0, review: 0, manual: 0, dismissed: 0 };
    const byBand = { high: 0, medium: 0, low: 0 }; // ≥0.65 / 0.4-0.64 / <0.4

    for (const c of columns) {
      byDetector.set(c.detector, (byDetector.get(c.detector) ?? 0) + 1);
      if (c.classification === "auto_classified") byClassification.auto += 1;
      else if (c.classification === "needs_review") byClassification.review += 1;
      else if (c.classification === "manually_classified") byClassification.manual += 1;
      else if (c.classification === "dismissed") byClassification.dismissed += 1;

      if (c.confidence >= 0.65) byBand.high += 1;
      else if (c.confidence >= 0.4) byBand.medium += 1;
      else byBand.low += 1;
    }

    const detectorRows = Array.from(byDetector.entries()).sort((a, b) => b[1] - a[1]);
    return { total, byClassification, byBand, detectorRows };
  }, [columns]);

  if (stats.total === 0) return null;

  return (
    <section
      aria-labelledby="scan-summary-title"
      className="rounded-lg border border-border bg-card px-5 py-4"
    >
      <header className="flex items-center justify-between mb-3">
        <div>
          <h3 id="scan-summary-title" className="text-sm font-semibold text-foreground">
            Sensitivity scan results
          </h3>
          <p className="text-xs text-muted-foreground">
            The 4-layer PII pipeline checked each column's name, data type, and sample
            values — buckets below summarise what it found.
          </p>
        </div>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground tabular-nums">
          {stats.total} column{stats.total === 1 ? "" : "s"} scanned
        </span>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile
          icon={CheckCircle2}
          label="Auto-classified"
          accent="success"
          value={stats.byClassification.auto}
          help="Confidence ≥ 0.65 — applied without review."
        />
        <StatTile
          icon={ShieldQuestion}
          label="Needs review"
          accent="warning"
          value={stats.byClassification.review}
          help="Confidence 0.4 – 0.65 — flagged for manual confirmation."
        />
        <StatTile
          icon={AlertTriangle}
          label="Manual / dismissed"
          accent="muted"
          value={stats.byClassification.manual + stats.byClassification.dismissed}
          help="Human-set classifications and explicit dismissals."
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <DetectorBreakdown rows={stats.detectorRows} total={stats.total} />
        <ConfidenceBand high={stats.byBand.high} medium={stats.byBand.medium} low={stats.byBand.low} />
      </div>
    </section>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
  help,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  help: string;
  accent: "success" | "warning" | "muted";
}) {
  const accentClass = {
    success: "text-[hsl(var(--dw-pill-success))]",
    warning: "text-[hsl(var(--dw-pill-warning))]",
    muted: "text-muted-foreground",
  }[accent];
  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-3.5 w-3.5", accentClass)} />
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      </div>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", accentClass)}>{value}</p>
      <p className="mt-0.5 text-[10px] text-muted-foreground">{help}</p>
    </div>
  );
}

function DetectorBreakdown({ rows, total }: { rows: [string, number][]; total: number }) {
  return (
    <div className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <Search className="h-3.5 w-3.5 text-[hsl(var(--dw-brand))]" />
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Caught by detector
        </p>
      </div>
      <ul className="mt-2 space-y-1.5">
        {rows.length === 0 ? (
          <li className="text-[11px] text-muted-foreground">No detections recorded.</li>
        ) : (
          rows.map(([detector, count]) => {
            const pct = total === 0 ? 0 : Math.round((count / total) * 100);
            return (
              <li key={detector} className="space-y-0.5">
                <div className="flex items-baseline justify-between text-[11px]">
                  <span className="font-medium text-foreground">{detector}</span>
                  <span className="font-mono tabular-nums text-muted-foreground">
                    {count} · {pct}%
                  </span>
                </div>
                <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full bg-[hsl(var(--dw-brand))]"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}

function ConfidenceBand({ high, medium, low }: { high: number; medium: number; low: number }) {
  return (
    <div className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Confidence distribution
      </p>
      <ul className="mt-2 space-y-1.5">
        <BandRow label="High (≥ 65%)" count={high} colorClass="bg-[hsl(var(--dw-pill-success))]" />
        <BandRow label="Medium (40–64%)" count={medium} colorClass="bg-[hsl(var(--dw-pill-warning))]" />
        <BandRow label="Low (< 40%)" count={low} colorClass="bg-muted-foreground/50" />
      </ul>
    </div>
  );
}

function BandRow({
  label,
  count,
  colorClass,
}: {
  label: string;
  count: number;
  colorClass: string;
}) {
  return (
    <li className="flex items-center gap-2 text-[11px]">
      <span aria-hidden="true" className={cn("h-2 w-2 rounded-full", colorClass)} />
      <span className="flex-1 text-foreground">{label}</span>
      <span className="font-mono tabular-nums text-muted-foreground">{count}</span>
    </li>
  );
}
