"use client";

import Link from "next/link";
import { ArrowLeft, HelpCircle, Sparkles } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { FaqAccordion } from "@/components/help/faq-accordion";
import { FAQ_ENTRIES, faqCategories } from "@/content/help-content";

export default function FaqPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <nav aria-label="Help navigation" className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link href="/help" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" />
            All topics
          </Link>
          <span className="opacity-50">/</span>
          <span className="font-medium text-foreground">FAQ</span>
        </nav>

        <header className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full opacity-25 blur-3xl"
            style={{ background: "hsl(var(--chart-3))" }}
          />
          <div className="relative flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
              <HelpCircle className="h-6 w-6 text-primary" aria-hidden />
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-semibold text-foreground sm:text-3xl">
                Frequently asked questions
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Searchable answers to the questions teams ask most. Use the categories to narrow down,
                or type a keyword to filter across all entries.
              </p>
            </div>
          </div>
        </header>

        <FaqAccordion entries={FAQ_ENTRIES} categories={faqCategories()} />

        <section className="rounded-xl border border-border bg-gradient-to-br from-card to-muted/30 p-6">
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Sparkles className="h-5 w-5 text-primary" aria-hidden />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-foreground">Looking for a deeper guide?</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Each feature has its own illustrated topic page with examples and interactive demos.
                </p>
              </div>
            </div>
            <Link
              href="/help"
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3.5 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              Browse topics
            </Link>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
