/**
 * Shared types for the Ephemeral Environments surface. Pulled out of the
 * page route in Phase 61 (F19) so each sub-component is independently
 * importable / testable.
 */

export interface EphemeralEnv {
  id: string;
  project_id: string;
  name: string;
  source_job_id: string | null;
  destination_connection_id: string | null;
  schema_name: string | null;
  status: "pending" | "provisioning" | "ready" | "expired" | "revoked";
  expires_at: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  seconds_remaining: number;
}

export interface EphemeralListResponse {
  items: EphemeralEnv[];
  total_count: number;
}

export interface ConnectionOption {
  id: string;
  name: string;
}

export const TTL_OPTIONS = [1, 3, 7, 14, 30];
