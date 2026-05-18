"use client";

import Link from "next/link";
import { Database } from "lucide-react";

interface ProjectCardProps {
  id: string;
  name: string;
  description: string | null;
  updated_at: string;
}

export function ProjectCard({ id, name, description, updated_at }: ProjectCardProps) {
  const relativeTime = new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
    Math.round((new Date(updated_at).getTime() - Date.now()) / 86400000),
    "day"
  );

  return (
    <Link
      href={`/projects/${id}`}
      className="rounded-lg border border-border bg-card p-5 hover:shadow-md transition-shadow block"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Database className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-foreground truncate">{name}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground truncate">{description || "No description"}</p>
          <p className="mt-2 text-xs text-muted-foreground">Updated {relativeTime}</p>
        </div>
      </div>
    </Link>
  );
}
