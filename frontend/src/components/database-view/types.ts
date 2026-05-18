export interface ColumnRow {
  schema_name: string;
  table_name: string;
  column_id: string;
  column_name: string;
  data_type: string;
  pii_type: string;
  pii_confidence: number | null;
  status: "not_sensitive" | "protected" | "unprotected";
  current_generator: string | null;
  current_preset_id: string | null;
  rule_id: string | null;
  connection_id: string;
  connection_name: string;
  connector_type: string;
  mixed_types: string[] | null;
  row_count_stale: boolean | null;
}

export interface PresetChoice {
  id: string;
  name: string;
  generator_type: string;
}

export interface DatabaseViewResponse {
  columns: ColumnRow[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
  generator_choices: string[];
  presets: PresetChoice[];
}

export interface BulkRuleResult {
  column_id: string;
  status: "created" | "updated" | "skipped";
  rule_id: string | null;
  error: string | null;
}

export interface BulkRuleResponse {
  results: BulkRuleResult[];
  applied: number;
  skipped: number;
}

export type SortKey = "column" | "type" | "pii" | "status";

export interface RuleAction {
  type: "set_generator" | "set_preset" | "clear";
  value?: string;
}
