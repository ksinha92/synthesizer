"use client";

import { useState, useRef, useEffect } from "react";
import { HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface HelpTooltipProps {
  text: string;
  position?: "top" | "right" | "bottom" | "left";
}

const POSITIONS = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
  right: "left-full top-1/2 -translate-y-1/2 ml-2",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
  left: "right-full top-1/2 -translate-y-1/2 mr-2",
};

export function HelpTooltip({ text, position = "top" }: HelpTooltipProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div className="relative inline-flex" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="text-muted-foreground hover:text-foreground transition-colors"
        type="button"
      >
        <HelpCircle className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className={cn("absolute z-50 w-48 rounded-lg border border-border bg-card p-2.5 text-xs text-foreground shadow-lg", POSITIONS[position])}>
          {text}
        </div>
      )}
    </div>
  );
}
