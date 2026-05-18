"use client";

import { useState } from "react";
import { Key, Hash, AlertTriangle } from "lucide-react";
import { PIIBadge } from "./pii-badge";

interface Column {
  id: string;
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  pii_type: string;
  pii_confidence: number;
  classification: string;
  stats: Record<string, unknown>;
}

interface ColumnDetailProps {
  column: Column | null;
  onOverride: (columnId: string, piiType: string, note: string) => void;
}

const PII_TYPES = [
  "none", "email", "phone", "ssn", "credit_card", "ip_address",
  "person_name", "address", "date_of_birth", "medical_record", "financial_account", "other",
];

export function ColumnDetail({ column, onOverride }: ColumnDetailProps) {
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [newType, setNewType] = useState("");
  const [note, setNote] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [saved, setSaved] = useState(false);

  if (!column) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Select a column to view details
      </div>
    );
  }

  const handleOverrideSave = () => {
    setConfirming(true);
  };

  const handleConfirm = () => {
    onOverride(column.id, newType, note);
    setOverrideOpen(false);
    setConfirming(false);
    setNewType("");
    setNote("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-5 p-4">
      {/* Column info */}
      <div>
        <h3 className="text-lg font-medium text-foreground">{column.column_name}</h3>
        <p className="text-sm text-muted-foreground font-mono">{column.data_type}</p>
      </div>

      {/* Properties */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm">
          {column.is_primary_key && <span className="inline-flex items-center gap-1 text-primary"><Key className="h-3 w-3" /> Primary Key</span>}
          {column.is_foreign_key && <span className="inline-flex items-center gap-1 text-blue-500"><Hash className="h-3 w-3" /> Foreign Key</span>}
          {column.is_nullable && <span className="text-muted-foreground">Nullable</span>}
        </div>
      </div>

      {/* Stats */}
      {column.stats && Object.keys(column.stats).length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-foreground mb-2">Statistics</h4>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(column.stats).map(([key, val]) => (
              <div key={key} className="rounded-md bg-muted px-3 py-2">
                <p className="text-xs text-muted-foreground">{key.replace("_", " ")}</p>
                <p className="text-sm font-medium text-foreground">{String(val)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PII Classification */}
      <div>
        <h4 className="text-sm font-medium text-foreground mb-2">PII Classification</h4>
        <div className="rounded-lg border border-border p-3 space-y-2">
          <div className="flex items-center justify-between">
            <PIIBadge piiType={column.pii_type} confidence={column.pii_confidence} classification={column.classification} size="md" />
            <span className="text-xs text-muted-foreground">{column.classification.replace("_", " ")}</span>
          </div>

          {/* Confidence bar */}
          <div>
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>Confidence</span>
              <span>{Math.round(column.pii_confidence * 100)}%</span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${column.pii_confidence >= 0.65 ? "bg-red-500" : column.pii_confidence >= 0.4 ? "bg-yellow-500" : "bg-gray-400"}`}
                style={{ width: `${column.pii_confidence * 100}%` }}
              />
            </div>
          </div>

          {/* Save feedback */}
          {saved && (
            <p className="text-xs text-green-600 dark:text-green-400 font-medium">Classification updated successfully</p>
          )}

          {/* Override */}
          {!overrideOpen ? (
            <button
              onClick={() => setOverrideOpen(true)}
              className="text-xs text-primary hover:underline"
            >
              Override classification
            </button>
          ) : confirming ? (
            <div className="rounded-md border border-warning bg-warning/5 p-3 space-y-2">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                <p className="text-xs text-foreground">
                  Are you sure you want to change <strong>{column.column_name}</strong> from <strong>{column.pii_type}</strong> to <strong>{newType}</strong>? This affects compliance posture.
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={handleConfirm} className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">Confirm</button>
                <button onClick={() => setConfirming(false)} className="rounded-md border border-border px-3 py-1 text-xs text-muted-foreground">Cancel</button>
              </div>
            </div>
          ) : (
            <div className="space-y-2 pt-2 border-t border-border">
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
              >
                <option value="">Select PII type...</option>
                {PII_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
              </select>
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Reason for override..."
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
              />
              <div className="flex gap-2">
                <button onClick={handleOverrideSave} disabled={!newType} className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground disabled:opacity-50">Save</button>
                <button onClick={() => { setOverrideOpen(false); setNewType(""); setNote(""); }} className="text-xs text-muted-foreground">Cancel</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
