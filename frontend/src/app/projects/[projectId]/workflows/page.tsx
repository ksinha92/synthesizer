"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Plus } from "lucide-react";
import { WorkflowList } from "@/components/workflows/workflow-list";
import { WorkflowEditor } from "@/components/workflows/workflow-editor";
import { useWorkflowStore } from "@/stores/workflow-store";

export default function WorkflowsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [showEditor, setShowEditor] = useState(false);
  const { fetchWorkflows } = useWorkflowStore();

  useEffect(() => { fetchWorkflows(projectId); }, [projectId, fetchWorkflows]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Workflows</h1>
        <button onClick={() => setShowEditor(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          <Plus className="h-4 w-4" /> Create Workflow
        </button>
      </div>
      <WorkflowList projectId={projectId} onCreateClick={() => setShowEditor(true)} />
      <WorkflowEditor open={showEditor} onClose={() => setShowEditor(false)} projectId={projectId} />
    </div>
  );
}
