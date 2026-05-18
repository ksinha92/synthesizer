"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { Select } from "@/components/common/select";
import { toast } from "@/components/common/toast";
import { api } from "@/hooks/use-api";
import type { ConnectionOption, EphemeralEnv } from "./types";
import { TTL_OPTIONS } from "./types";

export function ProvisionDialog({
  projectId,
  connections,
  onClose,
  onCreated,
}: {
  projectId: string;
  connections: ConnectionOption[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [destinationId, setDestinationId] = useState<string>("");
  const [ttlDays, setTtlDays] = useState<number>(7);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Environment name is required");
      return;
    }
    setSubmitting(true);
    try {
      await api.post<EphemeralEnv>(`/api/v1/projects/${projectId}/ephemeral`, {
        name: name.trim(),
        destination_connection_id: destinationId || null,
        ttl_days: ttlDays,
      });
      toast.success(`Provisioned "${name.trim()}" — expires in ${ttlDays} day${ttlDays === 1 ? "" : "s"}`);
      onCreated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to provision environment");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50" onClick={onClose} />
      <AccessibleDialog
        open
        onClose={onClose}
        titleId="ephemeral-provision-title"
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-card shadow-xl"
      >
        <form onSubmit={submit} className="flex flex-col">
          <header className="border-b border-border px-5 py-3">
            <h2 id="ephemeral-provision-title" className="text-sm font-semibold text-foreground">
              Provision ephemeral environment
            </h2>
            <p className="mt-1 text-[11px] text-muted-foreground">
              The environment starts in <span className="font-medium text-foreground">Pending</span> —
              the data-copy controller is a follow-on. TTL countdown begins immediately.
            </p>
          </header>

          <div className="space-y-3 px-5 py-4">
            <label className="block">
              <span className="text-xs font-medium text-foreground">Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="qa-fixture-2026-q2"
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:border-[hsl(var(--dw-brand))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--dw-brand))]"
                required
                maxLength={255}
                autoFocus
              />
            </label>

            <label className="block">
              <span className="text-xs font-medium text-foreground">
                Destination connection <span className="text-muted-foreground">(optional)</span>
              </span>
              <Select
                value={destinationId}
                onChange={(e) => setDestinationId(e.target.value)}
                className="mt-1 w-full"
              >
                <option value="">— No destination yet —</option>
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
              <span className="mt-1 block text-[10px] text-muted-foreground">
                Must already belong to this workspace. Leave blank if the controller
                will create one later.
              </span>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-foreground">TTL</span>
              <Select
                value={String(ttlDays)}
                onChange={(e) => setTtlDays(Number(e.target.value))}
                className="mt-1 w-full"
              >
                {TTL_OPTIONS.map((days) => (
                  <option key={days} value={days}>
                    {days} day{days === 1 ? "" : "s"}
                  </option>
                ))}
              </Select>
            </label>
          </div>

          <footer className="flex items-center justify-end gap-2 border-t border-border bg-muted/30 px-5 py-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting && <Loader2 className="h-3 w-3 animate-spin" />}
              Provision
            </button>
          </footer>
        </form>
      </AccessibleDialog>
    </>
  );
}
