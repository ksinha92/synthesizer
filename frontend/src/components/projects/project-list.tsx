"use client";

import { Copy, LayoutGrid, List, Trash2 } from "lucide-react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useProjectStore } from "@/stores/project-store";
import { ProjectCard } from "./project-card";
import { EmptyState } from "@/components/common/empty-state";
import { SkeletonCard } from "@/components/common/skeleton-card";
import { cn } from "@/lib/utils";

interface Project {
  id: string;
  name: string;
  description: string | null;
  updated_at: string;
}

interface ProjectListProps {
  onCreateClick: () => void;
}

export function ProjectList({ onCreateClick }: ProjectListProps) {
  const { projects, viewMode, setViewMode, loading, deleteProject, cloneProject } = useProjectStore();

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <SkeletonCard key={i} className="h-28" />
        ))}
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <EmptyState
        title="No projects yet"
        description="Create your first project to start managing test data."
        action={{ label: "Create Project", onClick: onCreateClick }}
      />
    );
  }

  const columns: ColumnsType<Project> = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (name: string, record) => (
        <a href={`/projects/${record.id}`} className="text-primary hover:underline font-medium">{name}</a>
      ),
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (desc: string | null) => <span className="text-muted-foreground">{desc || "—"}</span>,
    },
    {
      title: "Last Updated",
      dataIndex: "updated_at",
      key: "updated_at",
      sorter: (a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime(),
      render: (t: string) => <span className="text-xs text-muted-foreground">{new Date(t).toLocaleDateString()}</span>,
      width: 140,
    },
    {
      title: "",
      key: "actions",
      width: 110,
      render: (_, record) => (
        <div className="inline-flex items-center gap-1">
          <button
            onClick={() => {
              const name = prompt(
                `Clone "${record.name}" — name for the new workspace?`,
                `${record.name} (copy)`
              );
              if (name === null) return; // user cancelled
              cloneProject(record.id, name.trim() ? { name: name.trim() } : undefined);
            }}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Clone as child workspace"
            aria-label={`Clone ${record.name}`}
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => {
              if (confirm("Delete this project?")) deleteProject(record.id);
            }}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
            title="Delete project"
            aria-label={`Delete ${record.name}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div>
      {/* View toggle */}
      <div className="flex justify-end mb-4">
        <div className="flex items-center gap-0.5 rounded-lg border border-border p-0.5">
          <button
            onClick={() => setViewMode("table")}
            className={cn("rounded-md p-1.5", viewMode === "table" ? "bg-muted" : "")}
            title="Table view"
          >
            <List className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("card")}
            className={cn("rounded-md p-1.5", viewMode === "card" ? "bg-muted" : "")}
            title="Card view"
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
        </div>
      </div>

      {viewMode === "card" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <ProjectCard key={p.id} id={p.id} name={p.name} description={p.description} updated_at={p.updated_at} />
          ))}
        </div>
      ) : (
        <div className="ant-scoped">
          <Table<Project>
            columns={columns}
            dataSource={projects as Project[]}
            rowKey="id"
            pagination={false}
            size="middle"
          />
        </div>
      )}
    </div>
  );
}
