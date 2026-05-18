"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Check, Edit3, Eye, Loader2, Plus, Sparkles, Trash2, X } from "lucide-react";
import { MaskingPolicyList } from "@/components/masking/masking-policy-list";
import { MaskingRuleEditor } from "@/components/masking/masking-rule-editor";
import { MaskingPreview } from "@/components/masking/masking-preview";
import { useMaskingStore } from "@/stores/masking-store";
import { useConnectionStore } from "@/stores/connection-store";
import { toast } from "@/components/common/toast";

const MASKING_TYPES = ["redact", "hash", "tokenize", "format_preserving", "faker_replace", "shuffle", "nullify"];

export default function MaskingPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [showCreate, setShowCreate] = useState(false);
  const [policyName, setPolicyName] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState("redact");
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [appliedRules, setAppliedRules] = useState<Set<string>>(new Set());
  const [editingRule, setEditingRule] = useState<{ id: string; masking_type: string; preserve_format: boolean; deterministic: boolean } | null>(null);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [previewing, setPreviewing] = useState(false);
  // Phase 58 F7-UI: cross-column consistency metadata for the next rule
  // applied via the rule editor. Kept page-level so the editor stays
  // controlled and Apply/Apply-All can pass the same extras through.
  const [consistencyGroup, setConsistencyGroup] = useState<string>("");
  const [linkedColumnIds, setLinkedColumnIds] = useState<string[]>([]);
  const { policies, fetchPolicies, createPolicy, suggestions, autoSuggest, addRule, updateRule, deleteRule, previewData, previewMasking } = useMaskingStore();
  const { connections, fetchConnections } = useConnectionStore();

  useEffect(() => { fetchPolicies(projectId); }, [projectId, fetchPolicies]);
  useEffect(() => { fetchConnections(projectId); }, [projectId, fetchConnections]);

  // Auto-select first connection so Preview has a default target.
  useEffect(() => {
    if (!selectedConnectionId && connections.length > 0) {
      setSelectedConnectionId(connections[0].id);
    }
  }, [connections, selectedConnectionId]);

  const handlePreview = async () => {
    const policy = policies.find((p) => p.id === selectedPolicyId);
    if (!policy) {
      toast.error("Select a policy to preview");
      return;
    }
    if (!selectedConnectionId) {
      toast.error("Select a connection to preview against");
      return;
    }
    setPreviewing(true);
    try {
      await previewMasking(projectId, policy.id, selectedConnectionId);
    } finally {
      setPreviewing(false);
    }
  };

  // Auto-select first policy
  useEffect(() => {
    if (!selectedPolicyId && policies.length > 0) {
      setSelectedPolicyId(policies[0].id);
    }
  }, [policies, selectedPolicyId]);

  const handleCreate = async () => {
    if (!policyName.trim()) return;
    const policy = await createPolicy(projectId, policyName.trim());
    if (policy) setSelectedPolicyId(policy.id);
    setPolicyName("");
    setShowCreate(false);
    fetchPolicies(projectId);
  };

  const handleApplyRule = async (columnId: string, strategy: string) => {
    if (!selectedPolicyId) return;
    const extras = {
      linkedColumnIds: linkedColumnIds.length > 0 ? linkedColumnIds : undefined,
      consistencyGroup: consistencyGroup.trim() ? consistencyGroup.trim() : undefined,
    };
    const ok = await addRule(projectId, selectedPolicyId, columnId, strategy, extras);
    if (ok) {
      setAppliedRules((prev) => new Set([...Array.from(prev), columnId]));
    }
  };

  const handleApplyAll = async () => {
    if (!selectedPolicyId) return;
    for (const s of suggestions) {
      if (!appliedRules.has(s.column_id)) {
        await handleApplyRule(s.column_id, s.suggested_strategy);
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Data Masking</h1>
        <div className="flex gap-2">
          <button onClick={() => autoSuggest(projectId, "")} className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted">
            <Sparkles className="h-4 w-4" /> Auto-suggest from PII
          </button>
          <button onClick={() => setShowCreate(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <Plus className="h-4 w-4" /> Add Policy
          </button>
        </div>
      </div>

      {/* Policy selector + preview controls */}
      {policies.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs font-medium text-muted-foreground">Active Policy:</label>
          <select
            value={selectedPolicyId || ""}
            onChange={(e) => setSelectedPolicyId(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground"
          >
            {policies.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          {connections.length > 0 && (
            <>
              <label className="ml-2 text-xs font-medium text-muted-foreground">Preview against:</label>
              <select
                value={selectedConnectionId}
                onChange={(e) => setSelectedConnectionId(e.target.value)}
                className="rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground"
              >
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </>
          )}
          <button
            onClick={handlePreview}
            disabled={previewing || !selectedPolicyId || !selectedConnectionId}
            className="ml-auto inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            {previewing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eye className="h-3.5 w-3.5" />}
            {previewing ? "Previewing…" : "Preview Masking"}
          </button>
        </div>
      )}

      {/* Auto-suggest results */}
      {suggestions.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-foreground">Suggested Rules from PII Detection</h3>
            {selectedPolicyId && (
              <button onClick={handleApplyAll} className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90">
                <Check className="h-3 w-3" /> Apply All to Policy
              </button>
            )}
          </div>
          <div className="space-y-1.5">
            {suggestions.map((s, i) => {
              const isApplied = appliedRules.has(s.column_id);
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-foreground w-32 truncate">{s.column_name}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">{s.pii_type}</span>
                  <span className="text-primary font-medium">→ {s.suggested_strategy}</span>
                  <span className="text-muted-foreground">{Math.round(s.confidence * 100)}%</span>
                  {s.warning && <span className="text-xs text-warning">⚠ {s.warning}</span>}
                  <div className="ml-auto">
                    {isApplied ? (
                      <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
                        <Check className="h-3 w-3" /> Applied
                      </span>
                    ) : selectedPolicyId ? (
                      <button
                        onClick={() => handleApplyRule(s.column_id, s.suggested_strategy)}
                        className="rounded-md border border-border px-2 py-0.5 text-xs hover:bg-muted"
                      >
                        Apply
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {showCreate && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <input type="text" value={policyName} onChange={e => setPolicyName(e.target.value)} placeholder="Policy name..." className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" autoFocus />
          <div className="flex gap-2">
            <button onClick={handleCreate} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">Create</button>
            <button onClick={() => setShowCreate(false)} className="text-sm text-muted-foreground">Cancel</button>
          </div>
        </div>
      )}

      {/* Applied rules with edit/delete */}
      {selectedPolicyId && appliedRules.size > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-medium text-foreground mb-3">Applied Rules</h3>
          <div className="space-y-2">
            {Array.from(appliedRules).map((columnId) => {
              const suggestion = suggestions.find((s) => s.column_id === columnId);
              if (!suggestion) return null;
              const isEditing = editingRule?.id === columnId;
              return (
                <div key={columnId} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs">
                  <span className="font-mono text-foreground w-28 truncate">{suggestion.column_name}</span>
                  {isEditing ? (
                    <>
                      <select
                        value={editingRule.masking_type}
                        onChange={(e) => setEditingRule({ ...editingRule, masking_type: e.target.value })}
                        className="rounded border border-input bg-background px-2 py-1 text-xs"
                      >
                        {MASKING_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                      <label className="flex items-center gap-1 text-muted-foreground">
                        <input type="checkbox" checked={editingRule.preserve_format} onChange={(e) => setEditingRule({ ...editingRule, preserve_format: e.target.checked })} className="rounded" />
                        Preserve
                      </label>
                      <label className="flex items-center gap-1 text-muted-foreground">
                        <input type="checkbox" checked={editingRule.deterministic} onChange={(e) => setEditingRule({ ...editingRule, deterministic: e.target.checked })} className="rounded" />
                        Deterministic
                      </label>
                      <button
                        onClick={async () => {
                          if (!selectedPolicyId) return;
                          await updateRule(projectId, selectedPolicyId, columnId, {
                            masking_type: editingRule.masking_type,
                            preserve_format: editingRule.preserve_format,
                            deterministic: editingRule.deterministic,
                          });
                          setEditingRule(null);
                        }}
                        className="ml-auto rounded bg-primary px-2 py-1 text-primary-foreground hover:bg-primary/90"
                      >
                        Save
                      </button>
                      <button onClick={() => setEditingRule(null)} className="text-muted-foreground hover:text-foreground">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="text-primary font-medium">{suggestion.suggested_strategy}</span>
                      <div className="ml-auto flex items-center gap-1">
                        <button
                          onClick={() => setEditingRule({ id: columnId, masking_type: suggestion.suggested_strategy, preserve_format: false, deterministic: false })}
                          className="text-muted-foreground hover:text-foreground p-1"
                          title="Edit rule"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={async () => {
                            if (!selectedPolicyId || !confirm("Delete this masking rule?")) return;
                            const ok = await deleteRule(projectId, selectedPolicyId, columnId);
                            if (ok) setAppliedRules((prev) => { const next = new Set(prev); next.delete(columnId); return next; });
                          }}
                          className="text-muted-foreground hover:text-red-500 p-1"
                          title="Delete rule"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <MaskingPolicyList projectId={projectId} onCreateClick={() => setShowCreate(true)} />
      <MaskingRuleEditor
        selectedStrategy={selectedStrategy}
        onSelect={setSelectedStrategy}
        consistencyGroup={consistencyGroup}
        onConsistencyGroupChange={setConsistencyGroup}
        linkedColumnIds={linkedColumnIds}
        onLinkedColumnIdsChange={setLinkedColumnIds}
      />
      <MaskingPreview data={previewData} />
    </div>
  );
}
