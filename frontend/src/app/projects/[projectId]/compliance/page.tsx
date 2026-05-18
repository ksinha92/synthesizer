"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ReportGenerator } from "@/components/compliance/report-generator";
import { ReportList } from "@/components/compliance/report-list";
import { useComplianceStore } from "@/stores/compliance-store";

export default function CompliancePage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [selectedRegulation, setSelectedRegulation] = useState("hipaa");
  const { fetchReports } = useComplianceStore();

  useEffect(() => { fetchReports(projectId); }, [projectId, fetchReports]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Compliance & Audit</h1>
      <p className="text-sm text-muted-foreground">Generate HIPAA, GDPR, and CCPA compliance reports based on your PII detections and masking policies.</p>

      <ReportGenerator projectId={projectId} selectedRegulation={selectedRegulation} onSelect={setSelectedRegulation} />
      <ReportList projectId={projectId} />
    </div>
  );
}
