"use client";

import { Clock, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusPill } from "./StatusPill";
import { describeTtl, formatRelative } from "./utils";
import type { EphemeralEnv } from "./types";

export function EnvRow({
  env,
  now,
  onRevoke,
}: {
  env: EphemeralEnv;
  now: number;
  onRevoke: () => void;
}) {
  const ttl = describeTtl(env, now);
  const canRevoke = env.status !== "revoked" && env.status !== "expired";

  return (
    <li className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-baseline gap-2">
          <p className="truncate text-sm font-semibold text-foreground">{env.name}</p>
          <StatusPill status={env.status} />
        </div>
        <p className="font-mono text-[11px] text-muted-foreground">
          {env.schema_name ?? "—"}
        </p>
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {ttl}
          </span>
          <span>created {formatRelative(env.created_at)}</span>
        </div>
      </div>
      <div className="shrink-0">
        <button
          type="button"
          onClick={onRevoke}
          disabled={!canRevoke}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border border-border bg-background px-2.5 py-1.5 text-[11px] font-medium",
            canRevoke
              ? "text-foreground hover:bg-muted"
              : "cursor-not-allowed text-muted-foreground opacity-60"
          )}
        >
          <Trash2 className="h-3 w-3" />
          {env.status === "revoked" ? "Revoked" : env.status === "expired" ? "Expired" : "Revoke"}
        </button>
      </div>
    </li>
  );
}
