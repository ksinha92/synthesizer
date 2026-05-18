"use client";

import { Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

interface PrivacyMetricsProps {
  dcrMean: number;
  dcrMin: number;
  identicalMatches: number;
  identicalMatchPct: number;
}

export function PrivacyMetrics({ dcrMean, dcrMin, identicalMatches, identicalMatchPct }: PrivacyMetricsProps) {
  const isPrivate = identicalMatches === 0;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-4">
        {isPrivate ? <ShieldCheck className="h-5 w-5 text-green-600" /> : <ShieldAlert className="h-5 w-5 text-red-600" />}
        <h3 className="text-sm font-medium text-foreground">Privacy Metrics</h3>
        <span className={cn("ml-auto rounded-full px-2 py-0.5 text-xs font-medium", isPrivate ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600")}>
          {isPrivate ? "PASS" : "FAIL"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          label="DCR Mean"
          value={dcrMean.toFixed(4)}
          description="Average distance to closest real record"
          status={dcrMean > 0.1 ? "good" : "warn"}
        />
        <MetricCard
          label="DCR Min"
          value={dcrMin.toFixed(4)}
          description="Minimum distance — lower = closer to real data"
          status={dcrMin > 0.05 ? "good" : "warn"}
        />
        <MetricCard
          label="Identical Matches"
          value={String(identicalMatches)}
          description="Synthetic rows matching a real row exactly"
          status={identicalMatches === 0 ? "good" : "bad"}
        />
        <MetricCard
          label="Match Rate"
          value={`${(identicalMatchPct * 100).toFixed(2)}%`}
          description="Percentage of synthetic rows that are identical"
          status={identicalMatchPct === 0 ? "good" : "bad"}
        />
      </div>
    </div>
  );
}

function MetricCard({ label, value, description, status }: { label: string; value: string; description: string; status: "good" | "warn" | "bad" }) {
  const color = status === "good" ? "text-green-600 dark:text-green-400" : status === "warn" ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400";
  const bg = status === "good" ? "bg-green-500/5" : status === "warn" ? "bg-yellow-500/5" : "bg-red-500/5";

  return (
    <div className={cn("rounded-lg p-3", bg)}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("text-lg font-semibold mt-0.5", color)}>{value}</p>
      <p className="text-[10px] text-muted-foreground mt-1">{description}</p>
    </div>
  );
}
