"use client";

import { useParams } from "next/navigation";

import { ProjectOverview } from "@/components/dashboard/project-overview";
import { WorkflowIndicator } from "@/components/projects/workflow-indicator";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  return (
    <div className="space-y-6">
      <WorkflowIndicator projectId={projectId} activeSuffix="" />
      <ProjectOverview projectId={projectId} />
    </div>
  );
}
