import { redirect } from "next/navigation";

export default function FilesIndexPage({
  params,
}: {
  params: { projectId: string };
}) {
  // Browse is the most-used entry point — schema listings/upload sit one tab
  // over but rarely need to be the landing surface.
  redirect(`/projects/${params.projectId}/files/browse`);
}
