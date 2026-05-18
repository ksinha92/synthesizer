"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface SyntheticConfig {
  id: string;
  name: string;
  // Null when the original source connection has been deleted (FK ON DELETE SET NULL).
  // UI should surface a "disconnected — reassign source" affordance for these.
  source_connection_id: string | null;
  generation_method: string;
  row_count: number;
  status: string;
  created_at: string;
}

interface SyntheticState {
  configs: SyntheticConfig[];
  selectedEngine: string;
  previewData: Record<string, Record<string, unknown>[]> | null;
  previewLoading: boolean;
  generating: boolean;
  /** ID of the most recently created synthetic config — drives auto-loading of
   * the QualityReport panel after `createConfig` succeeds (Phase 58 F6). */
  lastConfigId: string | null;
  fetchConfigs: (projectId: string) => Promise<void>;
  createConfig: (projectId: string, data: Record<string, unknown>) => Promise<SyntheticConfig | null>;
  preview: (projectId: string, configId: string) => Promise<void>;
  generate: (projectId: string, configId: string) => Promise<string | null>;
  setEngine: (engine: string) => void;
  setLastConfigId: (id: string | null) => void;
}

export const useSyntheticStore = create<SyntheticState>((set) => ({
  configs: [],
  selectedEngine: "faker",
  previewData: null,
  previewLoading: false,
  generating: false,
  lastConfigId: null,

  fetchConfigs: async (projectId) => {
    try {
      const data = await api.get<{ configs: SyntheticConfig[] }>(`/api/v1/projects/${projectId}/synthetic/configs`);
      set({ configs: data.configs });
    } catch (err) { console.error("Failed to fetch configs:", err); }
  },

  createConfig: async (projectId, data) => {
    try {
      const config = await api.post<SyntheticConfig>(`/api/v1/projects/${projectId}/synthetic/configs`, data);
      set({ lastConfigId: config.id });
      toast.success("Config created");
      return config;
    } catch (err) { console.error("Failed to create config:", err); toast.error("Failed to create config"); return null; }
  },

  preview: async (projectId, configId) => {
    set({ previewLoading: true, previewData: null });
    try {
      const data = await api.post<{ preview: Record<string, Record<string, unknown>[]> }>(
        `/api/v1/projects/${projectId}/synthetic/preview`,
        { config_id: configId, limit: 10 }
      );
      set({ previewData: data.preview, previewLoading: false });
    } catch (err) {
      console.error("Failed to preview:", err);
      toast.error("Failed to generate preview");
      set({ previewLoading: false });
    }
  },

  generate: async (projectId, configId) => {
    set({ generating: true });
    try {
      const data = await api.post<{ job_id: string }>(
        `/api/v1/projects/${projectId}/synthetic/generate`,
        { config_id: configId }
      );
      set({ generating: false });
      toast.success("Generation job started");
      return data.job_id;
    } catch (err) {
      console.error("Failed to generate:", err);
      toast.error("Failed to start generation");
      set({ generating: false });
      return null;
    }
  },

  setEngine: (engine) => set({ selectedEngine: engine }),

  setLastConfigId: (id) => set({ lastConfigId: id }),
}));
