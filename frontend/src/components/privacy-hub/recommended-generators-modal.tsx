"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Search,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";

export interface RecommendationGroup {
  pii_type: string;
  label: string;
  unprotected_columns: number;
  recommended_generator: string;
}

interface RecommendedGeneratorsModalProps {
  open: boolean;
  onClose: () => void;
  recommendations: RecommendationGroup[];
  /** Fired with the list of pii_types the user chose to apply (one entry
   * per Apply click or the full set on Apply All). The parent already
   * owns the apply-all backend call. */
  onApply: (piiTypes: string[]) => Promise<void>;
}

/**
 * Tonic-style Recommended Generators review modal (screenshots 11.30.07 /
 * 11.30.21). Bulk-apply UX scaled up from the inline Privacy Hub table:
 *
 *  - Search filters the group list by label or pii_type.
 *  - Each row carries `Ignore (N)` / `Apply X (N)` buttons so users can
 *    triage one PII type at a time.
 *  - Footer carries `Exit Review` + `Apply All (N)` for "trust the
 *    defaults" workflows.
 *
 * The actual rule creation is done by the parent's `applyTypes` helper
 * via the existing POST /privacy-hub/apply-all endpoint — this component
 * is pure UI.
 */
export function RecommendedGeneratorsModal({
  open,
  onClose,
  recommendations,
  onApply,
}: RecommendedGeneratorsModalProps) {
  const [query, setQuery] = useState("");
  const [ignored, setIgnored] = useState<Set<string>>(new Set());
  const [busyType, setBusyType] = useState<string | null>(null);
  const [bulk, setBulk] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return recommendations
      .filter((r) => !ignored.has(r.pii_type))
      .filter((r) =>
        q === ""
          ? true
          : r.label.toLowerCase().includes(q) || r.pii_type.toLowerCase().includes(q)
      );
  }, [recommendations, ignored, query]);

  const totalUnprotected = useMemo(
    () => filtered.reduce((sum, r) => sum + r.unprotected_columns, 0),
    [filtered]
  );

  if (!open) return null;

  const handleApplyOne = async (pii: string) => {
    setBusyType(pii);
    await onApply([pii]);
    setBusyType(null);
    // Remove the applied group from the active list so the count goes down.
    setIgnored((prev) => new Set(prev).add(pii));
  };

  const handleIgnore = (pii: string) => {
    setIgnored((prev) => new Set(prev).add(pii));
  };

  const handleApplyAll = async () => {
    if (filtered.length === 0) return;
    setBulk(true);
    await onApply(filtered.map((r) => r.pii_type));
    setBulk(false);
    onClose();
  };

  return (
    <>
      <div
        aria-hidden="true"
        className="fixed inset-0 z-[55] bg-black/50"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="rec-gens-title"
        className="fixed inset-x-0 top-[8%] z-[60] mx-auto flex w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
        style={{ maxHeight: "84vh" }}
      >
        <header className="flex items-start justify-between border-b border-border px-5 py-4">
          <div>
            <h2 id="rec-gens-title" className="text-base font-semibold text-foreground">
              Recommended generators by sensitivity type
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Review the suggested generator for each detected PII type before applying.
            </p>
          </div>
          <button
            type="button"
            aria-label="Close recommended generators"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="border-b border-border px-5 py-3">
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by PII type"
              aria-label="Filter recommendations"
              className="w-full rounded-md border border-input bg-background px-7 py-1.5 text-xs"
            />
          </div>
        </div>

        <ul className="flex-1 overflow-y-auto divide-y divide-border">
          {filtered.length === 0 ? (
            <li className="flex flex-col items-center gap-2 px-5 py-12 text-center text-xs text-muted-foreground">
              <CheckCircle2 className="h-5 w-5 text-[hsl(var(--dw-pill-success))]" />
              {recommendations.length === 0
                ? "Nothing to review — every sensitive column already has a generator."
                : "All visible groups were ignored. Clear the search or reopen the modal to start over."}
            </li>
          ) : (
            filtered.map((r) => (
              <li key={r.pii_type} className="px-5 py-3">
                <RecommendationRow
                  rec={r}
                  busy={busyType === r.pii_type}
                  onApply={() => handleApplyOne(r.pii_type)}
                  onIgnore={() => handleIgnore(r.pii_type)}
                />
              </li>
            ))
          )}
        </ul>

        <footer className="flex items-center justify-between gap-2 border-t border-border bg-muted/20 px-5 py-3">
          <p className="text-[11px] text-muted-foreground">
            <span className="font-semibold text-foreground">{totalUnprotected}</span> unprotected
            column{totalUnprotected === 1 ? "" : "s"} across{" "}
            <span className="font-semibold text-foreground">{filtered.length}</span> PII type
            {filtered.length === 1 ? "" : "s"}.
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Exit review
            </button>
            <button
              type="button"
              onClick={handleApplyAll}
              disabled={bulk || filtered.length === 0}
              className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90 disabled:opacity-50"
            >
              {bulk && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Apply all ({totalUnprotected})
            </button>
          </div>
        </footer>
      </div>
    </>
  );
}

function RecommendationRow({
  rec,
  busy,
  onApply,
  onIgnore,
}: {
  rec: RecommendationGroup;
  busy: boolean;
  onApply: () => void;
  onIgnore: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex items-start gap-3">
      <button
        type="button"
        aria-label={open ? "Collapse group" : "Expand group"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="mt-0.5 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
      </button>
      <span className="mt-0.5 inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-[hsl(var(--dw-pill-warning)/0.15)] px-2 text-xs font-semibold text-[hsl(var(--dw-pill-warning))]">
        {rec.unprotected_columns}
      </span>
      <div className="flex-1">
        <p className="text-sm font-medium text-foreground">{rec.label}</p>
        <p className="text-xs text-muted-foreground">
          Suggested generator:{" "}
          <code className="font-mono text-[11px] text-foreground">{rec.recommended_generator}</code>
        </p>
        {open && (
          <div className="mt-2 rounded-md border border-dashed border-border bg-muted/10 px-3 py-2 text-[11px] text-muted-foreground">
            <p className="flex items-center gap-1.5">
              <AlertTriangle className="h-3 w-3 text-[hsl(var(--dw-pill-warning))]" />
              Applying creates a masking rule on every unprotected column tagged{" "}
              <code className="font-mono text-foreground">{rec.pii_type}</code>. Existing rules
              are left untouched.
            </p>
          </div>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onIgnore}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          Ignore ({rec.unprotected_columns})
        </button>
        <button
          type="button"
          onClick={onApply}
          disabled={busy}
          className={cn(
            "inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          )}
        >
          {busy && <Loader2 className="h-3 w-3 animate-spin" />}
          Apply {rec.recommended_generator} ({rec.unprotected_columns})
        </button>
      </div>
    </div>
  );
}
