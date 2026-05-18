"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface Project {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  settings: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  // Populated only when the New Project Wizard created a connection or
  // queued a discovery job inline. Plain create paths leave these null.
  connection_id?: string | null;
  discovery_job_id?: string | null;
}

/** Payload shape POST /projects accepts when called from the wizard. */
export interface AtomicProjectPayload {
  name: string;
  description?: string;
  initial_connection?: Record<string, unknown> | null;
  run_discovery?: boolean;
}

interface ProjectState {
  projects: Project[];
  totalCount: number;
  currentPage: number;
  pageSize: number;
  viewMode: "table" | "card";
  loading: boolean;
  error: string | null;
  fetchProjects: (page?: number) => Promise<void>;
  fetchProject: (id: string) => Promise<Project | null>;
  createProject: (name: string, description: string) => Promise<Project | null>;
  /** Wizard create. Returns null on failure (toast surfaced); on success
   * the returned Project carries connection_id + discovery_job_id when the
   * wizard included an initial_connection / run_discovery. */
  createProjectAtomic: (payload: AtomicProjectPayload) => Promise<Project | null>;
  /** Clone an existing project (T3.2 — child workspace). Optional name +
   * description overrides; null is a UI-surfaced error. */
  cloneProject: (
    parentId: string,
    overrides?: { name?: string; description?: string }
  ) => Promise<Project | null>;
  updateProject: (id: string, data: { name?: string; description?: string; settings?: Record<string, unknown> }) => Promise<Project | null>;
  deleteProject: (id: string) => Promise<void>;
  setViewMode: (mode: "table" | "card") => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  totalCount: 0,
  currentPage: 1,
  pageSize: 12,
  viewMode: "table",
  loading: false,
  error: null,

  fetchProjects: async (page?: number) => {
    const p = page || get().currentPage;
    set({ loading: true, error: null, currentPage: p });
    try {
      const data = await api.get<{ items: Project[]; total_count: number }>(
        `/api/v1/projects?page=${p}&page_size=${get().pageSize}`
      );
      set({ projects: data.items, totalCount: data.total_count, loading: false });
    } catch (err) {
      console.error("Failed to fetch projects:", err);
      set({ error: "Failed to load projects", loading: false });
    }
  },

  fetchProject: async (id: string) => {
    try {
      return await api.get<Project>(`/api/v1/projects/${id}`);
    } catch (err) {
      console.error("Failed to fetch project:", err);
      return null;
    }
  },

  updateProject: async (id, data) => {
    try {
      const project = await api.put<Project>(`/api/v1/projects/${id}`, data);
      toast.success("Project updated");
      await get().fetchProjects();
      return project;
    } catch (err) {
      console.error("Failed to update project:", err);
      toast.error("Failed to update project");
      return null;
    }
  },

  createProject: async (name: string, description: string) => {
    try {
      const project = await api.post<Project>("/api/v1/projects", { name, description });
      toast.success("Project created");
      await get().fetchProjects();
      return project;
    } catch (err) {
      console.error("Failed to create project:", err);
      toast.error("Failed to create project");
      return null;
    }
  },

  createProjectAtomic: async (payload) => {
    try {
      const project = await api.post<Project>("/api/v1/projects", payload);
      // The toast message reflects what actually happened — the wizard
      // promises connection + discovery feedback so users know how far
      // the chain ran.
      if (project.discovery_job_id) {
        toast.success("Project created and discovery started");
      } else if (project.connection_id) {
        toast.success("Project and connection created");
      } else {
        toast.success("Project created");
      }
      await get().fetchProjects();
      return project;
    } catch (err) {
      console.error("Failed to create project (atomic):", err);
      const message = err instanceof Error ? err.message : "Failed to create project";
      toast.error(message);
      return null;
    }
  },

  cloneProject: async (parentId, overrides) => {
    try {
      const child = await api.post<Project>(
        `/api/v1/projects/${parentId}/clone`,
        overrides ?? {}
      );
      toast.success(`Cloned to "${child.name}"`);
      await get().fetchProjects();
      return child;
    } catch (err) {
      console.error("Failed to clone project:", err);
      const message = err instanceof Error ? err.message : "Failed to clone project";
      toast.error(message);
      return null;
    }
  },

  deleteProject: async (id: string) => {
    try {
      await api.del(`/api/v1/projects/${id}`);
      toast.success("Project deleted");
      await get().fetchProjects();
    } catch (err) {
      console.error("Failed to delete project:", err);
      toast.error("Failed to delete project");
    }
  },

  setViewMode: (mode) => set({ viewMode: mode }),
}));
