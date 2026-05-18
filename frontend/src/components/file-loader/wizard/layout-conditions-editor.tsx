"use client";

import { Select } from "@/components/common/select";
import type { FileFieldDetail, LayoutCondition } from "../types";

interface LayoutConditionsEditorProps {
  variantName: string;
  baseFields: FileFieldDetail[];
  conditions: LayoutCondition[];
  onChange: (conditions: LayoutCondition[]) => void;
}

/**
 * Inline editor for the AND-conjoined conditions that pick a layout
 * variant. The values are scalar strings for eq/ne/starts_with and a
 * comma-separated list for "in" — the parent serializer splits the
 * comma list when handing the payload to the API.
 */
export function LayoutConditionsEditor({
  variantName,
  baseFields,
  conditions,
  onChange,
}: LayoutConditionsEditorProps) {
  const update = (
    index: number,
    patch: Partial<LayoutCondition>,
  ): LayoutCondition[] =>
    conditions.map((c, i) => (i === index ? { ...c, ...patch } : c));

  const remove = (index: number): LayoutCondition[] =>
    conditions.filter((_, i) => i !== index);

  return (
    <div className="rounded-md border border-border bg-card p-2">
      <p className="text-[11px] font-medium text-foreground">{variantName}</p>
      <div className="mt-1 space-y-1">
        {conditions.map((c, i) => (
          <div key={i} className="flex flex-wrap items-center gap-1 text-[11px]">
            <Select
              fullWidth={false}
              value={c.field_name}
              onChange={(e) =>
                onChange(update(i, { field_name: e.target.value }))
              }
              className="min-w-[140px]"
            >
              <option value="">— field —</option>
              {baseFields.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name}
                </option>
              ))}
            </Select>
            <Select
              fullWidth={false}
              value={c.operator}
              onChange={(e) =>
                onChange(
                  update(i, {
                    operator: e.target.value as LayoutCondition["operator"],
                  }),
                )
              }
              className="min-w-[110px]"
            >
              <option value="eq">equals</option>
              <option value="ne">not equals</option>
              <option value="in">one of</option>
              <option value="starts_with">starts with</option>
            </Select>
            <input
              value={
                Array.isArray(c.value) ? c.value.join(",") : String(c.value ?? "")
              }
              onChange={(e) => {
                const v = e.target.value;
                onChange(
                  update(i, {
                    value: c.operator === "in" ? v.split(",").map((x) => x.trim()) : v,
                  }),
                );
              }}
              placeholder={c.operator === "in" ? "A,B,C" : "value"}
              className="w-40 rounded border border-input bg-background px-2 py-1"
            />
            <button
              type="button"
              onClick={() => onChange(remove(i))}
              className="text-[10px] text-muted-foreground hover:text-destructive"
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            onChange([
              ...conditions,
              { field_name: "", operator: "eq", value: "" },
            ])
          }
          className="text-[11px] text-primary hover:underline"
        >
          + Add condition
        </button>
      </div>
    </div>
  );
}
