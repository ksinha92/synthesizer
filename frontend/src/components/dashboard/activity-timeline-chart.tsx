"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { JobRow } from "./pipeline-health";

interface ActivityTimelineChartProps {
  jobs: JobRow[];
  windowDays?: number;
}

interface DayBucket {
  date: string;
  label: string;
  completed: number;
  failed: number;
  running: number;
  cancelled: number;
  total: number;
}

const SERIES: Array<{
  key: keyof Pick<DayBucket, "completed" | "running" | "failed" | "cancelled">;
  label: string;
  cssVar: string;
}> = [
  { key: "completed", label: "Completed", cssVar: "--chart-4" }, // emerald
  { key: "running", label: "Running", cssVar: "--chart-7" }, // cyan
  { key: "failed", label: "Failed", cssVar: "--chart-6" }, // red
  { key: "cancelled", label: "Cancelled", cssVar: "--chart-axis" }, // muted
];

function dayKey(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function shortLabel(d: Date): string {
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ActivityTimelineChart({ jobs, windowDays = 14 }: ActivityTimelineChartProps) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const data: DayBucket[] = useMemo(() => {
    const buckets = new Map<string, DayBucket>();
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    for (let i = windowDays - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      const key = dayKey(d);
      buckets.set(key, {
        date: key,
        label: shortLabel(d),
        completed: 0,
        failed: 0,
        running: 0,
        cancelled: 0,
        total: 0,
      });
    }
    for (const job of jobs) {
      const t = new Date(job.created_at);
      if (Number.isNaN(t.getTime())) continue;
      t.setHours(0, 0, 0, 0);
      const k = dayKey(t);
      const bucket = buckets.get(k);
      if (!bucket) continue;
      // ``completed_with_warnings`` is a terminal-completed state — the
      // artifact exists. Bucket it with ``completed`` so the timeline
      // still shows the run; the warning surfaces on per-job detail.
      if (
        job.status === "completed" ||
        job.status === "completed_with_warnings" ||
        job.status === "succeeded"
      )
        bucket.completed++;
      else if (job.status === "failed") bucket.failed++;
      else if (job.status === "running" || job.status === "pending") bucket.running++;
      else if (job.status === "cancelled") bucket.cancelled++;
      bucket.total++;
    }
    return Array.from(buckets.values());
  }, [jobs, windowDays]);

  const totalInWindow = data.reduce((s, d) => s + d.total, 0);

  const toggle = (key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (totalInWindow === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
        <p className="text-sm font-medium text-foreground">No activity in the last {windowDays} days</p>
        <p className="max-w-xs text-xs text-muted-foreground">
          Once jobs start running, you&rsquo;ll see a live, multi-series breakdown of completed,
          running, failed, and cancelled jobs per day.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        className="h-64"
        role="img"
        aria-label={`Daily job activity over the last ${windowDays} days, ${totalInWindow} total jobs`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
            <defs>
              {SERIES.map((s) => (
                <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={`hsl(var(${s.cssVar}))`} stopOpacity={0.6} />
                  <stop offset="100%" stopColor={`hsl(var(${s.cssVar}))`} stopOpacity={0.05} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid stroke="hsl(var(--chart-grid))" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "hsl(var(--chart-axis))", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--chart-grid))" }}
              interval="preserveStartEnd"
              minTickGap={28}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "hsl(var(--chart-axis))", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--chart-grid))" }}
              width={36}
            />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 12,
                boxShadow: "0 4px 12px hsl(var(--foreground) / 0.08)",
                color: "hsl(var(--foreground))",
              }}
              labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600, marginBottom: 4 }}
              itemStyle={{ padding: 0 }}
              cursor={{ stroke: "hsl(var(--chart-axis))", strokeDasharray: "3 3" }}
            />
            <ReferenceLine
              x={data[data.length - 1]?.label}
              stroke="hsl(var(--chart-3))"
              strokeDasharray="2 2"
              label={{
                value: "now",
                position: "insideTopRight",
                fill: "hsl(var(--chart-3))",
                fontSize: 10,
              }}
            />
            {SERIES.map((s) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stackId="1"
                stroke={`hsl(var(${s.cssVar}))`}
                strokeWidth={1.5}
                fill={`url(#grad-${s.key})`}
                hide={hidden.has(s.key)}
                isAnimationActive
                animationDuration={500}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Interactive custom legend — click to toggle series visibility */}
      <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 pl-1 text-xs" aria-label="Series legend">
        {SERIES.map((s) => {
          const isHidden = hidden.has(s.key);
          return (
            <li key={s.key}>
              <button
                type="button"
                onClick={() => toggle(s.key)}
                aria-pressed={!isHidden}
                className="inline-flex items-center gap-1.5 rounded px-1 py-0.5 hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{
                    background: `hsl(var(${s.cssVar}))`,
                    opacity: isHidden ? 0.3 : 1,
                  }}
                  aria-hidden
                />
                <span
                  className={isHidden ? "text-muted-foreground line-through" : "text-foreground"}
                >
                  {s.label}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
