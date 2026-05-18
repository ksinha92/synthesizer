"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { api } from "@/hooks/use-api";
import { useWorkflowStore } from "@/stores/workflow-store";
import { cn } from "@/lib/utils";

// Dynamic import — ReactFlow is ~200KB, avoid SSR
const WorkflowCanvas = dynamic(
  () => import("@/components/workflows/workflow-canvas").then((m) => ({ default: m.WorkflowCanvas })),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-96 text-sm text-muted-foreground">Loading canvas...</div> }
);

interface WorkflowDetail {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  dag_definition: { nodes: any[]; edges: any[] };
}

const STATUS_STYLES: Record<string, { icon: typeof CheckCircle2; color: string }> = {
  completed: { icon: CheckCircle2, color: "text-green-600 dark:text-green-400 bg-green-500/10" },
  failed: { icon: XCircle, color: "text-red-600 dark:text-red-400 bg-red-500/10" },
  running: { icon: Loader2, color: "text-yellow-600 dark:text-yellow-400 bg-yellow-500/10" },
  pending: { icon: Clock, color: "text-muted-foreground bg-muted" },
};

export default function WorkflowDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const workflowId = params.workflowId as string;
  const [workflow, setWorkflow] = useState<WorkflowDetail | null>(null);
  const { executeWorkflow, fetchExecutions, executions, executionsLoading } = useWorkflowStore();

  useEffect(() => {
    api.get<WorkflowDetail>(`/api/v1/projects/${projectId}/workflows/${workflowId}`)
      .then(setWorkflow)
      .catch(() => {});
    fetchExecutions(projectId, workflowId);
  }, [projectId, workflowId, fetchExecutions]);

  if (!workflow) {
    return <div className="flex items-center justify-center h-96 text-sm text-muted-foreground">Loading workflow...</div>;
  }

  const handleSave = async (dag: { nodes: any[]; edges: any[] }) => {
    await api.put(`/api/v1/projects/${projectId}/workflows/${workflowId}`, {
      name: workflow.name,
      dag_definition: dag,
    });
  };

  const handleExecute = async () => {
    await executeWorkflow(projectId, workflowId);
    fetchExecutions(projectId, workflowId);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">{workflow.name}</h1>
      </div>

      <WorkflowCanvas
        initialDag={workflow.dag_definition || { nodes: [], edges: [] }}
        onSave={handleSave}
        onExecute={handleExecute}
      />

      {/* Execution History */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Execution History</h2>

        {executionsLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : executions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No executions yet. Click Execute to run this workflow.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Status</th>
                  <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Progress</th>
                  <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Started</th>
                  <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Completed</th>
                  <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {executions.map((exec) => {
                  const style = STATUS_STYLES[exec.status] || STATUS_STYLES.pending;
                  const Icon = style.icon;
                  return (
                    <tr key={exec.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", style.color)}>
                          <Icon className={cn("h-3 w-3", exec.status === "running" && "animate-spin")} />
                          {exec.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-20 rounded-full bg-muted overflow-hidden">
                            <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${exec.progress}%` }} />
                          </div>
                          <span className="text-xs text-muted-foreground">{exec.progress}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {exec.started_at ? new Date(exec.started_at).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {exec.completed_at ? new Date(exec.completed_at).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-red-600 dark:text-red-400 max-w-xs truncate" title={exec.error_message || ""}>
                        {exec.error_message || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
