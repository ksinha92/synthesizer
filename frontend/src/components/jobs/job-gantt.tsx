"use client";

import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface GanttJob {
  id: string;
  job_type: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface JobGanttProps {
  jobs: GanttJob[];
}

const TYPE_COLORS: Record<string, string> = {
  discovery: "#3b82f6",
  masking: "#f59e0b",
  generation: "#10b981",
  subsetting: "#8b5cf6",
  workflow: "#ec4899",
};

function getColor(type: string): string {
  return TYPE_COLORS[type] || "#6b7280";
}

export function JobGantt({ jobs }: JobGanttProps) {
  const { data, minTime } = useMemo(() => {
    const jobsWithTime = jobs
      .filter((j) => j.started_at)
      .map((j) => {
        const start = new Date(j.started_at!).getTime();
        const end = j.completed_at ? new Date(j.completed_at).getTime() : Date.now();
        return { ...j, start, end };
      })
      .sort((a, b) => a.start - b.start);

    if (jobsWithTime.length === 0) return { data: [], minTime: 0 };

    const earliest = jobsWithTime[0].start;

    const chartData = jobsWithTime.map((j) => ({
      name: `${j.job_type} (${j.id.slice(0, 6)})`,
      job_type: j.job_type,
      status: j.status,
      offset: (j.start - earliest) / 1000,
      duration: Math.max((j.end - j.start) / 1000, 1),
      startLabel: new Date(j.start).toLocaleTimeString(),
      endLabel: j.completed_at ? new Date(j.completed_at).toLocaleTimeString() : "running",
    }));

    return { data: chartData, minTime: earliest };
  }, [jobs]);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
        No jobs with timing data. Start and complete jobs to see the timeline.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-[11px]">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-5 rounded-sm" style={{ backgroundColor: color }} />
            <span className="capitalize text-muted-foreground">{type}</span>
          </div>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={Math.max(data.length * 36 + 40, 120)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 20, bottom: 4, left: 120 }}
          barSize={18}
        >
          <XAxis
            type="number"
            tickFormatter={(v: number) => `${Math.round(v)}s`}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            axisLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            axisLine={{ stroke: "var(--border)" }}
          />
          <Tooltip
            contentStyle={{
              fontSize: 11,
              backgroundColor: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              color: "var(--foreground)",
            }}
            formatter={(value: number, name: string) => {
              if (name === "duration") return [`${value.toFixed(1)}s`, "Duration"];
              return [value, name];
            }}
            labelFormatter={(label: string) => label}
          />
          <Bar dataKey="offset" stackId="timeline" fill="transparent" />
          <Bar dataKey="duration" stackId="timeline" radius={[0, 4, 4, 0]}>
            {data.map((entry, idx) => (
              <Cell key={idx} fill={getColor(entry.job_type)} fillOpacity={entry.status === "running" ? 0.6 : 1} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
