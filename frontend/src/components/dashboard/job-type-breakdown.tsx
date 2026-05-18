"use client";

import { useMemo, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { JobRow } from "./pipeline-health";

interface JobTypeBreakdownProps {
  jobs: JobRow[];
}

const COLOR_VARS = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5", "--chart-7", "--chart-8"];

function prettify(jobType: string): string {
  return jobType.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function JobTypeBreakdown({ jobs }: JobTypeBreakdownProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const data = useMemo(() => {
    const counts = new Map<string, number>();
    for (const j of jobs) counts.set(j.job_type, (counts.get(j.job_type) ?? 0) + 1);
    const rows = Array.from(counts.entries())
      .map(([key, count], idx) => ({
        name: prettify(key),
        value: count,
        fill: `hsl(var(${COLOR_VARS[idx % COLOR_VARS.length]}))`,
      }))
      .sort((a, b) => b.value - a.value);
    return rows;
  }, [jobs]);

  const total = data.reduce((s, d) => s + d.value, 0);

  if (total === 0) {
    return (
      <div className="flex h-48 flex-col items-center justify-center text-center text-xs text-muted-foreground">
        No jobs in the last 7 days to break down.
      </div>
    );
  }

  const highlighted = activeIndex !== null ? data[activeIndex] : null;

  return (
    <div className="grid h-48 grid-cols-2 items-center gap-3">
      <div className="relative h-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius="60%"
              outerRadius="92%"
              paddingAngle={2}
              stroke="hsl(var(--card))"
              strokeWidth={2}
              onMouseEnter={(_, idx) => setActiveIndex(idx)}
              onMouseLeave={() => setActiveIndex(null)}
              isAnimationActive
              animationDuration={500}
            >
              {data.map((entry, idx) => (
                <Cell
                  key={entry.name}
                  fill={entry.fill}
                  opacity={activeIndex === null || activeIndex === idx ? 1 : 0.4}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 12,
                color: "hsl(var(--foreground))",
              }}
              formatter={(v: number) => [`${v} ${v === 1 ? "job" : "jobs"}`, ""]}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums text-foreground">
            {highlighted ? highlighted.value : total}
          </span>
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {highlighted ? highlighted.name : `jobs · 7d`}
          </span>
        </div>
      </div>

      <ul className="space-y-1.5 overflow-y-auto pr-1 text-xs">
        {data.map((entry, idx) => {
          const pct = Math.round((entry.value / total) * 100);
          const isActive = activeIndex === idx;
          return (
            <li key={entry.name}>
              <button
                type="button"
                onMouseEnter={() => setActiveIndex(idx)}
                onMouseLeave={() => setActiveIndex(null)}
                onFocus={() => setActiveIndex(idx)}
                onBlur={() => setActiveIndex(null)}
                className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                aria-pressed={isActive}
              >
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                  style={{ background: entry.fill }}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate text-foreground">{entry.name}</span>
                <span className="whitespace-nowrap tabular-nums text-muted-foreground">
                  {pct}%
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
