"use client";

import { useParams } from "next/navigation";
import { PrivacyHub } from "@/components/privacy-hub/privacy-hub";

export default function PrivacyHubPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Privacy Hub</h1>
      <PrivacyHub projectId={projectId} />
    </div>
  );
}
