"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { toast } from "@/components/common/toast";
import { api } from "@/hooks/use-api";
import type { EphemeralEnv } from "./types";

export function RevokeDialog({
  env,
  projectId,
  onClose,
  onRevoked,
}: {
  env: EphemeralEnv;
  projectId: string;
  onClose: () => void;
  onRevoked: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const confirm = async () => {
    setBusy(true);
    try {
      await api.del(`/api/v1/projects/${projectId}/ephemeral/${env.id}`);
      toast.success(`Revoked "${env.name}"`);
      onRevoked();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to revoke");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50" onClick={onClose} />
      <AccessibleDialog
        open
        onClose={onClose}
        titleId="ephemeral-revoke-title"
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-card shadow-xl"
      >
        <div className="px-5 py-4">
          <h2 id="ephemeral-revoke-title" className="text-sm font-semibold text-foreground">
            Revoke environment?
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{env.name}</span> will be marked revoked.
            The record stays in the audit log; re-provisioning creates a new environment.
          </p>
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-border bg-muted/30 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md bg-[hsl(var(--dw-pill-warning))] px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy && <Loader2 className="h-3 w-3 animate-spin" />}
            Revoke
          </button>
        </footer>
      </AccessibleDialog>
    </>
  );
}
