"use client";

import type { FileFieldDetail } from "../types";

interface FieldDetailPanelProps {
  field: FileFieldDetail | null;
  sampleValues: (string | number | boolean | null)[];
}

/**
 * Right-rail field metadata panel — Microfocus / File-AID idiom. Shows
 * everything we know about the selected field plus a short list of
 * sample values pulled from the loaded preview rows.
 */
export function FieldDetailPanel({ field, sampleValues }: FieldDetailPanelProps) {
  if (!field) {
    return (
      <aside className="rounded-lg border border-border bg-card p-3 text-xs text-muted-foreground">
        Click a field in the structure pane to see its detail.
      </aside>
    );
  }
  const trimmedSamples = sampleValues
    .filter((v) => v !== null && v !== undefined && String(v).trim() !== "")
    .slice(0, 8);

  return (
    <aside className="space-y-3 rounded-lg border border-border bg-card p-3 text-xs">
      <header>
        <p className="font-mono text-sm text-foreground">{field.name}</p>
        <p className="text-muted-foreground">
          {field.data_type}
          {field.decimal_places ? `(${field.length}.${field.decimal_places})` : ""}
        </p>
      </header>
      <Row label="Offset (bytes)" value={String(field.start_position)} />
      <Row label="Byte length" value={String(field.byte_length)} />
      <Row label="Logical length" value={String(field.length)} />
      <Row label="COMP type" value={field.comp_type ?? "none"} />
      <Row label="Nullable" value={field.nullable === false ? "no" : "yes"} />
      <Row label="PII" value={field.pii_type ?? "—"} />
      <Row
        label="FK"
        value={
          field.fk_reference
            ? `${field.fk_reference.file}.${field.fk_reference.field}`
            : "—"
        }
      />
      <div>
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
          Sample values
        </p>
        {trimmedSamples.length === 0 ? (
          <p className="text-muted-foreground">— Load sample data to see values</p>
        ) : (
          <ul className="mt-1 space-y-0.5">
            {trimmedSamples.map((v, i) => (
              <li key={i} className="font-mono text-[11px] text-foreground">
                {String(v)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-border/60 pb-1">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono text-foreground">{value}</span>
    </div>
  );
}
