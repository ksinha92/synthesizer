"use client";

import { TopShell } from "./top-shell";

interface AppShellProps {
  children: React.ReactNode;
  projectId?: string;
}

/**
 * Thin alias kept for backward compatibility — every existing page still
 * imports { AppShell }. Internally delegates to the new TopShell.
 */
export function AppShell({ children, projectId }: AppShellProps) {
  return <TopShell projectId={projectId}>{children}</TopShell>;
}
