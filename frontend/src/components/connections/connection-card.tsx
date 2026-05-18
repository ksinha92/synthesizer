"use client";

import { Database, Cloud, Loader2, Trash2, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_DOT: Record<string, string> = {
  connected: "bg-green-500",
  untested: "bg-yellow-500",
  failed: "bg-red-500",
  disabled: "bg-gray-400",
};

const CONNECTOR_ICONS: Record<string, typeof Database> = {
  postgresql: Database,
  mysql: Database,
  mongodb: Database,
  snowflake: Cloud,
};

interface ConnectionCardProps {
  id: string;
  name: string;
  connector_type: string;
  host: string;
  port: number;
  database_name: string;
  status: string;
  last_tested_at: string | null;
  testing: boolean;
  testResult?: { success: boolean; latency_ms: number } | null;
  onTest: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export function ConnectionCard({
  name, connector_type, host, port, database_name, status,
  last_tested_at, testing, testResult, onTest, onEdit, onDelete,
}: ConnectionCardProps) {
  const Icon = CONNECTOR_ICONS[connector_type] || Database;
  const dotColor = STATUS_DOT[status] || STATUS_DOT.untested;

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-foreground truncate">{name}</h3>
            <span className={cn("h-2 w-2 rounded-full shrink-0", dotColor)} title={status} />
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground font-mono truncate">
            {connector_type}://{host}:{port}/{database_name}
          </p>
          {last_tested_at && (
            <p className="mt-1 text-xs text-muted-foreground">
              Last tested: {new Date(last_tested_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {/* Test result inline */}
      {testResult && (
        <div className={cn(
          "mt-3 rounded-md px-3 py-1.5 text-xs",
          testResult.success ? "bg-green-500/10 text-green-700 dark:text-green-400" : "bg-red-500/10 text-red-700 dark:text-red-400"
        )}>
          {testResult.success ? `Connected (${testResult.latency_ms}ms)` : "Connection failed"}
        </div>
      )}

      {/* Actions */}
      <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
        <button
          onClick={onTest}
          disabled={testing}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted transition-colors disabled:opacity-50"
        >
          {testing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
          {testing ? "Testing..." : "Test"}
        </button>
        <button
          onClick={onEdit}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted transition-colors"
        >
          Edit
        </button>
        <button
          onClick={() => { if (confirm("Delete this connection?")) onDelete(); }}
          className="ml-auto text-muted-foreground hover:text-destructive transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
