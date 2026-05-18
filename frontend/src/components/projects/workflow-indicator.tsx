"use client";

import Link from "next/link";
import {
  ArrowRight,
  Database,
  FileSearch,
  Play,
  Wand2,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface Step {
  index: number;
  title: string;
  blurb: string;
  icon: React.ElementType;
  /** Path suffix under /projects/[id]. Empty string = Privacy Hub landing. */
  suffix: string;
}

const STEPS: Step[] = [
  {
    index: 1,
    title: "Connect",
    blurb: "Add a read-only connection to your source database, warehouse, or file set.",
    icon: Database,
    suffix: "connections",
  },
  {
    index: 2,
    title: "Identify",
    blurb: "Run discovery — the 4-layer PII pipeline classifies every column with a confidence score.",
    icon: FileSearch,
    suffix: "discovery",
  },
  {
    index: 3,
    title: "Configure",
    blurb: "Apply generators in the Privacy Hub or hand-craft masking policies for finer control.",
    icon: Wand2,
    suffix: "masking",
  },
  {
    index: 4,
    title: "Generate",
    blurb: "Kick off synthetic, masking, or subsetting jobs and route the output to your destination.",
    icon: Play,
    suffix: "synthetic",
  },
];

interface WorkflowIndicatorProps {
  projectId: string;
  /** Highlight the step the user is currently on. */
  activeSuffix?: string;
  /** Compact horizontal-only render (no descriptions). Default is the full
   * card layout shown on the Privacy Hub landing page. */
  compact?: boolean;
}

/**
 * Tonic-style 4-step workflow indicator (screenshot 11.19.52). Renders the
 * Connect → Identify → Configure → Generate horizontal flow with deep-links
 * into each step's project surface. Same data drives the compact eyebrow
 * variant we can drop into the global nav next.
 */
export function WorkflowIndicator({ projectId, activeSuffix, compact }: WorkflowIndicatorProps) {
  const href = (suffix: string) =>
    suffix === "" ? `/projects/${projectId}` : `/projects/${projectId}/${suffix}`;

  if (compact) {
    return (
      <ol aria-label="Workflow steps" className="flex items-center gap-1 text-[10px] uppercase tracking-wide">
        {STEPS.map((s, i) => {
          const active = s.suffix === activeSuffix;
          return (
            <li key={s.index} className="flex items-center gap-1">
              <Link
                href={href(s.suffix)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 transition-colors",
                  active
                    ? "border-[hsl(var(--dw-brand))] bg-[hsl(var(--dw-brand)/0.1)] text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                <span className="font-mono">{s.index}</span>
                {s.title}
              </Link>
              {i < STEPS.length - 1 && (
                <ArrowRight aria-hidden="true" className="h-3 w-3 text-muted-foreground" />
              )}
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <section aria-labelledby="workflow-indicator-title" className="rounded-lg border border-border bg-card px-5 py-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 id="workflow-indicator-title" className="text-sm font-semibold text-foreground">
            How a TDM run flows
          </h2>
          <p className="text-xs text-muted-foreground">
            Four steps from a live database to compliant test data. Skip to any step using the links below.
          </p>
        </div>
      </div>

      <ol className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s) => {
          const active = s.suffix === activeSuffix;
          const Icon = s.icon;
          return (
            <li key={s.index} className="relative">
              <Link
                href={href(s.suffix)}
                aria-current={active ? "step" : undefined}
                className={cn(
                  "group flex h-full flex-col gap-2 rounded-lg border bg-background p-3 transition-all",
                  active
                    ? "border-primary shadow-sm ring-1 ring-primary/30"
                    : "border-border hover:border-primary/40 hover:bg-muted/20"
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "inline-flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold",
                      active
                        ? "bg-[hsl(var(--dw-brand))] text-white"
                        : "bg-muted text-muted-foreground group-hover:bg-[hsl(var(--dw-brand)/0.2)] group-hover:text-foreground"
                    )}
                  >
                    {s.index}
                  </span>
                  <Icon
                    className={cn(
                      "h-3.5 w-3.5",
                      active ? "text-primary" : "text-muted-foreground"
                    )}
                  />
                  <p className={cn("text-sm font-semibold", active ? "text-primary" : "text-foreground")}>
                    {s.title}
                  </p>
                </div>
                <p className="text-[11px] leading-snug text-muted-foreground">{s.blurb}</p>
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
