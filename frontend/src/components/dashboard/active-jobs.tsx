"use client";

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { api } from "@/hooks/use-api";
import { EmptyState } from "@/components/common/empty-state";
import { cn } from "@/lib/utils";

interface Job {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  started_at: string | null;
}

export function ActiveJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchActive = async () => {
      try {
        // Fetch running/pending jobs across all projects (uses first project for now)
        const projects = await api.get<{ items: { id: string }[] }>("/api/v1/projects?page=1&page_size=1");
        if (projects.items.length > 0) {
          const data = await api.get<{ items: Job[] }>(
            `/api/v1/projects/${projects.items[0].id}/jobs?status=running&page_size=5`
          );
          setJobs(data.items);
        }
      } catch { /* */ }
      setLoading(false);
    };

    fetchActive();
    const interval = setInterval(fetchActive, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="py-4 text-center text-xs text-muted-foreground">Loading...</div>;

  if (jobs.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No active jobs"
        description="Jobs will appear here when you run discovery, masking, or generation."
      />
    );
  }

  return (
    <div className="space-y-2">
      {jobs.map((job) => (
        <div key={job.id} className="flex items-center gap-3">
          <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
            <div className="h-full rounded-full bg-blue-500 animate-pulse transition-all" style={{ width: `${job.progress}%` }} />
          </div>
          <span className="text-xs text-muted-foreground whitespace-nowrap">{job.progress}%</span>
          <span className="text-xs text-foreground capitalize">{job.job_type}</span>
        </div>
      ))}
    </div>
  );
}
