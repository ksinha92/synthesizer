"use client";

import { cn } from "@/lib/utils";

interface CorrelationHeatmapProps {
  originalMatrix: number[][];
  syntheticMatrix: number[][];
  columnNames: string[];
}

function getCellColor(value: number): string {
  if (value >= 0.7) return "bg-blue-600 text-white";
  if (value >= 0.3) return "bg-blue-300 text-blue-900";
  if (value >= -0.3) return "bg-gray-100 dark:bg-gray-800 text-gray-600";
  if (value >= -0.7) return "bg-red-300 text-red-900";
  return "bg-red-600 text-white";
}

function HeatmapGrid({ title, matrix, columnNames }: { title: string; matrix: number[][]; columnNames: string[] }) {
  if (!matrix.length || !columnNames.length) return null;

  return (
    <div className="space-y-1">
      <h4 className="text-xs font-medium text-muted-foreground text-center">{title}</h4>
      <div className="overflow-x-auto">
        <div className="inline-grid gap-px" style={{ gridTemplateColumns: `60px repeat(${columnNames.length}, 36px)` }}>
          {/* Header row */}
          <div />
          {columnNames.map((name) => (
            <div key={name} className="text-[8px] text-muted-foreground truncate text-center rotate-[-45deg] h-8 flex items-end justify-center">
              {name.slice(0, 6)}
            </div>
          ))}

          {/* Data rows */}
          {matrix.map((row, i) => (
            <>
              <div key={`label-${i}`} className="text-[9px] text-muted-foreground truncate pr-1 flex items-center">{columnNames[i]?.slice(0, 8)}</div>
              {row.map((val, j) => (
                <div
                  key={`${i}-${j}`}
                  className={cn("w-9 h-6 flex items-center justify-center text-[8px] rounded-sm", getCellColor(val))}
                  title={`${columnNames[i]} × ${columnNames[j]}: ${val.toFixed(2)}`}
                >
                  {val.toFixed(1)}
                </div>
              ))}
            </>
          ))}
        </div>
      </div>
    </div>
  );
}

export function CorrelationHeatmap({ originalMatrix, syntheticMatrix, columnNames }: CorrelationHeatmapProps) {
  // Compute difference matrix
  const diffMatrix = originalMatrix.map((row, i) =>
    row.map((val, j) => Math.abs(val - (syntheticMatrix[i]?.[j] || 0)))
  );

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-foreground mb-4">Correlation Comparison</h3>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <HeatmapGrid title="Original" matrix={originalMatrix} columnNames={columnNames} />
        <HeatmapGrid title="Synthetic" matrix={syntheticMatrix} columnNames={columnNames} />
        <HeatmapGrid title="Difference" matrix={diffMatrix} columnNames={columnNames} />
      </div>
      <p className="text-[10px] text-muted-foreground mt-2">Blue = positive correlation, Red = negative, Gray = none. Difference shows absolute deviation.</p>
    </div>
  );
}
