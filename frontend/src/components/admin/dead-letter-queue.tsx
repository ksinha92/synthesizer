"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, RotateCcw, XCircle } from "lucide-react";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { cn } from "@/lib/utils";

interface DLQEntry {
  id: string;
  original_job_id: string;
  job_type: string;
  error_message: string | null;
  retry_count: number;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
}

export function DeadLetterQueue() {
  const [entries, setEntries] = useState<DLQEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  const fetchDLQ = async (p: number) => {
    setLoading(true);
    try {
      const data = await api.get<{ items: DLQEntry[]; total: number }>(
        `/api/v1/admin/dead-letter-jobs?page=${p}&page_size=${pageSize}`
      );
      setEntries(data.items || []);
      setTotal(data.total);
    } catch {
      toast.error("Failed to load dead letter queue");
    }
    setLoading(false);
  };

  useEffect(() => { fetchDLQ(page); }, [page]);

  const handleResolve = async (id: string) => {
    try {
      await api.post(`/api/v1/admin/dead-letter-jobs/${id}/resolve`);
      toast.success("Entry marked as resolved");
      fetchDLQ(page);
    } catch {
      toast.error("Failed to resolve entry");
    }
  };

  const handleRetry = async (id: string) => {
    try {
      await api.post(`/api/v1/admin/dead-letter-jobs/${id}/retry`);
      toast.success("Job retried successfully");
      fetchDLQ(page);
    } catch {
      toast.error("Failed to retry job");
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{total} entr{total !== 1 ? "ies" : "y"} in dead letter queue</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : entries.length === 0 ? (
        <div className="py-12 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-green-500/50 mb-3" />
          <p className="text-sm text-muted-foreground">Dead letter queue is empty. No failed jobs to review.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Job ID</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Type</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Error</th>
                <th className="px-4 py-2.5 text-center font-medium text-muted-foreground">Retries</th>
                <th className="px-4 py-2.5 text-center font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">Created</th>
                <th className="px-4 py-2.5 text-center font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entries.map((entry) => (
                <tr key={entry.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-mono text-xs text-foreground">
                    {entry.original_job_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground capitalize">
                      {entry.job_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-foreground max-w-xs truncate" title={entry.error_message || ""}>
                    {entry.error_message || "—"}
                  </td>
                  <td className="px-4 py-3 text-center text-xs text-muted-foreground">
                    {entry.retry_count}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {entry.resolved_at ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-xs text-green-600 dark:text-green-400">
                        <CheckCircle2 className="h-3 w-3" /> Resolved
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-xs text-red-600 dark:text-red-400">
                        <AlertCircle className="h-3 w-3" /> Unresolved
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(entry.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {!entry.resolved_at && (
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => handleRetry(entry.id)}
                          title="Retry job"
                          className="rounded p-1 text-blue-600 hover:bg-blue-500/10 dark:text-blue-400"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleResolve(entry.id)}
                          title="Mark as resolved"
                          className="rounded p-1 text-green-600 hover:bg-green-500/10 dark:text-green-400"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs text-muted-foreground">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
