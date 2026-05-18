"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  ShieldAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type InsightSeverity = "danger" | "warn" | "info" | "good";

export interface Insight {
  id: string;
  severity: InsightSeverity;
  title: string;
  body: string;
  ctaLabel: string;
  ctaHref: string;
}

const ICONS: Record<InsightSeverity, LucideIcon> = {
  danger: ShieldAlert,
  warn: AlertTriangle,
  info: Clock,
  good: CheckCircle2,
};

const TONE: Record<InsightSeverity, { ring: string; iconBg: string; iconFg: string; badge: string }> = {
  danger: {
    ring: "ring-1 ring-red-500/20",
    iconBg: "bg-red-500/10",
    iconFg: "text-red-600 dark:text-red-400",
    badge: "Critical",
  },
  warn: {
    ring: "ring-1 ring-amber-500/20",
    iconBg: "bg-amber-500/10",
    iconFg: "text-amber-600 dark:text-amber-400",
    badge: "Attention",
  },
  info: {
    ring: "ring-1 ring-blue-500/20",
    iconBg: "bg-blue-500/10",
    iconFg: "text-blue-600 dark:text-blue-400",
    badge: "Notice",
  },
  good: {
    ring: "ring-1 ring-emerald-500/20",
    iconBg: "bg-emerald-500/10",
    iconFg: "text-emerald-600 dark:text-emerald-400",
    badge: "Healthy",
  },
};

const SEVERITY_ORDER: Record<InsightSeverity, number> = {
  danger: 0,
  warn: 1,
  info: 2,
  good: 3,
};

interface InsightCardsProps {
  insights: Insight[];
  emptyMessage?: string;
}

export function InsightCards({
  insights,
  emptyMessage = "Nothing needs your attention right now. Nice work.",
}: InsightCardsProps) {
  const sorted = [...insights].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );

  if (sorted.length === 0) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-6 text-sm text-emerald-700 dark:text-emerald-300">
        <CheckCircle2 className="h-4 w-4" aria-hidden />
        {emptyMessage}
      </div>
    );
  }

  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Actionable insights">
      {sorted.slice(0, 6).map((insight) => {
        const Icon = ICONS[insight.severity];
        const t = TONE[insight.severity];
        return (
          <li
            key={insight.id}
            className={cn(
              "group relative flex flex-col rounded-lg border border-border bg-card p-4 shadow-sm transition-all hover:shadow-md",
              t.ring,
            )}
          >
            <div className="flex items-start gap-3">
              <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", t.iconBg)}>
                <Icon className={cn("h-4 w-4", t.iconFg)} aria-hidden />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-foreground">{insight.title}</h3>
                  <span className={cn("inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium", t.iconBg, t.iconFg)}>
                    {t.badge}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{insight.body}</p>
              </div>
            </div>
            <Link
              href={insight.ctaHref}
              className="mt-3 inline-flex w-fit items-center gap-1 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              {insight.ctaLabel}
              <ArrowRight className="h-3 w-3" />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

// Helper: failed-jobs insight uses XCircle visually, exported for the page to reuse
export { XCircle };
