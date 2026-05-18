"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface WorkflowItem { id: string; name: string; description: string; is_active: boolean; created_at: string; }

interface ExecutionEntry {
  id: string;
  status: string;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

interface WorkflowState {
  workflows: WorkflowItem[];
  loading: boolean;
  executions: ExecutionEntry[];
  executionsLoading: boolean;
  fetchWorkflows: (projectId: string) => Promise<void>;
  createWorkflow: (projectId: string, data: Record<string, unknown>) => Promise<WorkflowItem | null>;
  executeWorkflow: (projectId: string, workflowId: string) => Promise<string | null>;
  fetchExecutions: (projectId: string, workflowId: string) => Promise<void>;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflows: [], loading: false,
  executions: [], executionsLoading: false,

  fetchWorkflows: async (projectId) => {
    set({ loading: true });
    try {
      const data = await api.get<{ workflows: WorkflowItem[] }>(`/api/v1/projects/${projectId}/workflows`);
      set({ workflows: data.workflows, loading: false });
    } catch (err) { console.error("Failed to fetch workflows:", err); set({ loading: false }); }
  },

  createWorkflow: async (projectId, data) => {
    try {
      const wf = await api.post<WorkflowItem>(`/api/v1/projects/${projectId}/workflows`, data);
      toast.success("Workflow created");
      await get().fetchWorkflows(projectId);
      return wf;
    } catch (err) { console.error("Failed to create workflow:", err); toast.error("Failed to create workflow"); return null; }
  },

  executeWorkflow: async (projectId, workflowId) => {
    try {
      const data = await api.post<{ job_id: string }>(`/api/v1/projects/${projectId}/workflows/${workflowId}/execute`);
      toast.success("Workflow execution started");
      return data.job_id;
    } catch (err) { console.error("Failed to execute workflow:", err); toast.error("Failed to execute workflow"); return null; }
  },

  fetchExecutions: async (projectId, workflowId) => {
    set({ executionsLoading: true });
    try {
      const data = await api.get<{ items: ExecutionEntry[]; total: number }>(
        `/api/v1/projects/${projectId}/workflows/${workflowId}/executions?page=1&page_size=20`
      );
      set({ executions: data.items || [], executionsLoading: false });
    } catch (err) { console.error("Failed to fetch executions:", err); set({ executionsLoading: false }); }
  },
}));
