"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface Policy { id: string; name: string; description: string; is_default: boolean; created_at: string; }
interface Suggestion { column_id: string; column_name: string; pii_type: string; suggested_strategy: string; confidence: number; cardinality: number; warning: string | null; }

/** Phase 58 F7: per-rule consistency metadata. Both fields are optional; when
 * provided they are forwarded to the API as snake_case (`linked_column_ids`,
 * `consistency_group`). The UI keeps camelCase locally. */
export interface RuleConsistencyExtras {
  linkedColumnIds?: string[];
  consistencyGroup?: string | null;
}

interface MaskingState {
  policies: Policy[];
  suggestions: Suggestion[];
  previewData: { original: Record<string, unknown>; masked: Record<string, unknown> }[];
  loading: boolean;
  fetchPolicies: (projectId: string) => Promise<void>;
  createPolicy: (projectId: string, name: string, description?: string) => Promise<Policy | null>;
  autoSuggest: (projectId: string, schemaId: string) => Promise<void>;
  addRule: (projectId: string, policyId: string, columnId: string, strategy: string, extras?: RuleConsistencyExtras) => Promise<boolean>;
  updateRule: (projectId: string, policyId: string, ruleId: string, data: Record<string, unknown>) => Promise<boolean>;
  deleteRule: (projectId: string, policyId: string, ruleId: string) => Promise<boolean>;
  previewMasking: (projectId: string, policyId: string, connectionId: string) => Promise<void>;
  executeMasking: (projectId: string, policyId: string, connectionId: string) => Promise<string | null>;
}

export const useMaskingStore = create<MaskingState>((set) => ({
  policies: [], suggestions: [], previewData: [], loading: false,

  fetchPolicies: async (projectId) => {
    set({ loading: true });
    try {
      const data = await api.get<{ policies: Policy[] }>(`/api/v1/projects/${projectId}/masking/policies`);
      set({ policies: data.policies, loading: false });
    } catch (err) { console.error("Failed to fetch policies:", err); set({ loading: false }); }
  },

  createPolicy: async (projectId, name, description = "") => {
    try {
      const p = await api.post<Policy>(`/api/v1/projects/${projectId}/masking/policies`, { name, description });
      toast.success("Masking policy created");
      return p;
    } catch (err) { console.error("Failed to create policy:", err); toast.error("Failed to create policy"); return null; }
  },

  autoSuggest: async (projectId, schemaId) => {
    try {
      const data = await api.post<{ suggestions: Suggestion[] }>(`/api/v1/projects/${projectId}/masking/auto-suggest`, { schema_id: schemaId });
      set({ suggestions: data.suggestions });
      toast.info(`${data.suggestions.length} masking suggestions found`);
    } catch (err) { console.error("Failed to auto-suggest:", err); toast.error("Failed to generate suggestions"); }
  },

  addRule: async (projectId, policyId, columnId, strategy, extras) => {
    try {
      const payload: Record<string, unknown> = {
        column_id: columnId,
        masking_type: strategy,
        masking_config: {},
      };
      if (extras?.linkedColumnIds && extras.linkedColumnIds.length > 0) {
        payload.linked_column_ids = extras.linkedColumnIds;
      }
      if (extras?.consistencyGroup) {
        payload.consistency_group = extras.consistencyGroup;
      }
      await api.post(`/api/v1/projects/${projectId}/masking/policies/${policyId}/rules`, payload);
      toast.success("Rule applied");
      return true;
    } catch (err) { console.error("Failed to add rule:", err); toast.error("Failed to apply rule"); return false; }
  },

  updateRule: async (projectId, policyId, ruleId, data) => {
    try {
      // Forward UI-camelCase consistency fields as snake_case for the API.
      const payload: Record<string, unknown> = { ...data };
      if ("linkedColumnIds" in payload) {
        payload.linked_column_ids = payload.linkedColumnIds;
        delete payload.linkedColumnIds;
      }
      if ("consistencyGroup" in payload) {
        payload.consistency_group = payload.consistencyGroup;
        delete payload.consistencyGroup;
      }
      await api.put(`/api/v1/projects/${projectId}/masking/policies/${policyId}/rules/${ruleId}`, payload);
      toast.success("Rule updated");
      return true;
    } catch (err) { console.error("Failed to update rule:", err); toast.error("Failed to update rule"); return false; }
  },

  deleteRule: async (projectId, policyId, ruleId) => {
    try {
      await api.del(`/api/v1/projects/${projectId}/masking/policies/${policyId}/rules/${ruleId}`);
      toast.success("Rule deleted");
      return true;
    } catch (err) { console.error("Failed to delete rule:", err); toast.error("Failed to delete rule"); return false; }
  },

  previewMasking: async (projectId, policyId, connectionId) => {
    try {
      const data = await api.post<{ preview: { original: Record<string, unknown>; masked: Record<string, unknown> }[] }>(`/api/v1/projects/${projectId}/masking/preview`, { policy_id: policyId, connection_id: connectionId });
      set({ previewData: data.preview });
    } catch (err) { console.error("Failed to preview masking:", err); toast.error("Failed to generate preview"); }
  },

  executeMasking: async (projectId, policyId, connectionId) => {
    try {
      const data = await api.post<{ job_id: string }>(`/api/v1/projects/${projectId}/masking/execute`, { policy_id: policyId, connection_id: connectionId });
      toast.success("Masking job started");
      return data.job_id;
    } catch (err) { console.error("Failed to execute masking:", err); toast.error("Failed to start masking"); return null; }
  },
}));
