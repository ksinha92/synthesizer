"use client";

import { cn } from "@/lib/utils";
import type { LayoutVariant } from "../types";

interface LayoutSwitcherProps {
  variants: LayoutVariant[];
  selected: string; // "_base" or variant name
  onSelect: (name: string) => void;
}

/**
 * Tab strip used to switch which record layout the structure tree
 * displays. "_base" is the schema's flat field list; the others are
 * conditional variants set by the wizard's discriminator step.
 */
export function LayoutSwitcher({ variants, selected, onSelect }: LayoutSwitcherProps) {
  if (variants.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-border bg-muted/20 px-2 py-1">
      <button
        type="button"
        onClick={() => onSelect("_base")}
        className={cn(
          "rounded px-2 py-0.5 text-[11px] font-medium",
          selected === "_base"
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:bg-muted/40",
        )}
      >
        Base layout
      </button>
      {variants.map((v) => (
        <button
          key={v.name}
          type="button"
          onClick={() => onSelect(v.name)}
          title={
            v.conditions.length === 0
              ? "No discriminator conditions set — preview cannot route rows to this variant"
              : v.conditions
                  .map((c) => `${c.field_name} ${c.operator} ${Array.isArray(c.value) ? c.value.join(",") : c.value}`)
                  .join(" AND ")
          }
          className={cn(
            "rounded px-2 py-0.5 text-[11px] font-medium",
            selected === v.name
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted/40",
            v.conditions.length === 0 && "italic",
          )}
        >
          {v.name}
          {v.conditions.length === 0 && " *"}
        </button>
      ))}
      {variants.some((v) => v.conditions.length === 0) && (
        <span className="ml-1 text-[10px] text-amber-700 dark:text-amber-300">
          * needs discriminator conditions
        </span>
      )}
    </div>
  );
}
