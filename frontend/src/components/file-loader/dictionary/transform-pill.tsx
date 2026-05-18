"use client";

import { X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface TransformSpec {
  type: "trim" | "pad" | "upper" | "lower" | "substring" | "date_format";
  args?: Record<string, string | number>;
}

interface TransformPillProps {
  transform: TransformSpec;
  onRemove?: () => void;
}

/**
 * Compact rendering of one transform with its key args inline.
 *
 * Shown inline next to each mapping row so users can scan what's
 * happening between source and target.
 */
export function TransformPill({ transform, onRemove }: TransformPillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-input bg-background px-2 py-0.5 text-[10px]",
      )}
    >
      <span className="font-medium uppercase tracking-wide">{transform.type}</span>
      {transform.args && Object.keys(transform.args).length > 0 && (
        <span className="font-mono text-muted-foreground">
          {Object.entries(transform.args)
            .map(([k, v]) => `${k}=${v}`)
            .join(",")}
        </span>
      )}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="text-muted-foreground hover:text-destructive"
          aria-label="Remove transform"
        >
          <X className="h-2.5 w-2.5" />
        </button>
      )}
    </span>
  );
}
