"use client";

import { useParams } from "next/navigation";

import { FileViewerTab } from "@/components/database-view/file-viewer-tab";

/**
 * Files → Browse — columnar field inventory across every file schema in
 * the project. Reuses the existing FileViewerTab implementation
 * unchanged. The Database View now hosts only Database Viewer; this
 * page is the canonical location for file-field browsing.
 */
export default function FilesBrowsePage() {
  const params = useParams();
  const projectId = params.projectId as string;
  return <FileViewerTab projectId={projectId} />;
}
