"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface Job {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface JobState {
  jobs: Job[];
  totalCount: number;
  loading: boolean;
  fetchJobs: (projectId: string, filters?: { type?: string; status?: string; page?: number }) => Promise<void>;
  cancelJob: (projectId: string, jobId: string) => Promise<void>;
  retryJob: (projectId: string, jobId: string) => Promise<string | null>;
}

export const useJobStore = create<JobState>((set, get) => ({
  jobs: [],
  totalCount: 0,
  loading: false,

  fetchJobs: async (projectId, filters) => {
    set({ loading: true });
    try {
      const p = filters?.page || 1;
      let url = `/api/v1/projects/${projectId}/jobs?page=${p}&page_size=20`;
      if (filters?.type) url += `&job_type=${filters.type}`;
      if (filters?.status) url += `&status=${filters.status}`;
      const data = await api.get<{ items: Job[]; total_count: number }>(url);
      set({ jobs: data.items, totalCount: data.total_count, loading: false });
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
      set({ loading: false });
    }
  },

  cancelJob: async (projectId, jobId) => {
    try {
      await api.post(`/api/v1/projects/${projectId}/jobs/${jobId}/cancel`);
      toast.info("Job cancelled");
      await get().fetchJobs(projectId);
    } catch (err) {
      console.error("Failed to cancel job:", err);
      toast.error("Failed to cancel job");
    }
  },

  retryJob: async (projectId, jobId) => {
    try {
      const data = await api.post<{ job_id: string }>(`/api/v1/projects/${projectId}/jobs/${jobId}/retry`);
      toast.success("Job retry started");
      await get().fetchJobs(projectId);
      return data.job_id;
    } catch (err) {
      console.error("Failed to retry job:", err);
      toast.error("Failed to retry job");
      return null;
    }
  },
}));
