"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { cn } from "@/lib/utils";

interface Preset {
  id: string;
  name: string;
  description: string;
  generator_type: string;
  config: Record<string, unknown>;
  consistency: boolean;
  occurrences: number;
  created_at: string | null;
  updated_at: string | null;
}

const GENERATOR_TYPES = [
  "hash",
  "redact",
  "faker_replace",
  "shuffle",
  "nullify",
  "fpe",
  "passthrough",
] as const;

interface DraftPreset {
  id?: string;
  name: string;
  description: string;
  generator_type: string;
  config: string; // JSON text in the form
  consistency: boolean;
  occurrences?: number; // count of masking rules currently using this preset
}

const EMPTY_DRAFT: DraftPreset = {
  name: "",
  description: "",
  generator_type: "faker_replace",
  config: "{}",
  consistency: false,
};

export default function GeneratorPresetsPage() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState<DraftPreset | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const list = await api.get<Preset[]>(`/api/v1/generator-presets`);
      setPresets(list);
    } catch {
      setPresets([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const openNew = () => setDraft({ ...EMPTY_DRAFT });

  const openEdit = (p: Preset) =>
    setDraft({
      id: p.id,
      name: p.name,
      description: p.description,
      generator_type: p.generator_type,
      config: JSON.stringify(p.config, null, 2),
      consistency: p.consistency,
      occurrences: p.occurrences,
    });

  const closeDrawer = () => setDraft(null);

  const save = async () => {
    if (!draft) return;
    let parsedConfig: Record<string, unknown>;
    try {
      parsedConfig = draft.config.trim() ? JSON.parse(draft.config) : {};
    } catch {
      toast.error("Config must be valid JSON.");
      return;
    }
    setSaving(true);
    try {
      const body = {
        name: draft.name,
        description: draft.description,
        generator_type: draft.generator_type,
        config: parsedConfig,
        consistency: draft.consistency,
      };
      if (draft.id) {
        await api.put(`/api/v1/generator-presets/${draft.id}`, body);
        toast.success("Preset updated");
      } else {
        await api.post(`/api/v1/generator-presets`, body);
        toast.success("Preset created");
      }
      closeDrawer();
      await fetchAll();
    } catch {
      toast.error("Save failed.");
    }
    setSaving(false);
  };

  const remove = async (p: Preset) => {
    if (!confirm(`Delete preset ${p.name}? Existing rules will become unlinked.`)) return;
    try {
      await api.del(`/api/v1/generator-presets/${p.id}`);
      toast.success("Preset deleted");
      await fetchAll();
    } catch {
      toast.error("Delete failed.");
    }
  };

  return (
    <AppShell>
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Generator Presets</h1>
          <p className="text-xs text-muted-foreground">
            Reusable, named generator configurations shared across all projects.
          </p>
        </div>
        <button
          onClick={openNew}
          className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90"
        >
          <Plus className="h-3.5 w-3.5" />
          New Preset
        </button>
      </div>

      <GeneratorTypeOverview presetCountByType={countPresetsByType(presets)} />

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr className="text-left text-xs text-muted-foreground">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Generator</th>
              <th className="px-4 py-2 font-medium">Consistency</th>
              <th className="px-4 py-2 font-medium text-right">Occurrences</th>
              <th className="px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-xs text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : presets.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-xs text-muted-foreground">
                  No presets yet. Click <strong>New Preset</strong> to create one.
                </td>
              </tr>
            ) : (
              presets.map((p) => (
                <tr key={p.id} className="hover:bg-muted/20">
                  <td className="px-4 py-2">
                    <p className="font-medium text-foreground">{p.name}</p>
                    {p.description && (
                      <p className="text-[11px] text-muted-foreground">{p.description}</p>
                    )}
                  </td>
                  <td className="px-4 py-2 font-mono text-[11px]">{p.generator_type}</td>
                  <td className="px-4 py-2 text-xs">
                    {p.consistency ? (
                      <span className="rounded-full bg-[hsl(var(--dw-pill-success)/0.15)] px-2 py-0.5 text-[hsl(var(--dw-pill-success))]">
                        on
                      </span>
                    ) : (
                      <span className="text-muted-foreground">off</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {p.occurrences > 0 ? (
                      <span
                        className="inline-flex items-center rounded-full bg-[hsl(var(--dw-pill-success)/0.15)] px-2 py-0.5 text-[11px] font-medium text-[hsl(var(--dw-pill-success))] tabular-nums"
                        title={`${p.occurrences} masking rule${p.occurrences === 1 ? "" : "s"} using this preset`}
                      >
                        {p.occurrences} in use
                      </span>
                    ) : (
                      <span className="text-[11px] text-muted-foreground">unused</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button
                        onClick={() => openEdit(p)}
                        aria-label="Edit preset"
                        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => remove(p)}
                        aria-label="Delete preset"
                        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Side drawer */}
      {draft !== null && (
        <>
          <div className="fixed inset-0 z-40 bg-black/40" onClick={closeDrawer} />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label={draft.id ? "Edit preset" : "Create preset"}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold text-foreground">
                {draft.id ? "Edit Preset" : "New Preset"}
              </h2>
              <button
                onClick={closeDrawer}
                aria-label="Close"
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Retroactive-change warning (Tonic 11.28.37). Saved changes flow
                back to every masking rule that points at this preset, so we
                surface the blast radius before the user clicks Save. */}
            {draft.id && draft.occurrences != null && draft.occurrences > 0 && (
              <div className="border-b border-amber-300/40 bg-amber-50 px-5 py-3 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <p>
                    <span className="font-semibold">{draft.occurrences}</span>{" "}
                    masking rule{draft.occurrences === 1 ? "" : "s"} currently
                    use this preset. Saving will re-apply your changes to{" "}
                    {draft.occurrences === 1 ? "it" : "all of them"} the next
                    time generation runs.
                  </p>
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Name *</label>
                <input
                  type="text"
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Description</label>
                <textarea
                  value={draft.description}
                  onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                  rows={2}
                  className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-foreground mb-1">Generator Type</label>
                <select
                  value={draft.generator_type}
                  onChange={(e) => setDraft({ ...draft, generator_type: e.target.value })}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                >
                  {GENERATOR_TYPES.map((g) => (
                    <option key={g} value={g}>{g}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-foreground mb-1">
                  Config <span className="text-muted-foreground">(JSON)</span>
                </label>
                <textarea
                  value={draft.config}
                  onChange={(e) => setDraft({ ...draft, config: e.target.value })}
                  rows={6}
                  className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono"
                />
              </div>

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={draft.consistency}
                  onChange={(e) => setDraft({ ...draft, consistency: e.target.checked })}
                />
                <span>Consistency — same input always produces the same output</span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
              <button
                onClick={closeDrawer}
                className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={save}
                disabled={saving || !draft.name.trim()}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow",
                  "hover:opacity-90 disabled:opacity-50"
                )}
              >
                {saving && <Loader2 className="h-3 w-3 animate-spin" />}
                Save and Apply
              </button>
            </div>
          </aside>
        </>
      )}
    </div>
    </AppShell>
  );
}

// ── Generator type overview (T3.4, Tonic 11.27.48) ─────────────────────────
function countPresetsByType(presets: Preset[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const p of presets) {
    m.set(p.generator_type, (m.get(p.generator_type) ?? 0) + 1);
  }
  return m;
}

interface GeneratorMeta {
  type: string;
  label: string;
  family: "Identity" | "Privacy" | "Format" | "Pass-through";
  description: string;
}

const GENERATOR_META: GeneratorMeta[] = [
  { type: "faker_replace", label: "Faker", family: "Identity", description: "Realistic synthetic names, addresses, dates, etc." },
  { type: "hash", label: "Hash", family: "Privacy", description: "Deterministic HMAC-SHA256 — same input → same output." },
  { type: "redact", label: "Redact", family: "Privacy", description: "Whole-value X-out for any data type." },
  { type: "nullify", label: "Nullify", family: "Privacy", description: "Drop the value to NULL." },
  { type: "fpe", label: "FPE", family: "Format", description: "Format-preserving encryption — same length + alphabet." },
  { type: "partial_mask", label: "Partial", family: "Format", description: "Reveal first/last N chars, mask the middle." },
  { type: "shuffle", label: "Shuffle", family: "Privacy", description: "Random permutation across the column." },
  { type: "presidio_redact", label: "Free-text", family: "Privacy", description: "Redact PII spans (PERSON / EMAIL / SSN…) in narrative text." },
  { type: "passthrough", label: "Passthrough", family: "Pass-through", description: "Leave the value untouched. Useful for non-PII columns." },
];

const FAMILY_ORDER: GeneratorMeta["family"][] = ["Privacy", "Identity", "Format", "Pass-through"];

function GeneratorTypeOverview({ presetCountByType }: { presetCountByType: Map<string, number> }) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="border-b border-border px-5 py-3">
        <h2 className="text-sm font-semibold text-foreground">Available generators</h2>
        <p className="text-xs text-muted-foreground">
          Pick a starting point — every preset above wraps one of these generators with
          your own configuration.
        </p>
      </header>
      <div className="px-5 py-4 space-y-4">
        {FAMILY_ORDER.map((family) => {
          const items = GENERATOR_META.filter((g) => g.family === family);
          return (
            <div key={family}>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {family}
              </p>
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((g) => {
                  const count = presetCountByType.get(g.type) ?? 0;
                  return (
                    <li
                      key={g.type}
                      className="rounded-md border border-border bg-muted/10 px-3 py-2"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="text-xs font-semibold text-foreground">{g.label}</p>
                        {count > 0 ? (
                          <span className="rounded-full bg-[hsl(var(--dw-pill-success)/0.15)] px-1.5 py-0.5 text-[10px] font-medium text-[hsl(var(--dw-pill-success))] tabular-nums">
                            {count} preset{count === 1 ? "" : "s"}
                          </span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">no presets</span>
                        )}
                      </div>
                      <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                        {g.description}
                      </p>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        {g.type}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
