"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, Package, Plus, Trash2 } from "lucide-react";

import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

import { EvidenceChip } from "@/components/file-loader/relationships/evidence-chip";
import type {
  RelationshipSuggestion,
  SuggestRelationshipsResponse,
} from "@/components/file-loader/types";

interface AcceptedFk {
  source_file: string;
  source_field: string;
  target_file: string;
  target_field: string;
}

const STORAGE_PREFIX = "files-accepted-fks::";

/**
 * Files → Relationships — full-page version of the auto-mapper. Suggestions
 * are scored server-side; user-accepted edges are kept in localStorage so the
 * Output tab can hydrate them into the FileSetDefinition it sends to the
 * generation worker. Persisting on the server (as part of a project-scoped
 * FileSetDefinition aggregate) is the natural next step but out of scope
 * for this IA migration.
 */
export default function FilesRelationshipsPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SuggestRelationshipsResponse | null>(null);
  const [threshold, setThreshold] = useState(0.6);
  const [accepted, setAccepted] = useState<AcceptedFk[]>([]);

  // Hydrate accepted edges from localStorage (per-project).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_PREFIX + projectId);
    if (raw) {
      try {
        setAccepted(JSON.parse(raw) as AcceptedFk[]);
      } catch {
        // ignore corrupted state
      }
    }
  }, [projectId]);

  // Persist on change so the Output tab can read the same key.
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_PREFIX + projectId, JSON.stringify(accepted));
  }, [accepted, projectId]);

  const fetchSuggestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<SuggestRelationshipsResponse>(
        `/api/v1/projects/${projectId}/file-schemas/suggest-relationships?min_score=0.4`,
      );
      setData(res);
    } catch (e) {
      setError((e as Error).message || "Failed to fetch suggestions");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void fetchSuggestions();
  }, [fetchSuggestions]);

  const filtered = useMemo<RelationshipSuggestion[]>(
    () => data?.suggestions.filter((s) => s.score >= threshold) ?? [],
    [data, threshold],
  );

  const acceptedSet = useMemo(
    () =>
      new Set(
        accepted.map(
          (a) => `${a.source_file}.${a.source_field}→${a.target_file}.${a.target_field}`,
        ),
      ),
    [accepted],
  );

  const toggle = (s: RelationshipSuggestion, on: boolean) => {
    const key = `${s.source_file}.${s.source_field}→${s.target_file}.${s.target_field}`;
    if (on) {
      setAccepted((prev) => [
        ...prev.filter(
          (p) =>
            `${p.source_file}.${p.source_field}→${p.target_file}.${p.target_field}` !== key,
        ),
        {
          source_file: s.source_file,
          source_field: s.source_field,
          target_file: s.target_file,
          target_field: s.target_field,
        },
      ]);
    } else {
      setAccepted((prev) =>
        prev.filter(
          (p) =>
            `${p.source_file}.${p.source_field}→${p.target_file}.${p.target_field}` !== key,
        ),
      );
    }
  };

  const removeAccepted = (a: AcceptedFk) =>
    toggle(
      {
        source_file: a.source_file,
        source_field: a.source_field,
        target_file: a.target_file,
        target_field: a.target_field,
        score: 0,
        evidence: {
          name_similarity: 0,
          type_compatibility: 0,
          cardinality_match: false,
          value_overlap: null,
        },
        sample_size: 0,
      },
      false,
    );

  const bulkAccept = () => {
    const merged = new Map(
      accepted.map((a) => [
        `${a.source_file}.${a.source_field}→${a.target_file}.${a.target_field}`,
        a,
      ]),
    );
    for (const s of filtered) {
      const key = `${s.source_file}.${s.source_field}→${s.target_file}.${s.target_field}`;
      merged.set(key, {
        source_file: s.source_file,
        source_field: s.source_field,
        target_file: s.target_file,
        target_field: s.target_field,
      });
    }
    setAccepted(Array.from(merged.values()));
    toast.success(`Accepted ${filtered.length} above threshold`);
  };

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <p className="text-xs text-muted-foreground">
          Heuristic blend of name similarity + type compatibility + value overlap
          (when sample data exists). Accepted relationships flow into the Output
          tab&apos;s file-set generation.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-foreground">Accepted relationships</h2>
        {accepted.length === 0 ? (
          <p className="text-xs text-muted-foreground">None yet.</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {accepted.map((a, i) => (
              <li key={i} className="flex items-center gap-2 rounded border border-border bg-card px-2 py-1 font-mono">
                <span>{a.source_file}.{a.source_field}</span>
                <span>→</span>
                <span>{a.target_file}.{a.target_field}</span>
                <button
                  type="button"
                  onClick={() => removeAccepted(a)}
                  className="ml-auto text-muted-foreground hover:text-destructive"
                  aria-label="Remove"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <h2 className="text-sm font-semibold text-foreground">Suggestions</h2>
          <label className="flex items-center gap-2">
            <span className="text-muted-foreground">Threshold</span>
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
            onClick={bulkAccept}
            disabled={filtered.length === 0}
            className="ml-auto inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 hover:bg-muted/40 disabled:opacity-50"
          >
            <Plus className="h-3 w-3" /> Accept all above threshold
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
          <div className="overflow-hidden rounded-md border border-border">
            <table className="w-full text-xs">
              <thead className="bg-muted/30 text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="w-8 px-2 py-1.5" />
                  <th className="px-2 py-1.5 font-medium">Source</th>
                  <th className="px-2 py-1.5 font-medium">Target</th>
                  <th className="px-2 py-1.5 font-medium">Score</th>
                  <th className="px-2 py-1.5 font-medium">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => {
                  const id = `${s.source_file}.${s.source_field}→${s.target_file}.${s.target_field}`;
                  return (
                    <tr key={id} className="border-t border-border">
                      <td className="px-2 py-1">
                        <input
                          type="checkbox"
                          aria-label={`Accept ${id}`}
                          checked={acceptedSet.has(id)}
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
                          />
                          <EvidenceChip
                            label="type"
                            value={`${Math.round(s.evidence.type_compatibility * 100)}%`}
                            tone={s.evidence.type_compatibility >= 0.8 ? "good" : "warn"}
                          />
                          {s.evidence.value_overlap !== null && (
                            <EvidenceChip
                              label="overlap"
                              value={`${Math.round(s.evidence.value_overlap * 100)}%`}
                              tone={s.evidence.value_overlap >= 0.7 ? "good" : "warn"}
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
                      {data && data.schemas_considered < 2
                        ? "Need at least two file schemas to score suggestions."
                        : "No suggestions above the threshold."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-[11px] text-muted-foreground">
          <Package className="mr-1 inline h-3 w-3" /> Accepted relationships are
          stored locally per project and hydrated into the Output tab when you
          launch a file-set generation.
        </p>
      </section>
    </div>
  );
}
