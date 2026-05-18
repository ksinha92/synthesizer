"use client";

import { cn } from "@/lib/utils";

interface EvidenceChipProps {
  label: string;
  value: string;
  tone: "good" | "warn" | "neutral";
  title?: string;
}

/**
 * Tiny per-signal chip used in the relationship-suggestion table so
 * users see *why* the suggester scored a pair high.
 */
export function EvidenceChip({ label, value, tone, title }: EvidenceChipProps) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px]",
        tone === "good" && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        tone === "warn" && "bg-amber-500/10 text-amber-700 dark:text-amber-300",
        tone === "neutral" && "bg-muted text-muted-foreground",
      )}
    >
      <span className="font-medium uppercase tracking-wide">{label}</span>
      <span className="font-mono">{value}</span>
    </span>
  );
}
