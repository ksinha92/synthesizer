"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { cn } from "@/lib/utils";

const DEFAULT_TEST_COLUMNS = `customer_email
ssn
date_of_birth
phone_number
billing_address
order_total
last_login
notes
patient_id`;

interface Rule {
  id: string;
  name: string;
  description: string;
  match_type: "column_name_regex" | "column_name_contains" | "value_regex" | string;
  pattern: string;
  suggested_pii_type: string;
  suggested_preset_id: string | null;
  priority: number;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

interface PresetSummary {
  id: string;
  name: string;
}

const MATCH_TYPES = [
  { value: "column_name_contains", label: "Column name contains" },
  { value: "column_name_regex", label: "Column name regex" },
  { value: "value_regex", label: "Value regex" },
] as const;

const PII_TYPES = [
  "email", "phone", "ssn", "person_name", "address", "credit_card",
  "ip_address", "date_of_birth", "financial_account", "medical_record", "other",
] as const;

interface Draft {
  id?: string;
  name: string;
  description: string;
  match_type: string;
  pattern: string;
  suggested_pii_type: string;
  suggested_preset_id: string;
  priority: number;
  enabled: boolean;
}

const EMPTY_DRAFT: Draft = {
  name: "",
  description: "",
  match_type: "column_name_contains",
  pattern: "",
  suggested_pii_type: "other",
  suggested_preset_id: "",
  priority: 100,
  enabled: true,
};

export default function SensitivityRulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [testInput, setTestInput] = useState(DEFAULT_TEST_COLUMNS);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [rs, ps] = await Promise.all([
        api.get<Rule[]>(`/api/v1/sensitivity-rules`),
        api.get<PresetSummary[]>(`/api/v1/generator-presets`),
      ]);
      setRules(rs);
      setPresets(ps);
    } catch {
      setRules([]);
      setPresets([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const openNew = () => setDraft({ ...EMPTY_DRAFT });
  const openEdit = (r: Rule) =>
    setDraft({
      id: r.id,
      name: r.name,
      description: r.description,
      match_type: r.match_type,
      pattern: r.pattern,
      suggested_pii_type: r.suggested_pii_type,
      suggested_preset_id: r.suggested_preset_id || "",
      priority: r.priority,
      enabled: r.enabled,
    });
  const closeDrawer = () => setDraft(null);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    const body = {
      name: draft.name,
      description: draft.description,
      match_type: draft.match_type,
      pattern: draft.pattern,
      suggested_pii_type: draft.suggested_pii_type,
      suggested_preset_id: draft.suggested_preset_id || null,
      priority: draft.priority,
      enabled: draft.enabled,
    };
    try {
      if (draft.id) {
        await api.put(`/api/v1/sensitivity-rules/${draft.id}`, body);
        toast.success("Rule updated");
      } else {
        await api.post(`/api/v1/sensitivity-rules`, body);
        toast.success("Rule created");
      }
      closeDrawer();
      await fetchAll();
    } catch {
      toast.error("Save failed — check pattern is valid regex.");
    }
    setSaving(false);
  };

  const remove = async (r: Rule) => {
    if (!confirm(`Delete rule ${r.name}?`)) return;
    try {
      await api.del(`/api/v1/sensitivity-rules/${r.id}`);
      toast.success("Rule deleted");
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
            <h1 className="text-2xl font-semibold text-foreground">Sensitivity Rules</h1>
            <p className="text-xs text-muted-foreground">
              Custom detectors. Rules are evaluated in priority order during discovery — the first match wins.
            </p>
          </div>
          <button
            onClick={openNew}
            className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90"
          >
            <Plus className="h-3.5 w-3.5" />
            New Rule
          </button>
        </div>

        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-2 font-medium">#</th>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Match</th>
                <th className="px-4 py-2 font-medium">Pattern</th>
                <th className="px-4 py-2 font-medium">Suggested PII</th>
                <th className="px-4 py-2 font-medium">Preset</th>
                <th className="px-4 py-2 font-medium">Enabled</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr><td colSpan={8} className="px-4 py-6 text-center text-xs text-muted-foreground">Loading…</td></tr>
              ) : rules.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-6 text-center text-xs text-muted-foreground">No rules yet. Click <strong>New Rule</strong>.</td></tr>
              ) : (
                rules.map((r, idx) => {
                  const presetName =
                    r.suggested_preset_id &&
                    presets.find((p) => p.id === r.suggested_preset_id)?.name;
                  return (
                    <tr key={r.id} className="hover:bg-muted/20">
                      <td className="px-4 py-2 tabular-nums text-xs text-muted-foreground">{idx + 1}</td>
                      <td className="px-4 py-2">
                        <p className="font-medium text-foreground">{r.name}</p>
                        {r.description && (
                          <p className="text-[11px] text-muted-foreground">{r.description}</p>
                        )}
                      </td>
                      <td className="px-4 py-2 text-xs">
                        {MATCH_TYPES.find((m) => m.value === r.match_type)?.label || r.match_type}
                      </td>
                      <td className="px-4 py-2 font-mono text-[11px] max-w-[200px] truncate text-foreground">
                        {r.pattern}
                      </td>
                      <td className="px-4 py-2 text-xs">{r.suggested_pii_type}</td>
                      <td className="px-4 py-2 text-xs text-muted-foreground">{presetName || "—"}</td>
                      <td className="px-4 py-2 text-xs">
                        {r.enabled ? (
                          <span className="rounded-full bg-[hsl(var(--dw-pill-success)/0.15)] px-2 py-0.5 text-[hsl(var(--dw-pill-success))]">
                            on
                          </span>
                        ) : (
                          <span className="text-muted-foreground">off</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <div className="inline-flex items-center gap-1">
                          <button onClick={() => openEdit(r)} aria-label="Edit rule" className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button onClick={() => remove(r)} aria-label="Delete rule" className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive">
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {draft !== null && (
          <>
            <div className="fixed inset-0 z-40 bg-black/40" onClick={closeDrawer} />
            <aside
              role="dialog"
              aria-modal="true"
              aria-label={draft.id ? "Edit rule" : "New rule"}
              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-3xl flex-col border-l border-border bg-card shadow-xl"
            >
              <div className="flex items-center justify-between border-b border-border px-5 py-3">
                <h2 className="text-sm font-semibold text-foreground">
                  {draft.id ? "Edit Rule" : "New Rule"}
                </h2>
                <button onClick={closeDrawer} aria-label="Close" className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Split: form on left, live test pane on right. Mirrors Tonic
                  11.27.06 — the rule author types a pattern and immediately
                  sees which discovered columns it would catch, without
                  committing the rule. */}
              <div className="flex flex-1 min-h-0 divide-x divide-border">
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

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1">Match Type</label>
                    <select
                      value={draft.match_type}
                      onChange={(e) => setDraft({ ...draft, match_type: e.target.value })}
                      className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                    >
                      {MATCH_TYPES.map((m) => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1">Priority</label>
                    <input
                      type="number"
                      value={draft.priority}
                      onChange={(e) => setDraft({ ...draft, priority: parseInt(e.target.value || "100", 10) })}
                      className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm tabular-nums"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-foreground mb-1">Pattern *</label>
                  <input
                    type="text"
                    value={draft.pattern}
                    onChange={(e) => setDraft({ ...draft, pattern: e.target.value })}
                    placeholder={draft.match_type === "column_name_contains" ? "e.g. ssn" : "e.g. ^[0-9]{3}-[0-9]{2}-[0-9]{4}$"}
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1">Suggested PII</label>
                    <select
                      value={draft.suggested_pii_type}
                      onChange={(e) => setDraft({ ...draft, suggested_pii_type: e.target.value })}
                      className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                    >
                      {PII_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1">Suggested Preset</label>
                    <select
                      value={draft.suggested_preset_id}
                      onChange={(e) => setDraft({ ...draft, suggested_preset_id: e.target.value })}
                      className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                    >
                      <option value="">— None —</option>
                      {presets.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
                  />
                  <span>Enabled</span>
                </label>
              </div>

              {/* Test Results pane */}
              <TestResultsPane
                matchType={draft.match_type}
                pattern={draft.pattern}
                testInput={testInput}
                onTestInputChange={setTestInput}
              />
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
                <button onClick={closeDrawer} className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted">
                  Cancel
                </button>
                <button
                  onClick={save}
                  disabled={saving || !draft.name.trim() || !draft.pattern.trim()}
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

// ── Test Results pane ──────────────────────────────────────────────────────
interface TestResultsPaneProps {
  matchType: string;
  pattern: string;
  testInput: string;
  onTestInputChange: (v: string) => void;
}

function TestResultsPane({ matchType, pattern, testInput, onTestInputChange }: TestResultsPaneProps) {
  const lines = useMemo(
    () => testInput.split("\n").map((l) => l.trim()).filter(Boolean),
    [testInput]
  );

  const { matches, regexError, isValueRegex } = useMemo(() => {
    const isValue = matchType === "value_regex";
    if (!pattern || lines.length === 0) {
      return { matches: new Set<string>(), regexError: null as string | null, isValueRegex: isValue };
    }
    if (matchType === "column_name_contains") {
      const needle = pattern.toLowerCase();
      const hit = new Set(lines.filter((l) => l.toLowerCase().includes(needle)));
      return { matches: hit, regexError: null, isValueRegex: isValue };
    }
    // Both column_name_regex and value_regex are tested against the lines
    // as regex; we don't have real column values to match against here, so
    // value_regex falls back to "treating the input as candidate values".
    try {
      const re = new RegExp(pattern);
      const hit = new Set(lines.filter((l) => re.test(l)));
      return { matches: hit, regexError: null, isValueRegex: isValue };
    } catch (e) {
      return {
        matches: new Set<string>(),
        regexError: e instanceof Error ? e.message : "Invalid regex",
        isValueRegex: isValue,
      };
    }
  }, [pattern, lines, matchType]);

  return (
    <aside className="w-80 shrink-0 flex flex-col bg-muted/20">
      <header className="border-b border-border px-4 py-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-foreground">
          Test results
        </h3>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {isValueRegex
            ? "Paste sample values (one per line) — entries that match this regex are flagged."
            : "Paste sample column names (one per line) — entries that match this rule are flagged."}
        </p>
      </header>

      <div className="px-4 pt-3">
        <label className="block text-[10px] font-medium uppercase tracking-wide text-muted-foreground mb-1">
          {isValueRegex ? "Candidate values" : "Candidate columns"}
        </label>
        <textarea
          value={testInput}
          onChange={(e) => onTestInputChange(e.target.value)}
          spellCheck={false}
          rows={5}
          className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs font-mono"
        />
      </div>

      <div className="flex items-center justify-between px-4 pt-2 text-[11px] text-muted-foreground">
        <span>
          {pattern.trim() === "" ? (
            "Enter a pattern above to test"
          ) : regexError ? (
            <span className="text-destructive">Invalid regex: {regexError}</span>
          ) : (
            <>
              <span className="font-semibold text-foreground">{matches.size}</span> of{" "}
              <span className="font-semibold text-foreground">{lines.length}</span> match
            </>
          )}
        </span>
      </div>

      <ul className="flex-1 overflow-y-auto px-4 pb-4 pt-2 space-y-1">
        {lines.map((l) => {
          const isMatch = matches.has(l);
          return (
            <li
              key={l}
              className={cn(
                "flex items-center gap-2 rounded-md border px-2 py-1.5 text-xs font-mono",
                isMatch
                  ? "border-[hsl(var(--dw-pill-warning)/0.4)] bg-[hsl(var(--dw-pill-warning)/0.1)] text-[hsl(var(--dw-pill-warning))]"
                  : "border-transparent text-muted-foreground"
              )}
            >
              {isMatch ? (
                <AlertCircle className="h-3 w-3 shrink-0" aria-label="match" />
              ) : (
                <CheckCircle2 className="h-3 w-3 shrink-0 opacity-40" aria-label="no match" />
              )}
              <span className="truncate">{l}</span>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
