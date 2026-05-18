"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

interface HeatmapTable {
  id: string;
  table_name: string;
  total_columns: number;
  pii_columns: number;
  unmasked_count: number;
}

interface PIIHeatmapProps {
  tables: HeatmapTable[];
  projectId?: string;
}

function getDensityColor(ratio: number): string {
  if (ratio === 0) return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
  if (ratio < 0.2) return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
  if (ratio < 0.4) return "bg-amber-500/30 text-amber-800 dark:text-amber-300";
  if (ratio < 0.6) return "bg-orange-500/40 text-orange-800 dark:text-orange-300";
  if (ratio < 0.8) return "bg-red-500/40 text-red-800 dark:text-red-300";
  return "bg-red-500/60 text-red-900 dark:text-red-200";
}

export function PIIHeatmap({ tables, projectId }: PIIHeatmapProps) {
  const router = useRouter();

  const sorted = useMemo(
    () => [...tables].sort((a, b) => (b.pii_columns / (b.total_columns || 1)) - (a.pii_columns / (a.total_columns || 1))),
    [tables]
  );

  if (tables.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
        No discovery data available. Run discovery to see PII density.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Color intensity = PII column density</p>
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-500/10 border border-border" />
          <span>None</span>
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-amber-500/30 border border-border" />
          <span>Low</span>
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-orange-500/40 border border-border" />
          <span>Med</span>
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-500/60 border border-border" />
          <span>High</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6">
        {sorted.map((t) => {
          const ratio = t.total_columns > 0 ? t.pii_columns / t.total_columns : 0;
          const pct = Math.round(ratio * 100);
          return (
            <button
              key={t.id}
              onClick={() => projectId && router.push(`/projects/${projectId}/discovery`)}
              className={cn(
                "relative rounded-md px-2 py-2.5 text-left transition-all hover:ring-2 hover:ring-primary/40",
                getDensityColor(ratio)
              )}
              title={`${t.table_name}: ${t.pii_columns}/${t.total_columns} PII columns (${pct}%)`}
            >
              <p className="truncate text-[11px] font-medium leading-tight">{t.table_name}</p>
              <p className="mt-0.5 text-[10px] opacity-80">{pct}% PII</p>
              {t.unmasked_count > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[9px] font-bold text-destructive-foreground">
                  {t.unmasked_count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
