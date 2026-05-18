"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Bell,
  Database,
  Loader2,
  Settings as SettingsIcon,
  Shield,
} from "lucide-react";

import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { useProjectStore } from "@/stores/project-store";

/**
 * Workspace Settings page — Tonic-parity T2.5 (screenshots 11.23.21 /
 * 11.24.19). Consolidates per-project administration that today lives in
 * a mix of admin pages and inline drawers.
 *
 * Current sections:
 *  - Workspace details (rename / re-describe via PUT /projects/{id}).
 *  - Source settings → deep-link to Connections tab; the SSL/Kerberos
 *    fields land on the connection drawer (T2.1) rather than here so
 *    they stay co-located with the connector that uses them.
 *  - Destination settings → placeholder pending T3.1 (Ephemeral) and
 *    subset output_mode polish.
 *  - Webhooks → uses the existing /projects/{id}/webhooks API to scope
 *    the prior admin-only widget to a single project.
 */

interface WebhookEntry {
  id: string;
  url: string;
  events: string[];
  is_active: boolean;
}

export default function WorkspaceSettingsPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
            <SettingsIcon className="h-5 w-5 text-[hsl(var(--dw-brand))]" />
            Workspace Settings
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Per-project configuration. Global rules and presets live in the top nav.
          </p>
        </div>
      </header>

      <DetailsSection projectId={projectId} />
      <SourceSettingsSection projectId={projectId} />
      <DestinationSettingsSection projectId={projectId} />
      <WebhooksSection projectId={projectId} />
    </div>
  );
}

// ── Workspace details ──────────────────────────────────────────────────────
function DetailsSection({ projectId }: { projectId: string }) {
  const fetchProject = useProjectStore((s) => s.fetchProject);
  const updateProject = useProjectStore((s) => s.updateProject);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchProject(projectId).then((p) => {
      if (cancelled) return;
      if (p) {
        setName(p.name);
        setDescription(p.description ?? "");
      }
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [projectId, fetchProject]);

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Workspace name cannot be empty");
      return;
    }
    setSaving(true);
    const updated = await updateProject(projectId, {
      name: name.trim(),
      description: description.trim(),
    });
    setSaving(false);
    if (updated) {
      // Toast handled inside the store.
    }
  };

  return (
    <Section title="Workspace details" description="Visible to anyone with access to this workspace.">
      {loading ? (
        <p className="text-xs text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-3 max-w-xl">
          <div>
            <label htmlFor="ws-name" className="block text-xs font-medium text-foreground mb-1">
              Name *
            </label>
            <input
              id="ws-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="ws-desc" className="block text-xs font-medium text-foreground mb-1">
              Description
            </label>
            <textarea
              id="ws-desc"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90 disabled:opacity-50"
            >
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Save workspace details
            </button>
          </div>
        </div>
      )}
    </Section>
  );
}

// ── Source settings (deep-link) ────────────────────────────────────────────
function SourceSettingsSection({ projectId }: { projectId: string }) {
  return (
    <Section title="Source settings" description="Connection-level options including SSL/TLS, Kerberos, and schema-change behaviour.">
      <div className="flex items-start gap-3 rounded-md border border-border bg-muted/20 px-4 py-3">
        <Database className="mt-0.5 h-4 w-4 text-[hsl(var(--dw-brand))]" />
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">Manage on the Connections tab</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Source-level toggles live next to each connection so you can tune them per environment
            without leaving this workspace.
          </p>
        </div>
        <Link
          href={`/projects/${projectId}/connections`}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted"
        >
          Open Connections
        </Link>
      </div>
    </Section>
  );
}

// ── Destination settings (placeholder) ─────────────────────────────────────
function DestinationSettingsSection({ projectId }: { projectId: string }) {
  return (
    <Section title="Destination settings" description="Where generated data lands when a job completes.">
      <div className="flex items-start gap-3 rounded-md border border-border bg-muted/20 px-4 py-3">
        <Shield className="mt-0.5 h-4 w-4 text-[hsl(var(--dw-brand))]" />
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">Configured per generation config</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Synthetic and subsetting configs each choose between <code className="font-mono text-[10px]">same_database</code>,
            <code className="ml-1 font-mono text-[10px]">different_connection</code>,
            <code className="ml-1 font-mono text-[10px]">download_zip</code>, and
            <code className="ml-1 font-mono text-[10px]">s3</code>. Workspace-wide defaults arrive with the Ephemeral rollout.
          </p>
        </div>
        <Link
          href={`/projects/${projectId}/synthetic`}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted"
        >
          Open Synthetic
        </Link>
      </div>
    </Section>
  );
}

// ── Webhooks ───────────────────────────────────────────────────────────────
function WebhooksSection({ projectId }: { projectId: string }) {
  const [webhooks, setWebhooks] = useState<WebhookEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newUrl, setNewUrl] = useState("");

  const refresh = async () => {
    setLoading(true);
    try {
      const res = await api.get<{ webhooks: WebhookEntry[] }>(
        `/api/v1/projects/${projectId}/webhooks`
      );
      setWebhooks(res.webhooks ?? []);
    } catch {
      setWebhooks([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const handleCreate = async () => {
    if (!newUrl.trim()) return;
    setCreating(true);
    try {
      const res = await api.post<{ id: string; secret: string }>(
        `/api/v1/projects/${projectId}/webhooks`,
        { url: newUrl.trim() }
      );
      toast.success(
        `Webhook created. Secret (save it — won't be shown again): ${res.secret.slice(0, 12)}…`
      );
      setNewUrl("");
      await refresh();
    } catch {
      toast.error("Failed to create webhook");
    }
    setCreating(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this webhook?")) return;
    try {
      await api.del(`/api/v1/projects/${projectId}/webhooks/${id}`);
      toast.success("Webhook deleted");
      await refresh();
    } catch {
      toast.error("Failed to delete webhook");
    }
  };

  return (
    <Section title="Webhooks" description="Fired on job.completed and job.failed events. The signing secret is shown once on create.">
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="url"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            placeholder="https://example.com/webhook"
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm"
          />
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating || !newUrl.trim()}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
          >
            {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            <Bell className="h-3.5 w-3.5" />
            Add webhook
          </button>
        </div>

        {loading ? (
          <p className="text-xs text-muted-foreground">Loading webhooks…</p>
        ) : webhooks.length === 0 ? (
          <p className="rounded-md border border-dashed border-border bg-muted/10 px-3 py-2 text-xs text-muted-foreground">
            No webhooks yet. Add one above to receive event callbacks.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border">
            {webhooks.map((w) => (
              <li key={w.id} className="flex items-center gap-3 px-3 py-2 text-xs">
                <span
                  className={
                    w.is_active
                      ? "h-1.5 w-1.5 rounded-full bg-[hsl(var(--dw-pill-success))]"
                      : "h-1.5 w-1.5 rounded-full bg-muted-foreground"
                  }
                />
                <span className="flex-1 truncate font-mono text-foreground">{w.url}</span>
                <span className="text-[10px] text-muted-foreground">{w.events.join(", ")}</span>
                <button
                  type="button"
                  onClick={() => handleDelete(w.id)}
                  className="rounded-md border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-destructive"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}

// ── Layout primitive ──────────────────────────────────────────────────────
function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <header className="border-b border-border px-5 py-3">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </header>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}
