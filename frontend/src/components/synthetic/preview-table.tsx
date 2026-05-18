"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface PreviewTableProps {
  data: Record<string, Record<string, unknown>[]> | null;
  loading: boolean;
}

export function PreviewTable({ data, loading }: PreviewTableProps) {
  const [activeTable, setActiveTable] = useState<string | null>(null);

  if (loading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Generating preview...</div>;
  }

  if (!data || Object.keys(data).length === 0) return null;

  const tables = Object.keys(data);
  const current = activeTable || tables[0];
  const rows = data[current] || [];
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="space-y-3">
      {/* Synthetic data banner */}
      <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-2.5">
        <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
        <p className="text-xs font-medium text-amber-700 dark:text-amber-300">
          This is synthetic data — not real records
        </p>
      </div>

      {/* Table tabs */}
      {tables.length > 1 && (
        <div className="flex gap-1 border-b border-border">
          {tables.map((t) => (
            <button
              key={t}
              onClick={() => setActiveTable(t)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium border-b-2 -mb-px transition-colors",
                current === t ? "border-primary text-primary" : "border-transparent text-muted-foreground"
              )}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Data table with amber tint */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="bg-amber-500/5">
            <tr>
              {columns.map((col) => (
                <th key={col} className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, i) => (
              <tr key={i} className="bg-amber-500/[0.02] hover:bg-amber-500/[0.05]">
                {columns.map((col) => (
                  <td key={col} className="px-3 py-1.5 text-foreground whitespace-nowrap max-w-[200px] truncate">
                    {row[col] === null ? <span className="text-muted-foreground italic">NULL</span> : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground">Showing {rows.length} preview rows for {current}</p>
    </div>
  );
}
