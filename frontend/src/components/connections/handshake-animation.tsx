"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface HandshakeAnimationProps {
  port: number;
  dbLabel: string;
}

interface Stage {
  label: string;
  detail: string;
}

/** Animated multi-stage handshake. Cycles through DNS → TCP → auth → catalog
 *  probe → ready, with each stage briefly "running" before flipping to "done".
 *  Pure visual storytelling — no real network calls. */
export function HandshakeAnimation({ port, dbLabel }: HandshakeAnimationProps) {
  const stages: Stage[] = [
    { label: "DNS resolve", detail: "Resolving hostname" },
    { label: `TCP :${port}`, detail: "Opening connection" },
    { label: "Authenticate", detail: "Sending credentials" },
    { label: "Probe catalog", detail: `Verifying ${dbLabel} schema access` },
    { label: "Ready", detail: "Connection saved" },
  ];

  const [active, setActive] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setActive((a) => (a + 1) % (stages.length + 2));
    }, 900);
    return () => window.clearInterval(id);
    // We re-create the interval when the port/label changes — stages depends on them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, dbLabel]);

  return (
    <div className="relative h-full overflow-hidden rounded-xl border border-border bg-background">
      {/* Pulsing gradient backdrop */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(circle at 30% 30%, hsl(var(--chart-2) / 0.20), transparent 55%), radial-gradient(circle at 80% 80%, hsl(var(--chart-3) / 0.16), transparent 55%)",
        }}
      />
      <ol
        className="relative flex h-full flex-col justify-between px-4 py-3"
        aria-label="Connection handshake stages"
      >
        {stages.map((s, i) => {
          const state: "pending" | "running" | "done" =
            i < active ? "done" : i === active ? "running" : "pending";
          return (
            <li key={s.label} className="flex items-center gap-3">
              <StageDot state={state} />
              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    "text-[11px] font-medium leading-tight transition-colors",
                    state === "done"
                      ? "text-foreground"
                      : state === "running"
                        ? "text-foreground"
                        : "text-muted-foreground",
                  )}
                >
                  {s.label}
                </p>
                <p
                  className={cn(
                    "text-[10px] transition-colors",
                    state === "running" ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  {s.detail}
                </p>
              </div>
              {state === "running" && (
                <Loader2 className="h-3 w-3 animate-spin text-primary" aria-hidden />
              )}
              {state === "done" && (
                <Check className="h-3 w-3 text-emerald-500" aria-hidden />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StageDot({ state }: { state: "pending" | "running" | "done" }) {
  if (state === "done") {
    return <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden />;
  }
  if (state === "running") {
    return (
      <span className="relative inline-flex h-2 w-2 shrink-0" aria-hidden>
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
      </span>
    );
  }
  return <span className="h-2 w-2 shrink-0 rounded-full bg-foreground/20" aria-hidden />;
}
