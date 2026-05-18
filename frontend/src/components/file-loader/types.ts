/**
 * Shared types for the File Loader wizard, viewer, auto-mapper, and
 * dictionary mapper. Mirrors the Pydantic shapes defined by
 * ``synthetic_file_schemas.py``, ``file_schema_preview.py``,
 * ``file_schema_relationships.py``, and ``file_schema_mapper.py``.
 */

export interface FileFieldDetail {
  name: string;
  data_type: string; // "alphanumeric" | "numeric" | "decimal" | "binary" | "packed_decimal"
  length: number;
  byte_length: number;
  start_position: number;
  decimal_places?: number;
  comp_type?: string; // "none" | "comp" | "comp_3"
  nullable?: boolean;
  pii_type?: string | null;
  fk_reference?: { file: string; field: string } | null;
}

export interface LayoutCondition {
  field_name: string;
  operator: "eq" | "ne" | "in" | "starts_with";
  value: string | string[];
}

export interface LayoutVariant {
  name: string;
  fields: FileFieldDetail[];
  conditions: LayoutCondition[];
}

export interface FileSchemaDetail {
  id: string;
  name: string;
  file_format: string;
  encoding: string;
  record_length: number;
  field_count: number;
  output_filename?: string | null;
  has_rdw?: boolean;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  fields: FileFieldDetail[];
  layout_variants: LayoutVariant[];
}

export interface FileSchemaSummary {
  id: string;
  name: string;
  file_format: string;
  encoding: string;
  record_length: number;
  field_count: number;
  output_filename?: string | null;
  created_at?: string | null;
}

export interface PreviewRow {
  row_index: number;
  layout: string; // variant name or "_base"
  fields: Record<string, string | number | boolean | null>;
}

export interface PreviewSummary {
  total_rows: number;
  matched: Record<string, number>;
  parse_errors: number;
}

export interface PreviewResponse {
  rows: PreviewRow[];
  summary: PreviewSummary;
  errors: { field: string; row_index: number; error: string }[];
}

export interface RelationshipEvidence {
  name_similarity: number;
  type_compatibility: number;
  cardinality_match: boolean;
  value_overlap: number | null;
}

export interface RelationshipSuggestion {
  source_file: string;
  source_field: string;
  target_file: string;
  target_field: string;
  score: number;
  evidence: RelationshipEvidence;
  sample_size: number;
}

export interface SuggestRelationshipsResponse {
  suggestions: RelationshipSuggestion[];
  schemas_considered: number;
  threshold: number;
}

export type SplitStrategy = "single" | "split_01" | "split_redefine";

export type WizardSource =
  | "upload-copybook"
  | "upload-dictionary"
  | "manual"
  | "from-discovery";
