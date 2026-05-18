"use client";

import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import {
  Database,
  FileSearch,
  FileText,
  Link2,
  Package,
  Workflow,
} from "lucide-react";

import { cn } from "@/lib/utils";

const TABS = [
  {
    id: "schemas",
    label: "Schemas",
    icon: FileText,
    description: "Upload, edit, and manage file schemas.",
  },
  {
    id: "viewer",
    label: "Viewer",
    icon: Database,
    description: "Inspect a schema's structure and sample data.",
  },
  {
    id: "browse",
    label: "Browse",
    icon: FileSearch,
    description: "Columnar field inventory across all file schemas.",
  },
  {
    id: "relationships",
    label: "Relationships",
    icon: Link2,
    description: "Auto-detect and manage cross-file FKs.",
  },
  {
    id: "mappings",
    label: "Mappings",
    icon: Workflow,
    description: "Derive new schemas via the data dictionary mapper.",
  },
  {
    id: "output",
    label: "Output",
    icon: Package,
    description: "Build file sets and generate output bundles.",
  },
] as const;

export default function FilesLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const projectId = params.projectId as string;
  const pathname = usePathname();

  // Resolve the active tab by matching the last path segment.
  const activeTab =
    TABS.find((t) => pathname.includes(`/files/${t.id}`))?.id ?? "browse";

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-foreground">Files</h1>
        <p className="text-xs text-muted-foreground">
          Workspace for everything file-based — schemas, viewer, relationships,
          mappings, and output generation. The previous File Viewer tab on the
          Database View and the File output mode on Synthetic have moved here.
        </p>
      </header>

      <nav
        role="tablist"
        aria-label="Files area tabs"
        className="flex flex-wrap border-b border-border"
      >
        {TABS.map(({ id, label, icon: Icon, description }) => {
          const active = activeTab === id;
          return (
            <Link
              key={id}
              role="tab"
              aria-selected={active}
              href={`/projects/${projectId}/files/${id}`}
              title={description}
              className={cn(
                "inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary",
                active
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div role="tabpanel" className="pt-1">
        {children}
      </div>
    </div>
  );
}
