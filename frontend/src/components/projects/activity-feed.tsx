"use client";

import { useEffect, useState } from "react";
import { Activity, Database, FileSearch, Lock, Play } from "lucide-react";
import { api } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

interface AuditEntry { action: string; user_id: string | null; created_at: string; resource_type: string | null; }

const ACTION_ICONS: Record<string, { icon: typeof Activity; color: string }> = {
  "POST /discovery": { icon: FileSearch, color: "text-blue-500 bg-blue-500/10" },
  "POST /masking": { icon: Lock, color: "text-orange-500 bg-orange-500/10" },
  "POST /synthetic": { icon: Database, color: "text-green-500 bg-green-500/10" },
  "POST /workflows": { icon: Play, color: "text-purple-500 bg-purple-500/10" },
};

function getActionDisplay(action: string) {
  for (const [prefix, meta] of Object.entries(ACTION_ICONS)) {
    if (action.startsWith(prefix)) return meta;
  }
  return { icon: Activity, color: "text-muted-foreground bg-muted" };
}

export function ActivityFeed({ projectId }: { projectId: string }) {
  const [events, setEvents] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<{ logs: AuditEntry[] }>(`/api/v1/admin/audit-logs?project_id=${projectId}&page_size=10`)
      .then((data) => setEvents(data.logs))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <div className="py-4 text-center text-xs text-muted-foreground">Loading activity...</div>;
  if (events.length === 0) return <div className="py-4 text-center text-xs text-muted-foreground">No recent activity</div>;

  return (
    <div className="space-y-0">
      {events.map((event, i) => {
        const { icon: Icon, color } = getActionDisplay(event.action);
        const relTime = new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
          Math.round((new Date(event.created_at).getTime() - Date.now()) / 3600000), "hour"
        );

        return (
          <div key={i} className="flex items-start gap-3 py-2">
            <div className="relative">
              <div className={cn("flex h-7 w-7 items-center justify-center rounded-full", color)}>
                <Icon className="h-3.5 w-3.5" />
              </div>
              {i < events.length - 1 && <div className="absolute left-3.5 top-7 h-full w-px bg-border" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-foreground">{event.action}</p>
              <p className="text-[10px] text-muted-foreground">{event.user_id?.slice(0, 8) || "system"} · {relTime}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
