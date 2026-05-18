"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Circle,
  Map as MapIcon,
  PartyPopper,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Illustration } from "@/components/help/illustration";
import { ONBOARDING_STEPS } from "@/content/help-content";
import { cn } from "@/lib/utils";

export default function OnboardingPage() {
  const [active, setActive] = useState(0);
  const [completed, setCompleted] = useState<Set<number>>(new Set());

  const step = ONBOARDING_STEPS[active];
  const StepIcon = step.icon;
  const isLast = active === ONBOARDING_STEPS.length - 1;
  const allDone = completed.size === ONBOARDING_STEPS.length;

  const goNext = () => {
    setCompleted((prev) => new Set(prev).add(active));
    if (!isLast) setActive((a) => a + 1);
  };
  const goPrev = () => {
    if (active > 0) setActive((a) => a - 1);
  };

  const progressPct = useMemo(
    () => Math.round((completed.size / ONBOARDING_STEPS.length) * 100),
    [completed],
  );

  return (
    <AppShell>
      <div className="space-y-6">
        <nav aria-label="Help navigation" className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link href="/help" className="inline-flex items-center gap-1 hover:text-foreground">
            <ArrowLeft className="h-3 w-3" />
            All topics
          </Link>
          <span className="opacity-50">/</span>
          <span className="font-medium text-foreground">Onboarding</span>
        </nav>

        {/* Hero strip with progress bar */}
        <header className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.10]"
            style={{
              background:
                "linear-gradient(120deg, hsl(var(--dw-cta-from)) 0%, hsl(var(--dw-cta-to)) 100%)",
            }}
          />
          <div className="relative">
            <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <MapIcon className="h-5 w-5 text-primary" aria-hidden />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-foreground sm:text-2xl">
                    Get started with Synthia
                  </h1>
                  <p className="text-xs text-muted-foreground">
                    Seven short steps. Takes under 10 minutes end-to-end.
                  </p>
                </div>
              </div>
              <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary tabular-nums">
                {progressPct}% complete · {completed.size} / {ONBOARDING_STEPS.length}
              </span>
            </div>
            <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        </header>

        {/* Step rail + active step */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
          {/* Vertical rail (desktop) / horizontal pills (mobile) */}
          <ol
            className="flex gap-2 overflow-x-auto lg:col-span-1 lg:flex-col lg:overflow-visible"
            aria-label="Onboarding steps"
          >
            {ONBOARDING_STEPS.map((s, i) => {
              const isActive = i === active;
              const isDone = completed.has(i);
              const Sicon = s.icon;
              return (
                <li key={s.n} className="shrink-0 lg:shrink">
                  <button
                    type="button"
                    onClick={() => setActive(i)}
                    aria-current={isActive ? "step" : undefined}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition-colors",
                      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                      isActive
                        ? "border-primary/40 bg-primary/5 text-foreground"
                        : isDone
                          ? "border-emerald-500/20 bg-emerald-500/5 text-foreground"
                          : "border-border bg-card text-muted-foreground hover:bg-muted/30",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums",
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : isDone
                            ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                            : "bg-muted text-foreground",
                      )}
                    >
                      {isDone ? <CheckCircle2 className="h-4 w-4" /> : s.n}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 text-xs font-medium">
                        <Sicon className="h-3 w-3 shrink-0 opacity-60" aria-hidden />
                        <span className="truncate">{s.title}</span>
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ol>

          {/* Active step card */}
          <section
            aria-labelledby="active-step-heading"
            className="lg:col-span-3 space-y-4"
          >
            <div className="rounded-2xl border border-border bg-card shadow-sm">
              <div className="grid grid-cols-1 gap-0 lg:grid-cols-5">
                <div className="lg:col-span-3 p-6">
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-primary">
                    Step {step.n} of {ONBOARDING_STEPS.length}
                  </span>
                  <h2
                    id="active-step-heading"
                    className="mt-2 text-2xl font-semibold leading-tight text-foreground"
                  >
                    <span className="inline-flex items-center gap-2">
                      <StepIcon className="h-5 w-5 text-primary" aria-hidden />
                      {step.title}
                    </span>
                  </h2>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>

                  <ul className="mt-4 space-y-2">
                    {step.details.map((d, i) => (
                      <li key={i} className="flex gap-2 text-sm text-foreground">
                        <Circle
                          className="mt-1.5 h-1.5 w-1.5 shrink-0 fill-primary text-primary"
                          aria-hidden
                        />
                        <span>{d}</span>
                      </li>
                    ))}
                  </ul>

                  {step.cta && (
                    <Link
                      href={step.cta.href}
                      className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      {step.cta.label}
                      <ArrowRight className="h-3 w-3 opacity-80" />
                    </Link>
                  )}
                </div>
                <div className="lg:col-span-2 p-6 lg:border-l lg:border-border">
                  <div className="h-48 sm:h-56">
                    <Illustration kind={step.illustration} accent="--chart-3" />
                  </div>
                </div>
              </div>
              {/* Action bar */}
              <div className="flex items-center justify-between border-t border-border bg-muted/10 px-6 py-3">
                <button
                  type="button"
                  onClick={goPrev}
                  disabled={active === 0}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted/50 disabled:opacity-40"
                >
                  <ArrowLeft className="h-3 w-3" /> Back
                </button>
                <button
                  type="button"
                  onClick={goNext}
                  className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                >
                  {isLast ? (completed.has(active) ? "Done" : "Mark complete") : "Next step"}
                  <ArrowRight className="h-3 w-3 opacity-80" />
                </button>
              </div>
            </div>

            {/* Completion celebration */}
            {allDone && (
              <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-5">
                <div className="flex items-start gap-3">
                  <PartyPopper className="h-5 w-5 text-emerald-600 dark:text-emerald-400" aria-hidden />
                  <div className="flex-1">
                    <h3 className="text-sm font-semibold text-foreground">You finished the tour</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      You&rsquo;re ready to use Synthia in production workflows. Each feature has its own deep-dive
                      topic in the help center whenever you need a refresher.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Link
                        href="/"
                        className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                      >
                        Go to dashboard
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                      <Link
                        href="/help"
                        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted/50"
                      >
                        Browse all topics
                      </Link>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}
