import type { EphemeralEnv } from "./types";

/**
 * Friendly TTL label for a given env, recomputed against a ticking page
 * clock rather than the server-snapshot `seconds_remaining` so the value
 * stays accurate between reloads.
 */
export function describeTtl(env: EphemeralEnv, now: number): string {
  if (env.status === "revoked") return "Revoked";
  // Recompute remaining from absolute expiry against the page's ticking
  // clock — server's `seconds_remaining` is a snapshot from fetch time
  // and would otherwise stay frozen between reloads.
  const expiresAt = env.expires_at ? Date.parse(env.expires_at) : NaN;
  const secs = Number.isFinite(expiresAt) ? Math.floor((expiresAt - now) / 1000) : env.seconds_remaining;
  if (env.status === "expired" || secs <= 0) return "Expired";
  // Boundary check is >= so e.g. exactly 60s reads "1m left", not "60s left".
  if (secs >= 86_400) return `${Math.floor(secs / 86_400)}d ${Math.floor((secs % 86_400) / 3600)}h left`;
  if (secs >= 3600) return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m left`;
  if (secs >= 60) return `${Math.floor(secs / 60)}m left`;
  return `${secs}s left`;
}

/** Compact "Xm ago" / "Xh ago" / locale-date label for a list-row timestamp. */
export function formatRelative(iso: string): string {
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    if (diff < 60_000) return "just now";
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return d.toLocaleDateString();
  } catch {
    return iso;
  }
}
