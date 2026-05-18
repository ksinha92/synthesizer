"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Hourglass, Loader2, Plus } from "lucide-react";

import { toast } from "@/components/common/toast";
import { api } from "@/hooks/use-api";
import { useConnectionStore } from "@/stores/connection-store";

import { EmptyState } from "@/components/ephemeral/EmptyState";
import { EnvList } from "@/components/ephemeral/EnvList";
import { ProvisionDialog } from "@/components/ephemeral/ProvisionDialog";
import { RevokeDialog } from "@/components/ephemeral/RevokeDialog";
import type {
  EphemeralEnv,
  EphemeralListResponse,
} from "@/components/ephemeral/types";

/**
 * Ephemeral Environments — T3.1 (Tonic 11.25.00 / 11.35.01 / 11.35.09).
 *
 * Tonic-parity surface that lets a workspace track short-lived destination
 * environments seeded from generation jobs. The data-copy controller is a
 * follow-on (it needs deploy-shape decisions DataWrangler hasn't made
 * yet); this page owns the lifecycle metadata so users get a real list,
 * a real Provision form with TTL, and a real Revoke flow.
 *
 * Sub-components and helpers live under `components/ephemeral/` — see
 * Phase 61 (F19) for the extraction history.
 */
export default function EphemeralPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [envs, setEnvs] = useState<EphemeralEnv[]>([]);
  const [loading, setLoading] = useState(true);
  const [showProvision, setShowProvision] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<EphemeralEnv | null>(null);

  const connections = useConnectionStore((s) => s.connections);
  const fetchConnections = useConnectionStore((s) => s.fetchConnections);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<EphemeralListResponse>(`/api/v1/projects/${projectId}/ephemeral`);
      setEnvs(res.items);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load ephemeral envs");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    reload();
    fetchConnections(projectId).catch(() => {});
  }, [reload, fetchConnections, projectId]);

  // Tick a local clock so TTL counters recompute without polling the
  // server. The interval adapts to the soonest visible expiry so
  // second-level countdowns stay accurate near zero: 1s when any env
  // is in its final minute, 15s in the minutes band, 60s otherwise.
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const computeInterval = () => {
      const t = Date.now();
      let min = Number.POSITIVE_INFINITY;
      for (const env of envs) {
        if (env.status === "revoked" || env.status === "expired") continue;
        const ms = Date.parse(env.expires_at) - t;
        if (ms > 0 && ms < min) min = ms;
      }
      if (!Number.isFinite(min)) return 60_000;
      if (min < 60_000) return 1_000;
      if (min < 3_600_000) return 15_000;
      return 60_000;
    };
    const id = setInterval(() => setNow(Date.now()), computeInterval());
    return () => clearInterval(id);
  }, [envs]);

  const connectionOptions = useMemo(
    () => connections.map((c) => ({ id: c.id, name: c.name })),
    [connections]
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-foreground">
            <Hourglass className="h-5 w-5 text-[hsl(var(--dw-brand))]" />
            Ephemeral Environments
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Short-lived destination environments seeded from generation jobs. Each
            environment expires automatically — extend a TTL by re-provisioning
            from the same job.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowProvision(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:opacity-90"
        >
          <Plus className="h-3.5 w-3.5" />
          Provision environment
        </button>
      </header>

      <section className="rounded-lg border border-border bg-card">
        <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <h2 className="text-sm font-semibold text-foreground">Active &amp; recent</h2>
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {envs.length} env{envs.length === 1 ? "" : "s"}
          </span>
        </header>

        {loading ? (
          <div className="flex items-center justify-center px-4 py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            <span className="text-xs">Loading environments…</span>
          </div>
        ) : envs.length === 0 ? (
          <EmptyState onProvision={() => setShowProvision(true)} />
        ) : (
          <EnvList envs={envs} now={now} onRevoke={setRevokeTarget} />
        )}
      </section>

      {showProvision && (
        <ProvisionDialog
          projectId={projectId}
          connections={connectionOptions}
          onClose={() => setShowProvision(false)}
          onCreated={() => {
            setShowProvision(false);
            reload();
          }}
        />
      )}

      {revokeTarget && (
        <RevokeDialog
          env={revokeTarget}
          projectId={projectId}
          onClose={() => setRevokeTarget(null)}
          onRevoked={() => {
            setRevokeTarget(null);
            reload();
          }}
        />
      )}
    </div>
  );
}
