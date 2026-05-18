"use client";

import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";

interface ComplianceRadialProps {
  pct: number | null;
  protectedCount: number;
  sensitiveCount: number;
}

function toneFor(pct: number): { stroke: string; bg: string; label: string } {
  if (pct >= 95) return { stroke: "--chart-4", bg: "--chart-4", label: "Excellent" };
  if (pct >= 80) return { stroke: "--chart-2", bg: "--chart-2", label: "Healthy" };
  if (pct >= 60) return { stroke: "--chart-5", bg: "--chart-5", label: "Needs review" };
  return { stroke: "--chart-6", bg: "--chart-6", label: "At risk" };
}

export function ComplianceRadial({ pct, protectedCount, sensitiveCount }: ComplianceRadialProps) {
  if (pct === null) {
    return (
      <div className="flex h-48 flex-col items-center justify-center gap-1 text-center">
        <span className="text-3xl font-semibold tabular-nums text-muted-foreground">—</span>
        <p className="text-xs text-muted-foreground">No PII detected yet. Run discovery to score.</p>
      </div>
    );
  }

  const tone = toneFor(pct);
  const data = [{ name: "Compliance", value: pct, fill: `hsl(var(${tone.stroke}))` }];

  return (
    <div className="relative h-48" role="img" aria-label={`Compliance score ${pct}%, ${tone.label}`}>
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          innerRadius="70%"
          outerRadius="100%"
          data={data}
          startAngle={210}
          endAngle={-30}
          barSize={14}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} dataKey="value" tick={false} />
          <RadialBar
            background={{ fill: "hsl(var(--muted))" }}
            dataKey="value"
            cornerRadius={8}
            isAnimationActive
            animationDuration={700}
          />
        </RadialBarChart>
      </ResponsiveContainer>

      {/* Centered label */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-semibold tabular-nums text-foreground">{pct}%</span>
        <span
          className="mt-0.5 text-[11px] font-medium uppercase tracking-wide"
          style={{ color: `hsl(var(${tone.stroke}))` }}
        >
          {tone.label}
        </span>
        <span className="mt-1 text-[10px] text-muted-foreground tabular-nums">
          {protectedCount.toLocaleString()} / {sensitiveCount.toLocaleString()} protected
        </span>
      </div>
    </div>
  );
}
