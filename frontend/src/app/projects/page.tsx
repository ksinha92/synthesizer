"use client";

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { ProjectList } from "@/components/projects/project-list";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { Pagination } from "@/components/common/pagination";
import { useProjectStore } from "@/stores/project-store";

export default function ProjectsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const { fetchProjects, totalCount, currentPage, pageSize } = useProjectStore();

  useEffect(() => {
    fetchProjects(1);
  }, [fetchProjects]);

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-foreground">Projects</h1>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Project
          </button>
        </div>

        <ProjectList onCreateClick={() => setShowCreate(true)} />

        <Pagination
          page={currentPage}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={(page) => fetchProjects(page)}
        />
      </div>

      <CreateProjectDialog open={showCreate} onClose={() => setShowCreate(false)} />
    </AppShell>
  );
}
