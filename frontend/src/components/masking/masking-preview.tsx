"use client";

import { AlertTriangle, Info } from "lucide-react";

interface MaskingPreviewProps {
  data: { original: Record<string, unknown>; masked: Record<string, unknown> }[];
}

export function MaskingPreview({ data }: MaskingPreviewProps) {
  if (data.length === 0) return null;

  const columns = Object.keys(data[0]?.original || {});

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 rounded-lg bg-blue-500/10 border border-blue-500/20 px-4 py-2.5">
        <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0" />
        <p className="text-xs text-blue-700 dark:text-blue-300">
          Sample values shown are pre-masked approximations from schema discovery — not real production data
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/50">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Column</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Original</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground bg-amber-500/5">Masked</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.map((row, i) =>
              columns.map((col, j) => (
                <tr key={`${i}-${j}`} className={i % 2 === 0 ? "" : "bg-muted/20"}>
                  {j === 0 && <td className="px-3 py-1.5 font-mono text-muted-foreground" rowSpan={columns.length}>Row {i + 1}</td>}
                  <td className="px-3 py-1.5 text-foreground">{String(row.original[col] ?? "NULL")}</td>
                  <td className={`px-3 py-1.5 text-foreground ${String(row.original[col]) !== String(row.masked[col]) ? "bg-amber-100 dark:bg-amber-500/20" : "bg-amber-500/[0.03]"}`}>
                    {String(row.masked[col] ?? "NULL")}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
