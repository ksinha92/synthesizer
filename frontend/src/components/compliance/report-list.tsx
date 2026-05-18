"use client";

import { useState } from "react";
import { Download, FileText, Loader2 } from "lucide-react";
import { useComplianceStore } from "@/stores/compliance-store";
import { EmptyState } from "@/components/common/empty-state";
import { toast } from "@/components/common/toast";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const REGULATION_BADGE: Record<string, string> = {
  hipaa: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
  gdpr: "bg-green-500/10 text-green-700 dark:text-green-400",
  ccpa: "bg-purple-500/10 text-purple-700 dark:text-purple-400",
};

interface ReportListProps { projectId: string; }

export function ReportList({ projectId }: ReportListProps) {
  const { reports, loading } = useComplianceStore();
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownload = async (reportId: string, reportType: string) => {
    setDownloadingId(reportId);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/projects/${projectId}/compliance/reports/${reportId}/download`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error(`Download failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportType}-compliance-report.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("Failed to download report");
    }
    setDownloadingId(null);
  };

  if (loading) return <div className="space-y-2">{[1,2].map(i => <div key={i} className="h-16 animate-pulse rounded-lg border border-border bg-muted" />)}</div>;
  if (reports.length === 0) return <EmptyState icon={FileText} title="No compliance reports" description="Generate a HIPAA, GDPR, or CCPA compliance report." />;

  return (
    <div className="space-y-2">
      {reports.map(r => (
        <div key={r.id} className="flex items-center justify-between rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase ${REGULATION_BADGE[r.report_type] || ""}`}>{r.report_type}</span>
                <span className="text-xs text-muted-foreground">{new Date(r.generated_at).toLocaleString()}</span>
              </div>
              {r.summary && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {(r.summary?.total_pii_columns as number) || 0} PII columns — {(r.summary?.coverage_percentage as number) || 0}% coverage
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => handleDownload(r.id, r.report_type)}
            disabled={downloadingId === r.id}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
          >
            {downloadingId === r.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
            PDF
          </button>
        </div>
      ))}
    </div>
  );
}
