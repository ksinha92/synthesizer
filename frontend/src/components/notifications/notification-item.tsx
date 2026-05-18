"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle, Clock, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface NotificationItemProps {
  id: string;
  // ``warning`` is for terminal-but-partial outcomes — completed_with_warnings
  // jobs use it so the operator gets an "amber needs review" cue, not a red
  // failure cue.
  type: "completed" | "failed" | "info" | "warning";
  message: string;
  projectId?: string;
  jobId?: string;
  read: boolean;
  createdAt: string;
  onRead: () => void;
}

const ICONS = {
  completed: { icon: CheckCircle, color: "text-green-500" },
  failed: { icon: XCircle, color: "text-red-500" },
  warning: { icon: AlertTriangle, color: "text-amber-500" },
  info: { icon: Clock, color: "text-yellow-500" },
};

export function NotificationItem({ type, message, projectId, read, createdAt, onRead }: NotificationItemProps) {
  const { icon: Icon, color } = ICONS[type] || ICONS.info;

  const relTime = new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
    Math.round((new Date(createdAt).getTime() - Date.now()) / 60000), "minute"
  );

  return (
    <button onClick={onRead} className={cn("flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-muted", !read && "bg-primary/5")}>
      <div className="relative mt-0.5">
        <Icon className={cn("h-4 w-4", color)} />
        {!read && <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-primary" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn("text-xs", read ? "text-muted-foreground" : "text-foreground font-medium")}>{message}</p>
        <p className="text-[10px] text-muted-foreground mt-0.5">{relTime}</p>
      </div>
      {projectId && (
        <Link href={`/projects/${projectId}/jobs`} className="text-[10px] text-primary hover:underline shrink-0" onClick={(e) => e.stopPropagation()}>
          View
        </Link>
      )}
    </button>
  );
}
