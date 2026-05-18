"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Database } from "lucide-react";
import { api } from "@/hooks/use-api";
import { EmptyState } from "@/components/common/empty-state";

interface Project {
  id: string;
  name: string;
  description: string | null;
  updated_at: string;
}

export function RecentProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);

    api.get<{ items: Project[] }>("/api/v1/projects?page=1&page_size=6")
      .then((data) => {
        setProjects(data.items);
        setLoading(false);
      })
      .catch((err) => {
        if (err.message !== "Unauthorized") {
          setError("Unable to load projects");
        }
        setLoading(false);
      })
      .finally(() => clearTimeout(timer));

    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg border border-border bg-muted" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        {error}
        <button onClick={() => window.location.reload()} className="ml-2 underline">Retry</button>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <EmptyState
        icon={Database}
        title="No projects yet"
        description="Create your first project to start managing test data."
      />
    );
  }

  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Link
            key={project.id}
            href={`/projects/${project.id}`}
            className="rounded-lg border border-border bg-card p-4 hover:shadow-md transition-shadow"
          >
            <h3 className="text-sm font-medium text-foreground truncate">{project.name}</h3>
            <p className="mt-1 text-xs text-muted-foreground truncate">
              {project.description || "No description"}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Updated {new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
                Math.round((new Date(project.updated_at).getTime() - Date.now()) / 86400000),
                "day"
              )}
            </p>
          </Link>
        ))}
      </div>
      <Link href="/projects" className="mt-3 inline-flex items-center gap-1 text-sm text-primary hover:underline">
        View all <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}
