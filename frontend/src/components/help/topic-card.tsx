"use client";

import Link from "next/link";
import { ArrowRight, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface TopicCardProps {
  href: string;
  title: string;
  short: string;
  icon: LucideIcon;
  accent: string; // chart-N CSS var key
  category?: string;
}

export function TopicCard({ href, title, short, icon: Icon, accent, category }: TopicCardProps) {
  return (
    <Link
      href={href}
      className={cn(
        "group relative flex h-full flex-col gap-3 overflow-hidden rounded-xl border border-border bg-card p-5 shadow-sm transition-all",
        "hover:-translate-y-0.5 hover:border-foreground/15 hover:shadow-md",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
      )}
    >
      {/* accent glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full blur-2xl transition-opacity group-hover:opacity-70 opacity-30"
        style={{ background: `hsl(var(${accent}) / 0.35)` }}
      />
      <div className="flex items-start justify-between">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: `hsl(var(${accent}) / 0.12)` }}
        >
          <Icon className="h-5 w-5" style={{ color: `hsl(var(${accent}))` }} aria-hidden />
        </div>
        {category && (
          <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {category}
          </span>
        )}
      </div>
      <div className="flex-1">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{short}</p>
      </div>
      <span className="inline-flex items-center gap-1 text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
        Learn more <ArrowRight className="h-3 w-3" />
      </span>
    </Link>
  );
}
