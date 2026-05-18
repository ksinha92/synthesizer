"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface Connection {
  id: string;
  project_id: string;
  name: string;
  connector_type: string;
  host: string;
  port: number;
  database_name: string;
  /** Identity, not a secret — surfaced so the edit form can repopulate it. */
  username: string;
  status: string;
  last_tested_at: string | null;
  created_at: string;
  /** Backend-redacted ``extra_params`` — secret values are returned as ``""``.
   * Drives full form hydration on edit; without this, the edit drawer
   * silently wipes enterprise auth config (Snowflake key-pair, Databricks
   * M2M client creds, OAuth refresh-token quad, SSL cert paths, etc.). */
  safe_extras: Record<string, unknown>;
}

interface TestResult {
  success: boolean;
  latency_ms: number;
  status: string;
}

interface ConnectionState {
  connections: Connection[];
  totalCount: number;
  loading: boolean;
  testResults: Record<string, TestResult>;
  testingIds: Set<string>;
  schemas: Record<string, string[]>;
  schemasLoading: boolean;
  fetchConnections: (projectId: string) => Promise<void>;
  createConnection: (projectId: string, data: Record<string, unknown>) => Promise<Connection | null>;
  updateConnection: (projectId: string, connectionId: string, data: Record<string, unknown>) => Promise<Connection | null>;
  testConnection: (projectId: string, connectionId: string) => Promise<void>;
  deleteConnection: (projectId: string, connectionId: string) => Promise<void>;
  fetchSchemas: (projectId: string, connectionId: string) => Promise<string[]>;
}

export const useConnectionStore = create<ConnectionState>((set, get) => ({
  connections: [],
  totalCount: 0,
  loading: false,
  testResults: {},
  testingIds: new Set(),
  schemas: {},
  schemasLoading: false,

  fetchConnections: async (projectId: string) => {
    set({ loading: true });
    try {
      const data = await api.get<{ items: Connection[]; total_count: number }>(
        `/api/v1/projects/${projectId}/connections?page=1&page_size=50`
      );
      set({ connections: data.items, totalCount: data.total_count, loading: false });
    } catch (err) {
      console.error("Failed to fetch connections:", err);
      set({ loading: false });
    }
  },

  createConnection: async (projectId: string, data: Record<string, unknown>) => {
    try {
      const conn = await api.post<Connection>(`/api/v1/projects/${projectId}/connections`, data);
      toast.success("Connection created");
      await get().fetchConnections(projectId);
      return conn;
    } catch (err) {
      console.error("Failed to create connection:", err);
      toast.error("Failed to create connection");
      return null;
    }
  },

  updateConnection: async (projectId: string, connectionId: string, data: Record<string, unknown>) => {
    try {
      const conn = await api.put<Connection>(`/api/v1/projects/${projectId}/connections/${connectionId}`, data);
      toast.success("Connection updated");
      await get().fetchConnections(projectId);
      return conn;
    } catch (err) {
      console.error("Failed to update connection:", err);
      toast.error("Failed to update connection");
      return null;
    }
  },

  testConnection: async (projectId: string, connectionId: string) => {
    set((s) => ({ testingIds: new Set([...Array.from(s.testingIds), connectionId]) }));
    try {
      const result = await api.post<TestResult>(`/api/v1/projects/${projectId}/connections/${connectionId}/test`);
      set((s) => ({
        testResults: { ...s.testResults, [connectionId]: result },
        testingIds: new Set(Array.from(s.testingIds).filter((id) => id !== connectionId)),
      }));
      if (result.success) toast.success(`Connected (${result.latency_ms}ms)`);
      else toast.error("Connection test failed");
      await get().fetchConnections(projectId);
    } catch (err) {
      console.error("Failed to test connection:", err);
      set((s) => ({
        testResults: { ...s.testResults, [connectionId]: { success: false, latency_ms: 0, status: "error" } },
        testingIds: new Set(Array.from(s.testingIds).filter((id) => id !== connectionId)),
      }));
      toast.error("Connection test failed");
    }
  },

  deleteConnection: async (projectId: string, connectionId: string) => {
    try {
      await api.del(`/api/v1/projects/${projectId}/connections/${connectionId}`);
      toast.success("Connection deleted");
      await get().fetchConnections(projectId);
    } catch (err) {
      console.error("Failed to delete connection:", err);
      toast.error("Failed to delete connection");
    }
  },

  fetchSchemas: async (projectId: string, connectionId: string) => {
    set({ schemasLoading: true });
    try {
      const data = await api.get<{ schemas: Array<{ schema_name?: string; name?: string }> }>(
        `/api/v1/projects/${projectId}/connections/${connectionId}/schemas`
      );
      const names = (data.schemas || []).map((s) => s.schema_name || s.name || "unknown");
      set((state) => ({
        schemas: { ...state.schemas, [connectionId]: names },
        schemasLoading: false,
      }));
      return names;
    } catch (err) {
      console.error("Failed to fetch schemas:", err);
      set({ schemasLoading: false });
      toast.error("Failed to fetch schemas from connection");
      return [];
    }
  },
}));
