"use client";

import Link from "next/link";
import { Play, Workflow as WorkflowIcon } from "lucide-react";
import { useWorkflowStore } from "@/stores/workflow-store";
import { EmptyState } from "@/components/common/empty-state";

interface WorkflowListProps { projectId: string; onCreateClick: () => void; }

export function WorkflowList({ projectId, onCreateClick }: WorkflowListProps) {
  const { workflows, loading, executeWorkflow } = useWorkflowStore();

  if (loading) return <div className="space-y-2">{[1,2].map(i => <div key={i} className="h-16 animate-pulse rounded-lg border border-border bg-muted" />)}</div>;
  if (workflows.length === 0) return <EmptyState icon={WorkflowIcon} title="No workflows" description="Create a workflow to automate your TDM pipeline." action={{ label: "Create Workflow", onClick: onCreateClick }} />;

  return (
    <div className="space-y-3">
      {workflows.map(wf => (
        <div key={wf.id} className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <Link href={`/projects/${projectId}/workflows/${wf.id}`} className="text-sm font-medium text-foreground hover:text-primary">{wf.name}</Link>
              <p className="text-xs text-muted-foreground">{wf.description || "No description"}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-xs ${wf.is_active ? "bg-green-500/10 text-green-600" : "bg-gray-500/10 text-gray-500"}`}>
                {wf.is_active ? "Active" : "Inactive"}
              </span>
              <button onClick={() => executeWorkflow(projectId, wf.id)} className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted">
                <Play className="h-3 w-3" /> Run
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
