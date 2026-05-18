"use client";

import { AppShell } from "@/components/layout/app-shell";
import { useParams } from "next/navigation";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const projectId = params.projectId as string;

  return <AppShell projectId={projectId}>{children}</AppShell>;
}
