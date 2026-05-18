"use client";

import { useEffect, useState } from "react";
import { Copy, Loader2, Plus, Trash2, Webhook } from "lucide-react";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { Select } from "@/components/common/select";
import { cn } from "@/lib/utils";

interface WebhookEntry {
  id: string;
  url: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

const AVAILABLE_EVENTS = ["job.completed", "job.failed"];

export function WebhookManager() {
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<Array<{ id: string; name: string }>>([]);
  const [webhooks, setWebhooks] = useState<WebhookEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);

  const [newUrl, setNewUrl] = useState("");
  const [newEvents, setNewEvents] = useState<Set<string>>(new Set(AVAILABLE_EVENTS));
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    api.get<{ items: Array<{ id: string; name: string }> }>("/api/v1/projects?page=1&page_size=100")
      .then((data) => setProjects(data.items || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    api.get<{ webhooks: WebhookEntry[] }>(`/api/v1/projects/${projectId}/webhooks`)
      .then((data) => setWebhooks(data.webhooks || []))
      .catch(() => toast.error("Failed to load webhooks"))
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleCreate = async () => {
    if (!newUrl || !projectId) return;
    setCreating(true);
    try {
      const result = await api.post<{ id: string; secret: string }>(`/api/v1/projects/${projectId}/webhooks`, {
        url: newUrl,
        events: Array.from(newEvents),
      });
      setCreatedSecret(result.secret);
      setNewUrl("");
      setShowForm(false);
      toast.success("Webhook created");
      const data = await api.get<{ webhooks: WebhookEntry[] }>(`/api/v1/projects/${projectId}/webhooks`);
      setWebhooks(data.webhooks || []);
    } catch (err) {
      toast.error("Failed to create webhook");
    }
    setCreating(false);
  };

  const handleDelete = async (webhookId: string) => {
    if (!confirm("Delete this webhook? This cannot be undone.")) return;
    try {
      await api.del(`/api/v1/projects/${projectId}/webhooks/${webhookId}`);
      setWebhooks((prev) => prev.filter((w) => w.id !== webhookId));
      toast.success("Webhook deleted");
    } catch {
      toast.error("Failed to delete webhook");
    }
  };

  const copySecret = () => {
    if (createdSecret) {
      navigator.clipboard.writeText(createdSecret);
      toast.info("Secret copied to clipboard");
    }
  };

  return (
    <div className="space-y-4">
      {/* Project selector */}
      <div className="flex items-center gap-3">
        <label htmlFor="webhook-project-select" className="text-sm font-medium text-foreground">
          Project:
        </label>
        <Select
          id="webhook-project-select"
          fullWidth={false}
          selectSize="md"
          value={projectId}
          onChange={(e) => { setProjectId(e.target.value); setCreatedSecret(null); }}
          className="min-w-[260px]"
        >
          <option value="">Select a project…</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </Select>
      </div>

      {!projectId && (
        <p className="py-8 text-center text-sm text-muted-foreground">Select a project to manage webhooks.</p>
      )}

      {/* Secret banner */}
      {createdSecret && (
        <div className="flex items-center gap-3 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-3">
          <span className="text-sm text-yellow-700 dark:text-yellow-400 flex-1">
            Webhook secret (shown once): <code className="font-mono text-xs bg-yellow-500/20 px-1.5 py-0.5 rounded">{createdSecret}</code>
          </span>
          <button onClick={copySecret} className="text-yellow-700 dark:text-yellow-400 hover:opacity-80">
            <Copy className="h-4 w-4" />
          </button>
          <button onClick={() => setCreatedSecret(null)} className="text-yellow-700 dark:text-yellow-400 hover:opacity-80 text-xs">
            Dismiss
          </button>
        </div>
      )}

      {projectId && (
        <>
          {/* Header + Add button */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{webhooks.length} webhook{webhooks.length !== 1 ? "s" : ""} registered</span>
            <button
              onClick={() => setShowForm(!showForm)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" /> Add Webhook
            </button>
          </div>

          {/* Add form */}
          {showForm && (
            <div className="rounded-lg border border-border bg-card p-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Webhook URL</label>
                <input
                  type="url"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://example.com/webhook"
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Events</label>
                <div className="flex gap-3">
                  {AVAILABLE_EVENTS.map((evt) => (
                    <label key={evt} className="flex items-center gap-2 text-sm text-foreground">
                      <input
                        type="checkbox"
                        checked={newEvents.has(evt)}
                        onChange={() => {
                          setNewEvents((prev) => {
                            const next = new Set(prev);
                            if (next.has(evt)) next.delete(evt); else next.add(evt);
                            return next;
                          });
                        }}
                        className="rounded border-input"
                      />
                      {evt}
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowForm(false)} className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Cancel</button>
                <button onClick={handleCreate} disabled={!newUrl || creating} className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create"}
                </button>
              </div>
            </div>
          )}

          {/* Webhook list */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : webhooks.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No webhooks registered for this project.</p>
          ) : (
            <div className="space-y-2">
              {webhooks.map((w) => (
                <div key={w.id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
                  <Webhook className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{w.url}</p>
                    <div className="flex items-center gap-2 mt-1">
                      {w.events.map((evt) => (
                        <span key={evt} className="inline-flex rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{evt}</span>
                      ))}
                      <span className={cn("text-xs", w.is_active ? "text-green-600 dark:text-green-400" : "text-red-500")}>
                        {w.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                  </div>
                  <button onClick={() => handleDelete(w.id)} className="text-muted-foreground hover:text-red-500 shrink-0">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
