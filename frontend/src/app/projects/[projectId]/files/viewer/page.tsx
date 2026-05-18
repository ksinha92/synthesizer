"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { Select } from "@/components/common/select";
import { api } from "@/hooks/use-api";
import { FileSchemaViewer } from "@/components/file-loader/viewer/file-schema-viewer";
import type { FileSchemaSummary } from "@/components/file-loader/types";

/**
 * Files → Viewer — Microfocus-style 3-pane viewer. The schema id can
 * come from the URL (?schema_id=…) so the Schemas tab can deep-link
 * into the viewer with a specific schema selected.
 */
export default function FilesViewerPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const router = useRouter();
  const search = useSearchParams();
  const initialSchemaId = search.get("schema_id");

  const [schemas, setSchemas] = useState<FileSchemaSummary[]>([]);
  const [schemaId, setSchemaId] = useState<string | null>(initialSchemaId);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.get<FileSchemaSummary[]>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas`,
      );
      setSchemas(list);
      if (!schemaId && list.length > 0) {
        // Default to the first schema so the viewer renders something
        // useful instead of an "empty" state when the user lands here
        // without a deep link.
        setSchemaId(list[0].id);
      }
    } finally {
      setLoading(false);
    }
  }, [projectId, schemaId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleChange = (id: string) => {
    setSchemaId(id);
    // Keep the URL in sync so a refresh / share link reopens the same
    // schema. router.replace avoids polluting the back-button history.
    router.replace(`/projects/${projectId}/files/viewer?schema_id=${id}`);
  };

  if (loading) {
    return (
      <p className="text-xs text-muted-foreground">Loading schemas…</p>
    );
  }

  if (schemas.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
        No file schemas in this project yet. Add one from the{" "}
        <a
          href={`/projects/${projectId}/files/schemas`}
          className="text-primary hover:underline"
        >
          Schemas tab
        </a>
        .
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">Schema</span>
        <Select
          fullWidth={false}
          value={schemaId ?? ""}
          onChange={(e) => handleChange(e.target.value)}
          className="min-w-[260px]"
        >
          {schemas.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.file_format})
            </option>
          ))}
        </Select>
      </label>
      {schemaId && <FileSchemaViewer projectId={projectId} schemaId={schemaId} />}
    </div>
  );
}
