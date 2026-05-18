"use client";

import { cn } from "@/lib/utils";

interface PIIBadgeProps {
  piiType: string;
  confidence: number;
  classification: string;
  size?: "sm" | "md";
}

export function PIIBadge({ piiType, confidence, classification, size = "sm" }: PIIBadgeProps) {
  if (piiType === "none" || classification === "dismissed") return null;

  const color =
    confidence >= 0.65 ? "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20" :
    confidence >= 0.4 ? "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/20" :
    "bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-medium",
        color,
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"
      )}
      title={`${piiType} — ${Math.round(confidence * 100)}% confidence (${classification})`}
    >
      {piiType.replace("_", " ")}
      <span className="opacity-70">{Math.round(confidence * 100)}%</span>
    </span>
  );
}

export function PIIDot({ piiType, confidence }: { piiType: string; confidence: number }) {
  if (piiType === "none") return null;
  const color = confidence >= 0.65 ? "bg-red-500" : confidence >= 0.4 ? "bg-yellow-500" : "bg-gray-400";
  return <span className={cn("inline-block h-2 w-2 rounded-full shrink-0", color)} />;
}
