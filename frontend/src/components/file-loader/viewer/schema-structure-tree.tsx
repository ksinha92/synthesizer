"use client";

import { Key, Link2, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { FileFieldDetail } from "../types";

interface SchemaStructureTreeProps {
  fields: FileFieldDetail[];
  selected: string | null;
  onSelect: (fieldName: string | null) => void;
}

/**
 * Microfocus-style structure panel: one row per field with badges for
 * COMP type / nullable / PII / FK. Clicking a row sets the right-pane
 * field-detail target. Reused for both the base layout and any selected
 * conditional variant.
 */
export function SchemaStructureTree({
  fields,
  selected,
  onSelect,
}: SchemaStructureTreeProps) {
  return (
    <div className="overflow-auto rounded-lg border border-border bg-card">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-muted/40">
          <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
            <th className="px-3 py-1.5 font-medium">Field</th>
            <th className="px-3 py-1.5 font-medium">Type</th>
            <th className="px-3 py-1.5 font-medium">Offset</th>
            <th className="px-3 py-1.5 font-medium">Length</th>
            <th className="px-3 py-1.5 font-medium">Flags</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f) => {
            const active = selected === f.name;
            return (
              <tr
                key={f.name}
                onClick={() => onSelect(active ? null : f.name)}
                className={cn(
                  "cursor-pointer border-t border-border hover:bg-muted/30",
                  active && "bg-muted/40",
                )}
              >
                <td className="px-3 py-1 font-mono text-foreground">
                  {f.name}
                  {f.fk_reference && (
                    <span title={`FK → ${f.fk_reference.file}.${f.fk_reference.field}`}>
                      <Link2 className="ml-1 inline h-3 w-3 text-blue-600 dark:text-blue-400" />
                    </span>
                  )}
                </td>
                <td className="px-3 py-1 font-mono text-muted-foreground">
                  {f.data_type}
                  {f.decimal_places ? `(${f.length}.${f.decimal_places})` : ""}
                  {f.comp_type && f.comp_type !== "none" && (
                    <span className="ml-1 rounded bg-blue-500/10 px-1 text-[9px] uppercase text-blue-700 dark:text-blue-300">
                      {f.comp_type.replace("_", "-")}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1 font-mono text-muted-foreground">
                  {f.start_position}
                </td>
                <td className="px-3 py-1 font-mono text-muted-foreground">
                  {f.byte_length}
                </td>
                <td className="px-3 py-1">
                  <div className="flex items-center gap-1 text-[10px]">
                    {f.nullable === false && (
                      <span className="rounded bg-muted px-1 uppercase text-muted-foreground">
                        not null
                      </span>
                    )}
                    {f.pii_type && (
                      <span className="inline-flex items-center gap-0.5 rounded bg-amber-500/10 px-1 uppercase text-amber-700 dark:text-amber-300">
                        <ShieldAlert className="h-2.5 w-2.5" />
                        {f.pii_type}
                      </span>
                    )}
                    {f.name === "_id" || /(_KEY|_ID)$/i.test(f.name) ? (
                      <span title="Probable key">
                        <Key className="h-3 w-3 text-muted-foreground" />
                      </span>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
          {fields.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                No fields in this layout.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
