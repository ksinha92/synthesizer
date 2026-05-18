"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface AnalysisRow { table_name: string; full_count: number; subset_count: number; percentage: number; }

interface SubsetConfigEntry {
  id: string;
  name: string;
  // Null when the original source connection has been deleted (FK ON DELETE SET NULL).
  // UI should surface a "disconnected — reassign source" affordance for these.
  source_connection_id: string | null;
  target_connection_id: string | null;
  target_percentage: number | null;
  target_row_count: number | null;
  root_tables: Array<Record<string, unknown>>;
  traversal_strategy: string;
  created_at: string;
}

interface SubsettingState {
  analysis: AnalysisRow[];
  analyzing: boolean;
  configs: SubsetConfigEntry[];
  configsLoading: boolean;
  createConfig: (projectId: string, data: Record<string, unknown>) => Promise<string | null>;
  analyze: (projectId: string, configId: string) => Promise<void>;
  execute: (projectId: string, configId: string) => Promise<string | null>;
  fetchConfigs: (projectId: string) => Promise<void>;
}

export const useSubsettingStore = create<SubsettingState>((set) => ({
  analysis: [], analyzing: false,
  configs: [], configsLoading: false,

  createConfig: async (projectId, data) => {
    try {
      const res = await api.post<{ id: string }>(`/api/v1/projects/${projectId}/subset/configs`, data);
      toast.success("Subset config created");
      return res.id;
    } catch (err) { console.error("Failed to create subset config:", err); toast.error("Failed to create subset config"); return null; }
  },

  analyze: async (projectId, configId) => {
    set({ analyzing: true });
    try {
      const data = await api.post<{ analysis: AnalysisRow[] }>(`/api/v1/projects/${projectId}/subset/analyze`, { config_id: configId });
      set({ analysis: data.analysis, analyzing: false });
    } catch (err) { console.error("Failed to analyze subset:", err); toast.error("Analysis failed"); set({ analyzing: false }); }
  },

  execute: async (projectId, configId) => {
    try {
      const data = await api.post<{ job_id: string }>(`/api/v1/projects/${projectId}/subset/execute`, { config_id: configId });
      toast.success("Subsetting job started");
      return data.job_id;
    } catch (err) { console.error("Failed to execute subset:", err); toast.error("Failed to start subsetting"); return null; }
  },

  fetchConfigs: async (projectId) => {
    set({ configsLoading: true });
    try {
      const data = await api.get<{ configs: SubsetConfigEntry[] }>(`/api/v1/projects/${projectId}/subset/configs`);
      set({ configs: data.configs || [], configsLoading: false });
    } catch (err) { console.error("Failed to fetch configs:", err); set({ configsLoading: false }); }
  },
}));
