"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, HelpCircle, Map as MapIcon, Search, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { TopicCard } from "@/components/help/topic-card";
import { topicCategories, HELP_TOPICS } from "@/content/help-content";

export default function HelpIndexPage() {
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return topicCategories();
    const filtered = HELP_TOPICS.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.short.toLowerCase().includes(q) ||
        t.what.toLowerCase().includes(q),
    );
    if (filtered.length === 0) return [];
    return [{ name: "Results" as const, topics: filtered }];
  }, [query]);

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Hero */}
        <section
          aria-labelledby="help-hero"
          className="relative overflow-hidden rounded-2xl border border-border bg-card p-8 shadow-sm"
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.12]"
            style={{
              background:
                "linear-gradient(120deg, hsl(var(--dw-cta-from)) 0%, hsl(var(--dw-cta-to)) 100%)",
            }}
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full opacity-25 blur-3xl"
            style={{ background: "hsl(var(--dw-brand))" }}
          />
          <div className="relative max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5 text-primary" />
              Synthia Help Center
            </div>
            <h1 id="help-hero" className="mt-3 text-3xl font-semibold leading-tight text-foreground sm:text-4xl">
              Learn how Synthia keeps your test data safe and useful
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              Short, illustrated guides for every feature — plus an interactive onboarding tour and
              a searchable FAQ. Each topic has a try-it-yourself demo where useful.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              <Link
                href="/help/onboarding"
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90"
              >
                <MapIcon className="h-4 w-4" />
                Start onboarding
                <ArrowRight className="h-3 w-3 opacity-80" />
              </Link>
              <Link
                href="/help/faq"
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3.5 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
              >
                <HelpCircle className="h-4 w-4" />
                Browse FAQ
              </Link>
            </div>

            {/* Search */}
            <label className="relative mt-6 block max-w-md">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search topics — e.g. 'masking', 'webhook'…"
                className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                aria-label="Search help topics"
              />
            </label>
          </div>
        </section>

        {/* Topic grid */}
        {groups.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-8 text-center">
            <p className="text-sm font-medium text-foreground">No topics match &ldquo;{query}&rdquo;</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Try a different keyword or clear the search.
            </p>
          </div>
        ) : (
          groups.map((group) => (
            <section key={group.name} aria-labelledby={`group-${group.name}`} className="space-y-4">
              <div className="flex items-center gap-3">
                <h2
                  id={`group-${group.name}`}
                  className="text-sm font-semibold uppercase tracking-wider text-muted-foreground"
                >
                  {group.name}
                </h2>
                <div className="h-px flex-1 bg-border" />
                <span className="text-xs text-muted-foreground">
                  {group.topics.length} {group.topics.length === 1 ? "topic" : "topics"}
                </span>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {group.topics.map((t) => (
                  <TopicCard
                    key={t.slug}
                    href={`/help/${t.slug}`}
                    title={t.title}
                    short={t.short}
                    icon={t.icon}
                    accent={t.accent}
                    category={t.category}
                  />
                ))}
              </div>
            </section>
          ))
        )}

        {/* Footer CTA strip */}
        <section className="rounded-xl border border-border bg-gradient-to-br from-card to-muted/30 p-6">
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Sparkles className="h-5 w-5 text-primary" aria-hidden />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">Still have questions?</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  The FAQ covers the most common scenarios — searchable by keyword and grouped by topic.
                </p>
              </div>
            </div>
            <Link
              href="/help/faq"
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3.5 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              Open FAQ
              <ArrowRight className="h-3 w-3 opacity-70" />
            </Link>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
