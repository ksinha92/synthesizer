"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import { cn } from "@/lib/utils";

export type KpiTone = "neutral" | "good" | "warn" | "danger" | "accent" | "info";

interface KpiCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  /** If set, the card is a Link to this URL. Mutually exclusive with onClick. */
  href?: string;
  /** If set, the card is a button that calls this handler. Takes precedence over href. */
  onClick?: () => void;
  /** Aria label for the click affordance — useful when the card is a button. */
  actionLabel?: string;
  delta?: number | null;
  deltaLabel?: string;
  deltaInverted?: boolean;
  spark?: number[];
  tone?: KpiTone;
  hint?: string;
}

const TONE: Record<KpiTone, { fg: string; bg: string; stroke: string }> = {
  neutral: {
    fg: "text-primary",
    bg: "bg-[hsl(var(--chart-1)/0.12)]",
    stroke: "hsl(var(--chart-1))",
  },
  good: {
    fg: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-[hsl(var(--chart-4)/0.12)]",
    stroke: "hsl(var(--chart-4))",
  },
  warn: {
    fg: "text-amber-600 dark:text-amber-400",
    bg: "bg-[hsl(var(--chart-5)/0.12)]",
    stroke: "hsl(var(--chart-5))",
  },
  danger: {
    fg: "text-red-600 dark:text-red-400",
    bg: "bg-[hsl(var(--chart-6)/0.12)]",
    stroke: "hsl(var(--chart-6))",
  },
  accent: {
    fg: "text-[hsl(var(--chart-3))]",
    bg: "bg-[hsl(var(--chart-3)/0.12)]",
    stroke: "hsl(var(--chart-3))",
  },
  info: {
    fg: "text-[hsl(var(--chart-7))]",
    bg: "bg-[hsl(var(--chart-7)/0.12)]",
    stroke: "hsl(var(--chart-7))",
  },
};

function Delta({ value, label, inverted }: { value: number; label?: string; inverted?: boolean }) {
  const isUp = value > 0;
  const isFlat = value === 0;
  const positive = inverted ? !isUp : isUp;
  const Icon = isFlat ? Minus : isUp ? ArrowUpRight : ArrowDownRight;
  const klass = isFlat
    ? "text-muted-foreground"
    : positive
      ? "text-emerald-600 dark:text-emerald-400"
      : "text-red-600 dark:text-red-400";
  return (
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium", klass)}>
      <Icon className="h-3 w-3" aria-hidden />
      {Math.abs(value)}
      {label && <span className="ml-1 font-normal text-muted-foreground">{label}</span>}
    </span>
  );
}

export function KpiCard({
  label,
  value,
  icon: Icon,
  href,
  onClick,
  actionLabel,
  delta,
  deltaLabel = "vs 7d",
  deltaInverted = false,
  spark,
  tone = "neutral",
  hint,
}: KpiCardProps) {
  const t = TONE[tone];
  const sparkData = spark?.map((v, i) => ({ i, v })) ?? [];
  const ariaSummary =
    typeof value === "number" || typeof value === "string"
      ? `${label}: ${value}${delta !== undefined && delta !== null ? `, ${delta >= 0 ? "up" : "down"} ${Math.abs(delta)} ${deltaLabel}` : ""}`
      : label;

  const body = (
    <div
      className="group relative h-full overflow-hidden rounded-lg border border-border bg-card p-4 shadow-sm transition-all hover:shadow-md hover:border-foreground/10"
      role={href ? undefined : "group"}
      aria-label={ariaSummary}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-semibold leading-none text-foreground tabular-nums">{value}</p>
          <div className="mt-2 flex items-center gap-2 text-xs">
            {delta !== undefined && delta !== null ? (
              <Delta value={delta} label={deltaLabel} inverted={deltaInverted} />
            ) : hint ? (
              <span className="text-muted-foreground">{hint}</span>
            ) : null}
          </div>
        </div>
        <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", t.bg)}>
          <Icon className={cn("h-4 w-4", t.fg)} aria-hidden />
        </div>
      </div>

      {spark && spark.length > 1 && (
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 h-10 opacity-90"
          aria-hidden
        >
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={`spark-${label.replace(/\s+/g, "-")}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={t.stroke} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={t.stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis hide domain={["dataMin", "dataMax"]} />
              <Area
                type="monotone"
                dataKey="v"
                stroke={t.stroke}
                strokeWidth={1.5}
                fill={`url(#spark-${label.replace(/\s+/g, "-")})`}
                isAnimationActive
                animationDuration={400}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={actionLabel ?? ariaSummary}
        className="block w-full text-left focus-visible:rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        {body}
      </button>
    );
  }
  if (href) {
    return (
      <Link href={href} className="block focus-visible:rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
        {body}
      </Link>
    );
  }
  return body;
}
