"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";

export interface FileSchemaSummary {
  id: string;
  name: string;
  file_format: string;
  encoding: string;
  record_length: number;
  field_count: number;
  output_filename: string | null;
  created_at: string | null;
}

interface FileSchemaDetail extends FileSchemaSummary {
  fields: Array<{
    name: string;
    data_type: string;
    length: number;
    byte_length: number;
    start_position: number;
    decimal_places: number;
    comp_type: string;
    nullable: boolean;
    pii_type: string | null;
    fk_reference: { file: string; field: string } | null;
  }>;
  has_rdw: boolean;
  metadata: Record<string, unknown> | null;
}

export interface CrossFileFK {
  source_file: string;
  source_field: string;
  target_file: string;
  target_field: string;
}

export interface FileOutputJob {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  progress?: number;
  error_message?: string | null;
  result_summary?: Record<string, unknown> | null;
}

interface FileOutputState {
  schemas: FileSchemaSummary[];
  schemasLoading: boolean;
  selectedSchemaIds: Set<string>;
  schemaDetails: Record<string, FileSchemaDetail>;
  formats: Record<string, string>; // schemaId -> file_format
  rowCounts: Record<string, number>; // schemaId -> row_count
  foreignKeys: CrossFileFK[];
  currentJob: FileOutputJob | null;
  generating: boolean;
  fetchSchemas: (projectId: string) => Promise<void>;
  fetchSchemaDetail: (projectId: string, schemaId: string) => Promise<FileSchemaDetail | null>;
  toggleSchema: (schemaId: string) => void;
  setFormat: (schemaId: string, format: string) => void;
  setRowCount: (schemaId: string, count: number) => void;
  addFk: (fk: CrossFileFK) => void;
  removeFk: (index: number) => void;
  generate: (projectId: string, fileSetName: string) => Promise<string | null>;
  pollJob: (projectId: string, jobId: string) => Promise<FileOutputJob | null>;
  downloadUrl: (projectId: string, jobId: string) => string;
}

export const useFileOutputStore = create<FileOutputState>((set, get) => ({
  schemas: [],
  schemasLoading: false,
  selectedSchemaIds: new Set(),
  schemaDetails: {},
  formats: {},
  rowCounts: {},
  foreignKeys: [],
  currentJob: null,
  generating: false,

  fetchSchemas: async (projectId) => {
    set({ schemasLoading: true });
    try {
      const data = await api.get<FileSchemaSummary[]>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas`
      );
      set({ schemas: Array.isArray(data) ? data : [] });
    } catch {
      set({ schemas: [] });
    }
    set({ schemasLoading: false });
  },

  fetchSchemaDetail: async (projectId, schemaId) => {
    try {
      const detail = await api.get<FileSchemaDetail>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas/${schemaId}`
      );
      set((s) => ({ schemaDetails: { ...s.schemaDetails, [schemaId]: detail } }));
      return detail;
    } catch {
      return null;
    }
  },

  toggleSchema: (schemaId) => {
    set((s) => {
      const next = new Set(s.selectedSchemaIds);
      if (next.has(schemaId)) next.delete(schemaId);
      else next.add(schemaId);
      return { selectedSchemaIds: next };
    });
  },

  setFormat: (schemaId, format) => {
    set((s) => ({ formats: { ...s.formats, [schemaId]: format } }));
  },

  setRowCount: (schemaId, count) => {
    set((s) => ({ rowCounts: { ...s.rowCounts, [schemaId]: Math.max(1, count) } }));
  },

  addFk: (fk) => {
    set((s) => ({ foreignKeys: [...s.foreignKeys, fk] }));
  },

  removeFk: (index) => {
    set((s) => ({ foreignKeys: s.foreignKeys.filter((_, i) => i !== index) }));
  },

  generate: async (projectId, fileSetName) => {
    const state = get();
    const selected = state.schemas.filter((s) => state.selectedSchemaIds.has(s.id));
    if (selected.length === 0) return null;

    // Ensure we have full schema details for every selected schema.
    const details: FileSchemaDetail[] = [];
    for (const s of selected) {
      const detail = state.schemaDetails[s.id] || (await state.fetchSchemaDetail(projectId, s.id));
      if (detail) details.push(detail);
    }
    if (details.length !== selected.length) return null;

    const file_set = {
      name: fileSetName || "file-set",
      schemas: details.map((d) => ({
        name: d.name,
        fields: d.fields.map((f) => ({
          name: f.name,
          data_type: f.data_type,
          length: f.length,
          byte_length: f.byte_length,
          start_position: f.start_position,
          decimal_places: f.decimal_places,
          signed: false,
          comp_type: f.comp_type,
          nullable: f.nullable,
          pii_type: f.pii_type,
          fk_reference: f.fk_reference,
          is_filler: false,
          redefines: null,
          occurs: 1,
        })),
        file_format: state.formats[d.id] || d.file_format,
        encoding: d.encoding,
        record_length: d.record_length,
        has_rdw: d.has_rdw,
        output_filename: d.output_filename,
        metadata: d.metadata || {},
      })),
      foreign_keys: state.foreignKeys,
    };

    const row_counts: Record<string, number> = {};
    for (const d of details) {
      row_counts[d.name] = state.rowCounts[d.id] || 100;
    }

    set({ generating: true });
    try {
      const res = await api.post<{ job_id: string; status: string }>(
        `/api/v1/projects/${projectId}/synthetic/file-sets/generate`,
        { file_set, row_counts }
      );
      set({
        currentJob: { job_id: res.job_id, status: res.status },
        generating: false,
      });
      return res.job_id;
    } catch {
      set({ generating: false });
      return null;
    }
  },

  pollJob: async (projectId, jobId) => {
    try {
      // GET /jobs/{id} returns the new JobDetailResponse shape which uses
      // `id` rather than `job_id`. The store still keys file-output UI on
      // `job_id`, so normalise the payload before persisting it — otherwise
      // currentJob.job_id becomes undefined after the first poll and the
      // download link + progress label both crash on `.slice(...)`.
      const raw = await api.get<Partial<FileOutputJob> & { id?: string }>(
        `/api/v1/projects/${projectId}/jobs/${jobId}`
      );
      const job: FileOutputJob = {
        job_id: raw.job_id ?? raw.id ?? jobId,
        status: raw.status ?? "pending",
        progress: raw.progress,
        error_message: raw.error_message,
        result_summary: raw.result_summary,
      };
      set({ currentJob: job });
      return job;
    } catch {
      return null;
    }
  },

  downloadUrl: (projectId, jobId) =>
    `/api/v1/projects/${projectId}/synthetic/jobs/${jobId}/file-output`,
}));
