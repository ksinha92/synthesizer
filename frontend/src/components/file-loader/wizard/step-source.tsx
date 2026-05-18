"use client";

import { FileCode2, FileSpreadsheet, FileText, Database } from "lucide-react";

import { cn } from "@/lib/utils";
import type { WizardSource } from "../types";

const SOURCES: {
  id: WizardSource;
  label: string;
  description: string;
  icon: typeof FileCode2;
}[] = [
  {
    id: "upload-copybook",
    label: "Upload COBOL copybook",
    description:
      "Parse PIC/COMP/COMP-3/REDEFINES/OCCURS into a fixed-width or VSAM schema.",
    icon: FileCode2,
  },
  {
    id: "upload-dictionary",
    label: "Upload Excel data dictionary",
    description:
      "Parse a .xlsx data dictionary into a target file format and encoding.",
    icon: FileSpreadsheet,
  },
  {
    id: "manual",
    label: "Build manually",
    description:
      "Define fields by hand — useful for greenfield schemas or quick test cases.",
    icon: FileText,
  },
  {
    id: "from-discovery",
    label: "Derive from a discovered DB table",
    description:
      "Reuse a connection's discovered schema as the basis for a file output schema.",
    icon: Database,
  },
];

interface StepSourceProps {
  selected: WizardSource | null;
  onSelect: (source: WizardSource) => void;
  onCancel: () => void;
}

export function StepSource({ selected, onSelect, onCancel }: StepSourceProps) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Choose where the schema comes from. You can refine it in the next step
        before saving.
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {SOURCES.map(({ id, label, description, icon: Icon }) => {
          const active = selected === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              className={cn(
                "flex items-start gap-3 rounded-lg border border-border bg-card p-3 text-left hover:border-primary/60 hover:bg-muted/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary",
                active && "border-primary bg-primary/5",
              )}
            >
              <Icon className="mt-0.5 h-5 w-5 text-primary" />
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">{label}</p>
                <p className="text-[11px] text-muted-foreground">{description}</p>
              </div>
            </button>
          );
        })}
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-input bg-background px-3 py-1.5 text-xs hover:bg-muted/40"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
