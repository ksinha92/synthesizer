"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

interface Column {
  id: string;
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  pii_type: string;
  pii_confidence: number;
  classification: string;
  stats: Record<string, unknown>;
}

interface Table {
  id: string;
  table_name: string;
  row_count: number;
  size_bytes: number;
  columns: Column[];
}

interface Schema {
  id: string;
  schema_name: string;
  discovered_at: string;
  tables: Table[];
}

interface PIIColumn {
  id: string;
  table_id: string;
  column_name: string;
  data_type: string;
  pii_type: string;
  confidence: number;
  detector: string;
  classification: string;
  override_by: string | null;
  override_note: string | null;
}

interface DiscoveryState {
  schemas: Schema[];
  piiColumns: PIIColumn[];
  selectedColumn: Column | null;
  loading: boolean;
  piiLoading: boolean;
  runDiscovery: (projectId: string, connectionId: string) => Promise<string | null>;
  fetchResults: (projectId: string, connectionId: string) => Promise<void>;
  fetchPII: (projectId: string, schemaId: string) => Promise<void>;
  selectColumn: (col: Column | null) => void;
  overrideClassification: (projectId: string, columnId: string, piiType: string, note: string) => Promise<void>;
  relationships: {
    id?: string;
    source_table: string;
    target_table: string;
    source_column: string;
    target_column: string;
    is_virtual?: boolean;
  }[];
  fetchRelationships: (projectId: string) => Promise<void>;
  deleteRelationship: (projectId: string, relationshipId: string) => Promise<void>;
}

export const useDiscoveryStore = create<DiscoveryState>((set, get) => ({
  schemas: [],
  piiColumns: [],
  selectedColumn: null,
  loading: false,
  piiLoading: false,

  runDiscovery: async (projectId, connectionId) => {
    try {
      const res = await api.post<{ job_id: string }>(`/api/v1/projects/${projectId}/discovery/run`, { connection_id: connectionId });
      toast.success("Discovery job started");
      return res.job_id;
    } catch (err) {
      console.error("Failed to run discovery:", err);
      toast.error("Failed to start discovery");
      return null;
    }
  },

  fetchResults: async (projectId, connectionId) => {
    set({ loading: true });
    try {
      const data = await api.get<{ schemas: Schema[] }>(`/api/v1/projects/${projectId}/discovery/results?connection_id=${connectionId}`);
      set({ schemas: data.schemas, loading: false });
    } catch (err) {
      console.error("Failed to fetch discovery results:", err);
      set({ loading: false });
    }
  },

  fetchPII: async (projectId, schemaId) => {
    set({ piiLoading: true });
    try {
      const data = await api.get<{ columns: PIIColumn[] }>(`/api/v1/projects/${projectId}/discovery/pii?schema_id=${schemaId}`);
      set({ piiColumns: data.columns, piiLoading: false });
    } catch {
      set({ piiLoading: false });
    }
  },

  relationships: [],

  fetchRelationships: async (projectId) => {
    // The relationships endpoint requires schema_id; use the first schema's id
    // when available. Fall back to FK-derived heuristic otherwise.
    const { schemas } = get();
    const firstSchemaId = schemas[0]?.id;
    if (firstSchemaId) {
      try {
        type ApiRel = {
          id: string;
          source_table_id: string;
          target_table_id: string;
          source_column_id: string;
          target_column_id: string;
          is_virtual?: boolean;
        };
        const data = await api.get<{ relationships: ApiRel[] }>(
          `/api/v1/projects/${projectId}/discovery/relationships?schema_id=${firstSchemaId}`
        );
        // Resolve table/column IDs back to names from the loaded schemas.
        const tableNameById = new Map<string, string>();
        const colNameById = new Map<string, string>();
        for (const s of schemas) {
          for (const t of s.tables || []) {
            tableNameById.set(t.id, t.table_name);
            for (const c of t.columns || []) {
              colNameById.set(c.id, c.column_name);
            }
          }
        }
        const rels = data.relationships.map((r) => ({
          id: r.id,
          source_table: tableNameById.get(r.source_table_id) || r.source_table_id,
          target_table: tableNameById.get(r.target_table_id) || r.target_table_id,
          source_column: colNameById.get(r.source_column_id) || "",
          target_column: colNameById.get(r.target_column_id) || "",
          is_virtual: !!r.is_virtual,
        }));
        set({ relationships: rels });
        return;
      } catch {
        // fall through to heuristic
      }
    }

    // Fallback: derive from schema FK info if available
    const rels: {
      source_table: string;
      target_table: string;
      source_column: string;
      target_column: string;
    }[] = [];
    for (const schema of schemas) {
      for (const table of schema.tables) {
        for (const col of table.columns) {
          if (col.is_foreign_key) {
            rels.push({
              source_table: table.table_name,
              target_table: col.column_name.replace(/_id$/, "s"),
              source_column: col.column_name,
              target_column: "id",
            });
          }
        }
      }
    }
    set({ relationships: rels });
  },

  deleteRelationship: async (projectId, relationshipId) => {
    try {
      await api.del(`/api/v1/projects/${projectId}/relationships/${relationshipId}`);
      toast.success("Relationship deleted");
      // Re-fetch to reflect the removal.
      await get().fetchRelationships(projectId);
    } catch {
      toast.error("Delete failed");
    }
  },

  selectColumn: (col) => set({ selectedColumn: col }),

  overrideClassification: async (projectId, columnId, piiType, note) => {
    try {
      await api.put(`/api/v1/projects/${projectId}/discovery/columns/${columnId}/classification`, {
        pii_type: piiType,
        classification: "manually_classified",
        note,
      });
      // Refresh PII list
      const { schemas } = get();
      if (schemas.length > 0) {
        await get().fetchPII(projectId, schemas[0].id);
      }
    } catch {
      // handled
    }
  },
}));
