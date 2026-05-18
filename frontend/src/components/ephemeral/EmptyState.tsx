"use client";

import { Hourglass, Plus } from "lucide-react";

export function EmptyState({ onProvision }: { onProvision: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-12 text-center">
      <Hourglass className="h-8 w-8 text-muted-foreground" />
      <div>
        <p className="text-sm font-medium text-foreground">No ephemeral environments yet</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Provision one to spin up a TTL-bound destination — useful for demo
          fixtures, regression suites, and short-lived QA shares.
        </p>
      </div>
      <button
        type="button"
        onClick={onProvision}
        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
      >
        <Plus className="h-3.5 w-3.5" />
        Provision your first environment
      </button>
    </div>
  );
}
