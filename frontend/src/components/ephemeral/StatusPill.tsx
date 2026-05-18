"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { EphemeralEnv } from "./types";

export function StatusPill({ status }: { status: EphemeralEnv["status"] }) {
  const palette: Record<EphemeralEnv["status"], { label: string; tone: string; icon: React.ElementType }> = {
    pending: {
      label: "Pending",
      tone: "bg-[hsl(var(--dw-pill-warning)/0.15)] text-[hsl(var(--dw-pill-warning))]",
      icon: Clock,
    },
    provisioning: {
      label: "Provisioning",
      tone: "bg-[hsl(var(--dw-brand)/0.15)] text-[hsl(var(--dw-brand))]",
      icon: Loader2,
    },
    ready: {
      label: "Ready",
      tone: "bg-[hsl(var(--dw-pill-success)/0.15)] text-[hsl(var(--dw-pill-success))]",
      icon: CheckCircle2,
    },
    expired: {
      label: "Expired",
      tone: "bg-muted text-muted-foreground",
      icon: AlertTriangle,
    },
    revoked: {
      label: "Revoked",
      tone: "bg-muted text-muted-foreground",
      icon: Trash2,
    },
  };
  const { label, tone, icon: Icon } = palette[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        tone
      )}
    >
      <Icon className={cn("h-3 w-3", status === "provisioning" && "animate-spin")} />
      {label}
    </span>
  );
}
