"use client";

import { CheckCircle2 } from "lucide-react";

import type { FileSchemaDetail } from "../types";

interface StepConfirmProps {
  schema: FileSchemaDetail;
  onConfirm: () => void;
  onBack: () => void;
}

/**
 * Final read-only summary. The schema was already saved at the parse
 * step — this is just a "looks good" gate so the user can review before
 * the wizard closes. Closing without confirming still leaves the schema
 * behind; that's intentional (the user can find it from the File Viewer
 * list and delete it if they regret it).
 */
export function StepConfirm({ schema, onConfirm, onBack }: StepConfirmProps) {
  const totalVariants = schema.layout_variants.length;
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3">
        <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600 dark:text-emerald-400" />
        <div>
          <p className="text-sm font-medium text-foreground">{schema.name}</p>
          <p className="text-xs text-muted-foreground">
            Format <span className="font-mono">{schema.file_format}</span> • encoding{" "}
            <span className="font-mono">{schema.encoding}</span> • {schema.field_count}{" "}
            field{schema.field_count === 1 ? "" : "s"} • record length{" "}
            {schema.record_length} bytes
            {totalVariants > 0 && (
              <>
                {" "}
                • {totalVariants} additional layout{totalVariants === 1 ? "" : "s"}
              </>
            )}
          </p>
        </div>
      </div>

      <div className="rounded-md border border-border bg-card">
        <table className="w-full text-xs">
          <thead className="bg-muted/30 text-left">
            <tr>
              <th className="px-2 py-1.5 font-medium text-muted-foreground">Field</th>
              <th className="px-2 py-1.5 font-medium text-muted-foreground">Type</th>
              <th className="px-2 py-1.5 font-medium text-muted-foreground">Offset</th>
              <th className="px-2 py-1.5 font-medium text-muted-foreground">Length</th>
              <th className="px-2 py-1.5 font-medium text-muted-foreground">PII</th>
            </tr>
          </thead>
          <tbody>
            {schema.fields.slice(0, 20).map((f) => (
              <tr key={f.name} className="border-t border-border">
                <td className="px-2 py-1 font-mono text-foreground">{f.name}</td>
                <td className="px-2 py-1 font-mono text-muted-foreground">
                  {f.data_type}
                </td>
                <td className="px-2 py-1 font-mono text-muted-foreground">
                  {f.start_position}
                </td>
                <td className="px-2 py-1 font-mono text-muted-foreground">
                  {f.byte_length}
                </td>
                <td className="px-2 py-1 text-muted-foreground">{f.pii_type ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {schema.fields.length > 20 && (
          <p className="border-t border-border bg-muted/20 px-2 py-1 text-[10px] text-muted-foreground">
            Showing first 20 of {schema.fields.length} fields.
          </p>
        )}
      </div>

      <div className="flex justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-input bg-background px-3 py-1.5 text-xs hover:bg-muted/40"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
        >
          Done
        </button>
      </div>
    </div>
  );
}
