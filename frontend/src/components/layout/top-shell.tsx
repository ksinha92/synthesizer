"use client";

import { AssistantSidebar } from "@/components/assistant/assistant-sidebar";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { GlobalNavBar } from "@/components/layout/global-nav-bar";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";
import { WorkspaceTabBar } from "@/components/layout/workspace-tab-bar";
import { useAssistantStore } from "@/stores/assistant-store";

interface TopShellProps {
  children: React.ReactNode;
  projectId?: string;
}

export function TopShell({ children, projectId }: TopShellProps) {
  const toggleAssistant = useAssistantStore((s) => s.toggleOpen);

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground focus:text-sm focus:font-medium"
      >
        Skip to content
      </a>

      <GlobalNavBar onAssistantClick={toggleAssistant} />

      {projectId && <WorkspaceTabBar projectId={projectId} />}

      <main id="main-content" className="mx-auto max-w-7xl px-6 py-6">
        <Breadcrumbs />
        {children}
      </main>

      <AssistantSidebar projectId={projectId} />
      <OnboardingWizard />
    </div>
  );
}
