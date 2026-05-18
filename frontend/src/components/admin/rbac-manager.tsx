"use client";

import { useEffect, useState } from "react";
import { Loader2, Plus, Trash2, Users } from "lucide-react";
import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { api } from "@/hooks/use-api";
import { EmptyState } from "@/components/common/empty-state";
import { Select } from "@/components/common/select";
import { useAuthStore } from "@/stores/auth-store";

interface Member {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  added_at: string;
}

const ROLES = ["admin", "editor", "viewer"] as const;

const ROLE_COLORS: Record<string, string> = {
  admin: "red",
  editor: "blue",
  viewer: "default",
};

const PERMISSIONS = [
  ["View projects/data", true, true, true],
  ["Create/edit connections", true, true, false],
  ["Run discovery/masking/generation", true, true, false],
  ["Manage masking policies", true, true, false],
  ["Execute workflows", true, true, false],
  ["Delete projects", true, false, false],
  ["Manage users/roles", true, false, false],
  ["View audit logs", true, false, false],
  ["Generate compliance reports", true, true, false],
] as const;

export function RBACManager() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [inviting, setInviting] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  // Single inline-error slot for any failed admin action. Previously every
  // catch swallowed silently, so the user couldn't tell self-demotion /
  // last-admin / 403s apart from a no-op.
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const messageFromError = (e: unknown, fallback: string) =>
    e instanceof Error && e.message ? e.message : fallback;

  // Caller's own user id — used to disable role-update + remove on the
  // caller's own row so they can't lock themselves out from the UI. The
  // backend enforces this too (self_demotion_forbidden / self_removal_forbidden);
  // disabling the controls just makes the policy visible.
  const currentUserId = useAuthStore((s) => s.user?.id);

  // ── Members fetching ──────────────────────────────────────────────────
  //
  // fetchMembers is intentionally NOT in charge of writing the action-error
  // state. It returns its own status; callers decide how to combine action
  // outcomes with refresh outcomes.
  //
  // Lifecycle contract (action handlers):
  //   - On entry: clear errorMsg (start of attempt).
  //   - On action SUCCESS: await fetchMembers(). If the refresh failed, the
  //     stored member list is now stale — surface "saved, but couldn't
  //     refresh" so the dropdown that appears to have reverted isn't
  //     mistaken for the action having silently failed.
  //   - On action FAILURE: best-effort refresh to revert any optimistic UI,
  //     then set errorMsg with the action's reason (action error wins over
  //     any refresh error — it's the more actionable one).
  type RefreshResult = { ok: true } | { ok: false; error: string };

  const fetchMembers = async (): Promise<RefreshResult> => {
    setLoading(true);
    try {
      const data = await api.get<{ members: Member[] }>("/api/v1/admin/members");
      setMembers(data.members);
      setLoading(false);
      return { ok: true };
    } catch (e) {
      setLoading(false);
      return { ok: false, error: messageFromError(e, "Couldn't load team members.") };
    }
  };

  useEffect(() => {
    (async () => {
      const refresh = await fetchMembers();
      if (!refresh.ok) setErrorMsg(refresh.error);
    })();
  }, []);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setErrorMsg(null);
    try {
      await api.post("/api/v1/admin/members", { email: inviteEmail.trim(), role: inviteRole });
      setInviteEmail("");
      setShowInvite(false);
      const refresh = await fetchMembers();
      if (!refresh.ok) {
        setErrorMsg(`Member added, but the list couldn't be refreshed: ${refresh.error}`);
      }
    } catch (e) {
      setErrorMsg(messageFromError(e, "Couldn't add member."));
    }
    setInviting(false);
  };

  const handleRoleChange = async (memberId: string, newRole: string) => {
    setErrorMsg(null);
    try {
      await api.put(`/api/v1/admin/members/${memberId}`, { role: newRole });
      const refresh = await fetchMembers();
      if (!refresh.ok) {
        setErrorMsg(`Role updated, but the list couldn't be refreshed: ${refresh.error}`);
      }
    } catch (e) {
      // Best-effort revert of the dropdown via refresh. Action error wins
      // over any refresh error — set it last so it's the rendered message.
      await fetchMembers();
      setErrorMsg(messageFromError(e, "Couldn't update role."));
    }
  };

  const handleRemove = async (memberId: string) => {
    if (!confirm("Remove this member?")) return;
    setErrorMsg(null);
    try {
      await api.del(`/api/v1/admin/members/${memberId}`);
      const refresh = await fetchMembers();
      if (!refresh.ok) {
        setErrorMsg(`Member removed, but the list couldn't be refreshed: ${refresh.error}`);
      }
    } catch (e) {
      await fetchMembers();
      setErrorMsg(messageFromError(e, "Couldn't remove member."));
    }
  };

  const memberColumns: ColumnsType<Member> = [
    {
      title: "Name",
      dataIndex: "full_name",
      key: "full_name",
      render: (name: string | null, record) => (
        <div>
          <p className="text-sm font-medium text-foreground">{name || record.email}</p>
          {name && <p className="text-xs text-muted-foreground">{record.email}</p>}
        </div>
      ),
    },
    {
      title: "Role",
      dataIndex: "role",
      key: "role",
      width: 150,
      render: (role: string, record) => {
        const isSelf = currentUserId === record.id;
        return (
          <Select
            aria-label={`Role for ${record.email}`}
            fullWidth={false}
            value={role}
            disabled={isSelf}
            title={isSelf ? "You can't change your own role. Ask another admin." : undefined}
            onChange={(e) => handleRoleChange(record.id, e.target.value)}
            className="min-w-[120px]"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
            ))}
          </Select>
        );
      },
    },
    {
      title: "Added",
      dataIndex: "added_at",
      key: "added_at",
      width: 120,
      render: (t: string) => <span className="text-xs text-muted-foreground">{new Date(t).toLocaleDateString()}</span>,
    },
    {
      title: "",
      key: "actions",
      width: 50,
      render: (_, record) => {
        const isSelf = currentUserId === record.id;
        return (
          <button
            type="button"
            onClick={() => handleRemove(record.id)}
            disabled={isSelf}
            title={isSelf ? "You can't remove your own account. Ask another admin." : "Remove member"}
            className="text-muted-foreground hover:text-destructive disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-muted-foreground"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Member management */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-foreground">Team Members</h4>
          <button
            onClick={() => setShowInvite(!showInvite)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-3 w-3" /> Invite Member
          </button>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="flex items-start justify-between gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
          >
            <span>{errorMsg}</span>
            <button
              type="button"
              onClick={() => setErrorMsg(null)}
              className="shrink-0 font-medium hover:underline"
              aria-label="Dismiss"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Invite form */}
        {showInvite && (
          <div className="flex items-end gap-2 rounded-lg border border-border bg-muted/30 p-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-foreground mb-1">Email</label>
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="user@ameritas.com"
                className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <Select
                label="Role"
                fullWidth
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                selectSize="md"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
                ))}
              </Select>
            </div>
            <button
              onClick={handleInvite}
              disabled={inviting || !inviteEmail.trim()}
              className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {inviting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
            </button>
          </div>
        )}

        {/* Member list */}
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" />)}
          </div>
        ) : members.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No team members"
            description="Invite team members to collaborate on projects."
          />
        ) : (
          <div className="ant-scoped">
            <Table<Member>
              columns={memberColumns}
              dataSource={members}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </div>
        )}
      </div>

      {/* Permission matrix (reference) */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h4 className="text-sm font-medium text-foreground mb-2">Role Permissions</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left">Permission</th>
                <th className="px-3 py-2 text-center">Admin</th>
                <th className="px-3 py-2 text-center">Editor</th>
                <th className="px-3 py-2 text-center">Viewer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {PERMISSIONS.map(([perm, admin, editor, viewer], i) => (
                <tr key={i}>
                  <td className="px-3 py-1.5 text-foreground">{perm as string}</td>
                  <td className="px-3 py-1.5 text-center">{admin ? "✓" : "—"}</td>
                  <td className="px-3 py-1.5 text-center">{editor ? "✓" : "—"}</td>
                  <td className="px-3 py-1.5 text-center">{viewer ? "✓" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
