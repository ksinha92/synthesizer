"use client";

import Link from "next/link";
import { ArrowRight, FileText, Plus, Sparkles } from "lucide-react";

interface DashboardHeroProps {
  name?: string | null;
  compliancePct: number | null;
  attentionCount: number;
  loading?: boolean;
  /** Where "New project" navigates — typically /projects. */
  newProjectHref?: string;
  /** Called when "Run discovery" is clicked — opens a project picker dialog. */
  onRunDiscovery?: () => void;
  /** Called when "Reports" is clicked — opens a project picker dialog. */
  onOpenReports?: () => void;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 5) return "You're up late";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function DashboardHero({
  name,
  compliancePct,
  attentionCount,
  loading,
  newProjectHref = "/projects",
  onRunDiscovery,
  onOpenReports,
}: DashboardHeroProps) {
  const headline =
    loading
      ? "Pulling in your latest data..."
      : compliancePct === null
        ? "Welcome to Synthia. Run discovery on a connection to see your privacy posture."
        : compliancePct >= 95
          ? `Your data is ${compliancePct}% compliant. Everything looks healthy.`
          : compliancePct >= 75
            ? `Your data is ${compliancePct}% compliant. ${attentionCount} ${attentionCount === 1 ? "item needs" : "items need"} attention.`
            : `Your data is ${compliancePct}% compliant. Privacy coverage needs review — ${attentionCount} ${attentionCount === 1 ? "item" : "items"} flagged.`;

  return (
    <section
      aria-label="Workspace overview"
      className="relative overflow-hidden rounded-xl border border-border bg-card p-6 shadow-sm"
    >
      {/* Brand gradient wash — uses dw-cta tokens (teal → purple) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.06] dark:opacity-[0.12]"
        style={{
          background:
            "linear-gradient(120deg, hsl(var(--dw-cta-from)) 0%, hsl(var(--dw-cta-to)) 100%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full opacity-20 blur-3xl"
        style={{ background: "hsl(var(--dw-brand))" }}
      />

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {greeting()}{name ? `, ${name.split(" ")[0]}` : ""}
          </p>
          <h1 className="mt-1 text-2xl font-semibold leading-tight text-foreground sm:text-3xl">
            {headline}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Synthia · AI-Powered Test Data Management
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={newProjectHref}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <Plus className="h-4 w-4" />
            New project
          </Link>
          <button
            type="button"
            onClick={onRunDiscovery}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3.5 py-2 text-sm font-medium text-foreground hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <Sparkles className="h-4 w-4" />
            Run discovery
          </button>
          <button
            type="button"
            onClick={onOpenReports}
            className="hidden sm:inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3.5 py-2 text-sm font-medium text-foreground hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <FileText className="h-4 w-4" />
            Reports
            <ArrowRight className="h-3 w-3 opacity-60" />
          </button>
        </div>
      </div>
    </section>
  );
}
