"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, X } from "lucide-react";

import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

import { EvidenceChip } from "./evidence-chip";
import type {
  RelationshipSuggestion,
  SuggestRelationshipsResponse,
} from "../types";

interface SuggestRelationshipsModalProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
  /** Notified with the user's accepted set when they hit "Save accepted". */
  onAccepted?: (accepted: RelationshipSuggestion[]) => void;
}

/**
 * The auto-mapper. Pulls ranked cross-file FK candidates from the
 * suggester endpoint and lets the user accept/reject each one, with a
 * confidence-threshold slider so the noisy tail can be hidden.
 *
 * Accepted suggestions are returned via ``onAccepted`` — the caller is
 * responsible for persisting them into the project's FileSetDefinition
 * (out of scope for the suggester itself).
 */
export function SuggestRelationshipsModal({
  projectId,
  open,
  onClose,
  onAccepted,
}: SuggestRelationshipsModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SuggestRelationshipsResponse | null>(null);
  const [threshold, setThreshold] = useState(0.6);
  const [accepted, setAccepted] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get<SuggestRelationshipsResponse>(
          `/api/v1/projects/${projectId}/file-schemas/suggest-relationships?min_score=0.4`,
        );
        if (!cancelled) {
          setData(res);
          setAccepted(new Set());
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message || "Failed to load suggestions");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, projectId]);

  const filtered = useMemo<RelationshipSuggestion[]>(
    () => data?.suggestions.filter((s) => s.score >= threshold) ?? [],
    [data, threshold],
  );

  const idFor = (s: RelationshipSuggestion) =>
    `${s.source_file}.${s.source_field}→${s.target_file}.${s.target_field}`;

  const toggle = (s: RelationshipSuggestion, on: boolean) => {
    setAccepted((prev) => {
      const next = new Set(prev);
      if (on) next.add(idFor(s));
      else next.delete(idFor(s));
      return next;
    });
  };

  const bulkAcceptAboveThreshold = () => {
    setAccepted(new Set(filtered.map(idFor)));
  };

  const save = () => {
    if (!data) return;
    const picks = data.suggestions.filter((s) => accepted.has(idFor(s)));
    onAccepted?.(picks);
    toast.success(
      `Accepted ${picks.length} relationship${picks.length === 1 ? "" : "s"}`,
    );
    onClose();
  };

  return (
    <AccessibleDialog
      open={open}
      onClose={onClose}
      titleId="suggest-relationships-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="relative w-full max-w-4xl rounded-lg border border-border bg-card shadow-xl">
        <header className="flex items-baseline justify-between border-b border-border px-6 py-4">
          <div>
            <h2
              id="suggest-relationships-title"
              className="text-lg font-semibold text-foreground"
            >
              Suggested file relationships
            </h2>
            <p className="text-xs text-muted-foreground">
              Heuristic blend of name similarity, type compatibility, and value
              overlap (when sample data is loaded).
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted/40 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-3 px-6 py-4">
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-2">
              Confidence threshold
              <input
                type="range"
                min={0.4}
                max={1}
                step={0.05}
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
              />
              <span className="font-mono">{threshold.toFixed(2)}</span>
            </label>
            <button
              type="button"
              onClick={bulkAcceptAboveThreshold}
              className="ml-auto rounded-md border border-input bg-background px-2 py-1 hover:bg-muted/40"
            >
              Accept all above threshold
            </button>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Scoring pairs…
            </div>
          ) : error ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </p>
          ) : (
            <div className="max-h-[420px] overflow-auto rounded-md border border-border">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-muted/30">
                  <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                    <th className="w-8 px-2 py-1.5" />
                    <th className="px-2 py-1.5 font-medium">Source</th>
                    <th className="px-2 py-1.5 font-medium">Target</th>
                    <th className="px-2 py-1.5 font-medium">Score</th>
                    <th className="px-2 py-1.5 font-medium">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((s) => {
                    const id = idFor(s);
                    return (
                      <tr key={id} className="border-t border-border">
                        <td className="px-2 py-1">
                          <input
                            type="checkbox"
                            aria-label={`Accept ${id}`}
                            checked={accepted.has(id)}
                            onChange={(e) => toggle(s, e.target.checked)}
                          />
                        </td>
                        <td className="px-2 py-1 font-mono text-foreground">
                          {s.source_file}.<span className="font-bold">{s.source_field}</span>
                        </td>
                        <td className="px-2 py-1 font-mono text-foreground">
                          {s.target_file}.<span className="font-bold">{s.target_field}</span>
                        </td>
                        <td className="px-2 py-1 font-mono text-foreground">
                          {(s.score * 100).toFixed(0)}%
                        </td>
                        <td className="px-2 py-1">
                          <div className="flex flex-wrap items-center gap-1">
                            <EvidenceChip
                              label="name"
                              value={`${Math.round(s.evidence.name_similarity * 100)}%`}
                              tone={s.evidence.name_similarity >= 0.8 ? "good" : "neutral"}
                              title="Normalized identifier similarity"
                            />
                            <EvidenceChip
                              label="type"
                              value={`${Math.round(s.evidence.type_compatibility * 100)}%`}
                              tone={s.evidence.type_compatibility >= 0.8 ? "good" : "warn"}
                              title="Data type + length compatibility"
                            />
                            {s.evidence.value_overlap !== null && (
                              <EvidenceChip
                                label="overlap"
                                value={`${Math.round(s.evidence.value_overlap * 100)}%`}
                                tone={s.evidence.value_overlap >= 0.7 ? "good" : "warn"}
                                title={`Sample value overlap (n=${s.sample_size})`}
                              />
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                        No suggestions above the threshold.
                        {data && data.schemas_considered < 2
                          ? " Add at least two file schemas to enable suggestions."
                          : null}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <footer className="flex justify-end gap-2 border-t border-border px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-xs hover:bg-muted/40"
          >
            Close
          </button>
          <button
            type="button"
            onClick={save}
            disabled={accepted.size === 0}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            <Check className="h-3 w-3" />
            Save {accepted.size} accepted
          </button>
        </footer>
      </div>
    </AccessibleDialog>
  );
}
