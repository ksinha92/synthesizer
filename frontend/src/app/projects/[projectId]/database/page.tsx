"use client";

import { useParams } from "next/navigation";

import { DatabaseViewerTab } from "@/components/database-view/database-viewer-tab";

/**
 * Database View page — DB-only after the Files IA migration. File-schema
 * browsing, viewing, relationships, mappings, and output generation all
 * live under the dedicated Files workspace area now.
 */
export default function DatabaseViewPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Database View</h1>
        <p className="text-xs text-muted-foreground">
          Browse columns from connected sources and assign masking rules
          inline.
        </p>
      </header>
      <DatabaseViewerTab projectId={projectId} />
    </div>
  );
}
