"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle, Loader2, Play, X } from "lucide-react";

interface ConfirmGenerateDrawerProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  generating: boolean;

  // Summary fields rendered in the pre-flight panel.
  configName: string;
  connectionName: string;
  rowCount: number;
  engine: string;
  seed?: string;
  outputMode?: string;
  destinationLabel?: string;

  warning?: string;
}

/**
 * Tonic-style pre-flight summary that intercepts the Generate click.
 * Surfaces what's about to run (engine, row count, destination) so users
 * don't kick off a 1M-row job by accident. Mirrors screenshot 11.33.25.
 */
export function ConfirmGenerateDrawer({
  open,
  onCancel,
  onConfirm,
  generating,
  configName,
  connectionName,
  rowCount,
  engine,
  seed,
  outputMode = "same_database",
  destinationLabel,
  warning,
}: ConfirmGenerateDrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Trap focus + close on Escape (matches existing AccessibleDialog patterns).
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>("button, [tabindex]")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !generating) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open, generating, onCancel]);

  if (!open) return null;

  return (
    <>
      <div
        aria-hidden="true"
        className="fixed inset-0 z-40 bg-black/40"
        onClick={() => !generating && onCancel()}
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-generate-title"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 id="confirm-generate-title" className="text-sm font-semibold text-foreground">
            Confirm generation
          </h2>
          <button
            type="button"
            onClick={onCancel}
            disabled={generating}
            aria-label="Close confirm generation"
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4 text-sm">
          <p className="text-xs text-muted-foreground">
            Review the run before it kicks off. The job appears on the Jobs tab
            once started.
          </p>

          <dl className="mt-4 divide-y divide-border rounded-md border border-border">
            <Row label="Config name" value={configName || "(unnamed)"} />
            <Row label="Source connection" value={connectionName || "—"} />
            <Row label="Engine" value={engine} />
            <Row label="Row count" value={rowCount.toLocaleString()} />
            {seed && <Row label="Seed" value={seed} />}
            <Row label="Output mode" value={outputMode} />
            {destinationLabel && <Row label="Destination" value={destinationLabel} />}
          </dl>

          {warning && (
            <div className="mt-4 flex gap-2 rounded-md border border-amber-300/40 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{warning}</span>
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={generating}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={generating}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {generating ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Starting…
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                Confirm & generate
              </>
            )}
          </button>
        </footer>
      </aside>
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-3 gap-3 px-3 py-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="col-span-2 text-xs font-medium text-foreground">{value}</dd>
    </div>
  );
}
