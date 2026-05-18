"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface DistributionChartProps {
  columnName: string;
  data: { bucket: string; real: number; synthetic: number }[];
  matchScore: number;
}

export function DistributionChart({ columnName, data, matchScore }: DistributionChartProps) {
  const scoreColor = matchScore >= 80 ? "text-green-600" : matchScore >= 50 ? "text-yellow-600" : "text-red-600";

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-foreground font-mono">{columnName}</span>
        <span className={`text-xs font-semibold ${scoreColor}`}>{matchScore}% match</span>
      </div>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barCategoryGap="20%">
            <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="real" name="Real Data" fill="#334155" radius={[2, 2, 0, 0]} />
            <Bar dataKey="synthetic" name="Synthetic" fill="#3B82F6" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
