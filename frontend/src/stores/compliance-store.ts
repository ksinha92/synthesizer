"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface Report { id: string; report_type: string; generated_at: string; summary: Record<string, unknown>; storage_path: string; }

interface ComplianceState {
  reports: Report[];
  loading: boolean;
  generating: boolean;
  fetchReports: (projectId: string) => Promise<void>;
  generateReport: (projectId: string, regulation: string) => Promise<Report | null>;
}

export const useComplianceStore = create<ComplianceState>((set, get) => ({
  reports: [], loading: false, generating: false,

  fetchReports: async (projectId) => {
    set({ loading: true });
    try {
      const data = await api.get<{ reports: Report[] }>(`/api/v1/projects/${projectId}/compliance/reports`);
      set({ reports: data.reports, loading: false });
    } catch (err) { console.error("Failed to fetch reports:", err); set({ loading: false }); }
  },

  generateReport: async (projectId, regulation) => {
    set({ generating: true });
    try {
      const report = await api.post<Report>(`/api/v1/projects/${projectId}/compliance/reports`, { regulation });
      toast.success(`${regulation.toUpperCase()} report generated`);
      await get().fetchReports(projectId);
      set({ generating: false });
      return report;
    } catch (err) { console.error("Failed to generate report:", err); toast.error("Failed to generate report"); set({ generating: false }); return null; }
  },
}));
