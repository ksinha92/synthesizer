"use client";

import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  Lightbulb,
  ListChecks,
  Settings2,
  TriangleAlert,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Illustration } from "@/components/help/illustration";
import { MiniDemo } from "@/components/help/mini-demo";
import { getTopic, HELP_TOPICS } from "@/content/help-content";

export default function TopicPage() {
  const params = useParams<{ topic: string }>();
  const topic = getTopic(params.topic);
  if (!topic) return notFound();

  const Icon = topic.icon;
  const idx = HELP_TOPICS.findIndex((t) => t.slug === topic.slug);
  const prev = HELP_TOPICS[(idx - 1 + HELP_TOPICS.length) % HELP_TOPICS.length];
  const next = HELP_TOPICS[(idx + 1) % HELP_TOPICS.length];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Breadcrumb */}
        <nav aria-label="Help navigation" className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link href="/help" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" />
            All topics
          </Link>
          <span className="opacity-50">/</span>
          <span className="font-medium text-foreground">{topic.title}</span>
        </nav>

        {/* Hero */}
        <header className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <div className="flex items-center gap-2">
              <span
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wider"
                style={{
                  background: `hsl(var(${topic.accent}) / 0.12)`,
                  color: `hsl(var(${topic.accent}))`,
                }}
              >
                {topic.category}
              </span>
              {topic.appRoute && (
                <Link
                  href={topic.appRoute}
                  className="inline-flex items-center gap-1 rounded-full border border-border bg-background px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground hover:text-foreground"
                >
                  Open in app
                  <ExternalLink className="h-2.5 w-2.5" />
                </Link>
              )}
            </div>
            <div className="mt-3 flex items-start gap-4">
              <div
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
                style={{ background: `hsl(var(${topic.accent}) / 0.12)` }}
              >
                <Icon className="h-6 w-6" style={{ color: `hsl(var(${topic.accent}))` }} aria-hidden />
              </div>
              <div>
                <h1 className="text-3xl font-semibold leading-tight text-foreground">{topic.title}</h1>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{topic.short}</p>
              </div>
            </div>
          </div>
          <div className="lg:col-span-2">
            <div className="h-48 sm:h-56">
              <Illustration kind={topic.illustration} accent={topic.accent} />
            </div>
          </div>
        </header>

        {/* What it does */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            What it does
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-foreground">{topic.what}</p>
        </section>

        {/* When to use it */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-amber-500" aria-hidden />
            <h2 className="text-sm font-semibold text-foreground">When to use it</h2>
          </div>
          <ul className="mt-3 space-y-2 text-sm text-foreground">
            {topic.whenToUse.map((u, i) => (
              <li key={i} className="flex gap-2">
                <CheckCircle2
                  className="mt-0.5 h-4 w-4 shrink-0"
                  style={{ color: `hsl(var(${topic.accent}))` }}
                  aria-hidden
                />
                <span>{u}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* How it works (numbered cards) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-primary" aria-hidden />
            <h2 className="text-sm font-semibold text-foreground">How it works in Synthia</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {topic.howItWorks.map((step, i) => (
              <div
                key={step.title}
                className="relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <span
                  className="absolute -right-4 -top-4 text-7xl font-bold tabular-nums opacity-[0.07]"
                  aria-hidden
                  style={{ color: `hsl(var(${topic.accent}))` }}
                >
                  {i + 1}
                </span>
                <span
                  className="inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold"
                  style={{
                    background: `hsl(var(${topic.accent}) / 0.12)`,
                    color: `hsl(var(${topic.accent}))`,
                  }}
                >
                  {i + 1}
                </span>
                <h3 className="mt-3 text-sm font-semibold text-foreground">{step.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{step.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Interactive demo (only when applicable) */}
        {topic.demo !== "none" && <MiniDemo kind={topic.demo} />}

        {/* Examples */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-emerald-500" aria-hidden />
            <h2 className="text-sm font-semibold text-foreground">Real-world examples</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {topic.examples.map((ex) => (
              <div
                key={ex.title}
                className="rounded-lg border border-border bg-background p-4"
              >
                <h3 className="text-sm font-semibold text-foreground">{ex.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{ex.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Gotchas */}
        <section className="rounded-xl border border-amber-500/30 bg-amber-500/[0.04] p-6">
          <div className="mb-2 flex items-center gap-2">
            <TriangleAlert className="h-4 w-4 text-amber-600 dark:text-amber-400" aria-hidden />
            <h2 className="text-sm font-semibold text-foreground">Watch out for</h2>
          </div>
          <ul className="space-y-2 text-sm text-foreground">
            {topic.gotchas.map((g, i) => (
              <li key={i} className="flex gap-2">
                <span
                  aria-hidden
                  className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500/70"
                />
                <span>{g}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* Prev / Next */}
        <nav aria-label="Topic navigation" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Link
            href={`/help/${prev.slug}`}
            className="group inline-flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-4 shadow-sm hover:border-foreground/15 hover:shadow-md"
          >
            <div className="flex items-center gap-2 text-muted-foreground">
              <ArrowLeft className="h-4 w-4" />
              <span className="text-[10px] uppercase tracking-wider">Previous</span>
            </div>
            <span className="truncate text-sm font-medium text-foreground">{prev.title}</span>
          </Link>
          <Link
            href={`/help/${next.slug}`}
            className="group inline-flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-4 shadow-sm hover:border-foreground/15 hover:shadow-md"
          >
            <span className="truncate text-sm font-medium text-foreground">{next.title}</span>
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="text-[10px] uppercase tracking-wider">Next</span>
              <ArrowRight className="h-4 w-4" />
            </div>
          </Link>
        </nav>
      </div>
    </AppShell>
  );
}
