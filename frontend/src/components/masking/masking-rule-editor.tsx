"use client";

import { useMemo } from "react";
import { Hash, EyeOff, Shuffle, XCircle, Lock, Type, Eye, ScanText, Link2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDiscoveryStore } from "@/stores/discovery-store";

const STRATEGIES = [
  { key: "hash", label: "Hash", icon: Hash, description: "Deterministic SHA-256" },
  { key: "redact", label: "Redact", icon: EyeOff, description: "Replace with X's" },
  { key: "faker_replace", label: "Faker", icon: Type, description: "Realistic fake" },
  { key: "shuffle", label: "Shuffle", icon: Shuffle, description: "Randomize order" },
  { key: "nullify", label: "Nullify", icon: XCircle, description: "Set to NULL" },
  { key: "fpe", label: "FPE", icon: Lock, description: "Format-preserving" },
  { key: "partial_mask", label: "Partial", icon: Eye, description: "Show first/last" },
  {
    key: "presidio_redact",
    label: "Free-text",
    icon: ScanText,
    description: "Redact PII entities in narrative text (notes, descriptions)",
  },
];

interface MaskingRuleEditorProps {
  selectedStrategy: string;
  onSelect: (s: string) => void;
  /** Phase 58 F7: consistency-group label (free-form). Optional — when omitted
   * the rule is not part of any group and is masked independently. */
  consistencyGroup?: string;
  onConsistencyGroupChange?: (value: string) => void;
  /** Column IDs in the same table that should mask deterministically alongside
   * the current column. Source list is derived from the discovery store. */
  linkedColumnIds?: string[];
  onLinkedColumnIdsChange?: (ids: string[]) => void;
  /** Table whose columns populate the "Link to columns" multi-select. When
   * absent the picker shows an empty hint instead of every column in the DB. */
  currentTableId?: string;
  /** Optional column being edited — excluded from its own link picker. */
  currentColumnId?: string;
}

export function MaskingRuleEditor({
  selectedStrategy,
  onSelect,
  consistencyGroup,
  onConsistencyGroupChange,
  linkedColumnIds,
  onLinkedColumnIdsChange,
  currentTableId,
  currentColumnId,
}: MaskingRuleEditorProps) {
  const schemas = useDiscoveryStore((s) => s.schemas);

  // Columns in the same table (excluding the rule's own column) drive the
  // "Link to columns" picker. Use an empty list when no table is selected so
  // the picker stays inert rather than listing every column in the database.
  const linkableColumns = useMemo(() => {
    if (!currentTableId) return [];
    for (const schema of schemas) {
      const table = schema.tables.find((t) => t.id === currentTableId);
      if (!table) continue;
      return table.columns
        .filter((c) => c.id !== currentColumnId)
        .map((c) => ({ id: c.id, name: c.column_name }));
    }
    return [];
  }, [schemas, currentTableId, currentColumnId]);

  const selectedLinks = linkedColumnIds ?? [];

  const toggleLink = (id: string) => {
    if (!onLinkedColumnIdsChange) return;
    onLinkedColumnIdsChange(
      selectedLinks.includes(id)
        ? selectedLinks.filter((x) => x !== id)
        : [...selectedLinks, id]
    );
  };

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-xs font-medium text-foreground mb-2">Masking Strategy</h4>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {STRATEGIES.map((s) => (
            <button
              key={s.key}
              onClick={() => onSelect(s.key)}
              className={cn(
                "rounded-lg border p-3 text-left transition-all",
                selectedStrategy === s.key ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
              )}
            >
              <s.icon className={cn("h-4 w-4 mb-1", selectedStrategy === s.key ? "text-primary" : "text-muted-foreground")} />
              <p className="text-xs font-medium text-foreground">{s.label}</p>
              <p className="text-[10px] text-muted-foreground">{s.description}</p>
            </button>
          ))}
        </div>
      </div>

      {(onConsistencyGroupChange || onLinkedColumnIdsChange) && (
        <div className="rounded-lg border border-border bg-card p-3 space-y-3">
          <div className="flex items-center gap-2">
            <Link2 className="h-3.5 w-3.5 text-muted-foreground" />
            <h4 className="text-xs font-medium text-foreground">Cross-column consistency</h4>
          </div>

          {onConsistencyGroupChange && (
            <div className="space-y-1">
              <label htmlFor="consistency-group" className="text-[11px] font-medium text-muted-foreground">
                Consistency group
              </label>
              <input
                id="consistency-group"
                type="text"
                value={consistencyGroup ?? ""}
                onChange={(e) => onConsistencyGroupChange(e.target.value)}
                placeholder="e.g. customer-pii"
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/60"
              />
              <p className="text-[10px] text-muted-foreground">
                Rules sharing a group are masked with the same deterministic seed.
              </p>
            </div>
          )}

          {onLinkedColumnIdsChange && (
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">Link to columns</label>
              {!currentTableId ? (
                <p className="rounded-md border border-dashed border-border px-2.5 py-1.5 text-[11px] text-muted-foreground">
                  Select a column from the schema to pick linkable peers in its table.
                </p>
              ) : linkableColumns.length === 0 ? (
                <p className="rounded-md border border-dashed border-border px-2.5 py-1.5 text-[11px] text-muted-foreground">
                  No other columns in this table.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5 rounded-md border border-input bg-background p-1.5">
                  {linkableColumns.map((col) => {
                    const active = selectedLinks.includes(col.id);
                    return (
                      <button
                        key={col.id}
                        type="button"
                        onClick={() => toggleLink(col.id)}
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-mono transition-colors",
                          active
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-muted/70"
                        )}
                      >
                        {col.name}
                      </button>
                    );
                  })}
                </div>
              )}
              <p className="text-[10px] text-muted-foreground">
                Linked columns mask in lock-step so joinable values stay aligned.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
