"use client";

import { Loader2, Shield } from "lucide-react";
import { useComplianceStore } from "@/stores/compliance-store";
import { cn } from "@/lib/utils";

const REGULATIONS = [
  { key: "hipaa", label: "HIPAA", description: "PHI inventory, access controls, encryption status" },
  { key: "gdpr", label: "GDPR", description: "Data mapping, DPIA, right-to-erasure" },
  { key: "ccpa", label: "CCPA", description: "Consumer data categories, business purpose" },
] as const;

interface ReportGeneratorProps { projectId: string; selectedRegulation: string; onSelect: (r: string) => void; }

export function ReportGenerator({ projectId, selectedRegulation, onSelect }: ReportGeneratorProps) {
  const { generateReport, generating } = useComplianceStore();

  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-4">
      <h3 className="text-sm font-semibold text-foreground">Generate Compliance Report</h3>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {REGULATIONS.map(r => (
          <button key={r.key} onClick={() => onSelect(r.key)} className={cn(
            "rounded-lg border p-4 text-left transition-all",
            selectedRegulation === r.key ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
          )}>
            <Shield className={cn("h-5 w-5 mb-2", selectedRegulation === r.key ? "text-primary" : "text-muted-foreground")} />
            <p className="text-sm font-semibold text-foreground">{r.label}</p>
            <p className="text-xs text-muted-foreground mt-1">{r.description}</p>
          </button>
        ))}
      </div>

      <button
        onClick={() => generateReport(projectId, selectedRegulation)}
        disabled={!selectedRegulation || generating}
        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
        {generating ? "Generating..." : "Generate Report"}
      </button>
    </div>
  );
}
