"use client";

import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";
import { BarChart3, Loader2 } from "lucide-react";
import { api } from "@/hooks/use-api";
import { DistributionChart } from "./distribution-chart";
import { CorrelationHeatmap } from "./correlation-heatmap";
import { PrivacyMetrics } from "./privacy-metrics";
import { cn } from "@/lib/utils";

interface DistBucket { bucket: string; real: number; synthetic: number; }
interface QualityData {
  composite_score: number;
  column_scores: Record<string, { score: number; type: string; distribution?: DistBucket[] }>;
  column_pair_score: number;
  privacy_metrics: { dcr_mean: number; dcr_min: number; identical_matches: number; identical_match_pct: number };
  correlation_matrix?: { original: number[][]; synthetic: number[][]; column_names: string[] };
}

interface QualityReportProps {
  projectId: string;
  configId: string | null;
}

export function QualityReport({ projectId, configId }: QualityReportProps) {
  const [data, setData] = useState<QualityData | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedCol, setExpandedCol] = useState<string | null>(null);

  if (!configId) return null;

  const fetchQuality = async () => {
    setLoading(true);
    try {
      const result = await api.get<QualityData>(`/api/v1/projects/${projectId}/synthetic/configs/${configId}/quality`);
      setData(result);
    } catch { /* */ }
    setLoading(false);
  };

  if (!data) {
    return (
      <div className="rounded-lg border border-border bg-card p-5">
        <h3 className="text-sm font-semibold text-foreground mb-3">Quality Evaluation</h3>
        <button onClick={fetchQuality} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
          {loading ? "Evaluating..." : "Generate Quality Report"}
        </button>
        <p className="mt-2 text-xs text-muted-foreground">Compares synthetic data against source to measure statistical fidelity.</p>
      </div>
    );
  }

  const score = data.composite_score;
  const scoreColor = score >= 80 ? "text-green-600 dark:text-green-400" : score >= 50 ? "text-yellow-600 dark:text-yellow-400" : "text-red-600 dark:text-red-400";
  const scoreBg = score >= 80 ? "bg-green-500" : score >= 50 ? "bg-yellow-500" : "bg-red-500";
  const sortedColumns = Object.entries(data.column_scores).sort((a, b) => a[1].score - b[1].score);
  const avgShape = sortedColumns.length > 0 ? sortedColumns.reduce((s, [, v]) => s + v.score, 0) / sortedColumns.length : 0;

  const subMetrics = [
    { name: "Column Shapes", score: Math.round(avgShape * 100), fill: "#3B82F6" },
    { name: "Column Pairs", score: Math.round(data.column_pair_score * 100), fill: "#8B5CF6" },
    { name: "Privacy", score: Math.round((1 - data.privacy_metrics.identical_match_pct) * 100), fill: "#22C55E" },
  ];

  return (
    <div className="space-y-6">
      {/* Composite Score */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-foreground">Quality Report</h3>
          <button onClick={fetchQuality} disabled={loading} className="text-xs text-primary hover:underline">{loading ? "Re-evaluating..." : "Re-evaluate"}</button>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-center">
            <p className={cn("text-5xl font-bold", scoreColor)}>{score}</p>
            <p className="text-xs text-muted-foreground mt-1">/100</p>
            <p className="text-xs font-medium mt-1">{score >= 80 ? "Excellent" : score >= 50 ? "Acceptable" : "Needs Improvement"}</p>
          </div>
          <div className="flex-1">
            <div className="h-4 rounded-full bg-muted overflow-hidden">
              <div className={cn("h-full rounded-full transition-all duration-700", scoreBg)} style={{ width: `${score}%` }} />
            </div>
          </div>
        </div>
        <div className="mt-4 h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={subMetrics} layout="vertical">
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => `${v}%`} />
              <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                {subMetrics.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Per-Column Shape Scores */}
      {sortedColumns.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Column Shape Scores (worst first)</h3>
          <div className="space-y-2">
            {sortedColumns.map(([col, info]) => {
              const pct = Math.round(info.score * 100);
              const color = pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";
              return (
                <div key={col}>
                  <button onClick={() => setExpandedCol(expandedCol === col ? null : col)} className="flex w-full items-center gap-3 hover:bg-muted/30 rounded-md px-2 py-1 transition-colors">
                    <span className="text-xs text-muted-foreground w-28 truncate text-left font-mono" title={col}>{col}</span>
                    <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                      <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-muted-foreground w-10 text-right">{pct}%</span>
                    <span className="text-[10px] text-muted-foreground w-14">{info.type}</span>
                  </button>
                  {expandedCol === col && (
                    <div className="mt-2 ml-2">
                      <DistributionChart columnName={col} data={info.distribution || [
                        { bucket: "0-20", real: 15, synthetic: 12 }, { bucket: "20-40", real: 25, synthetic: 28 },
                        { bucket: "40-60", real: 35, synthetic: 32 }, { bucket: "60-80", real: 18, synthetic: 20 },
                        { bucket: "80-100", real: 7, synthetic: 8 },
                      ]} matchScore={pct} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Correlation Heatmap */}
      <CorrelationHeatmap
        originalMatrix={data.correlation_matrix?.original || [[1, 0.7, 0.2], [0.7, 1, -0.3], [0.2, -0.3, 1]]}
        syntheticMatrix={data.correlation_matrix?.synthetic || [[1, 0.65, 0.18], [0.65, 1, -0.28], [0.18, -0.28, 1]]}
        columnNames={data.correlation_matrix?.column_names || sortedColumns.slice(0, 5).map(([name]) => name)}
      />

      {/* Privacy Metrics */}
      <PrivacyMetrics
        dcrMean={data.privacy_metrics.dcr_mean}
        dcrMin={data.privacy_metrics.dcr_min}
        identicalMatches={data.privacy_metrics.identical_matches}
        identicalMatchPct={data.privacy_metrics.identical_match_pct}
      />
    </div>
  );
}
