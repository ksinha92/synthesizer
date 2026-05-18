"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useRef } from "react";
import {
  Database,
  FileBox,
  FileSearch,
  Hourglass,
  LayoutDashboard,
  Lock,
  Network,
  Plug,
  ScrollText,
  Settings,
  Shield,
  Shuffle,
  TestTube,
  Workflow,
} from "lucide-react";

import { GenerateDataButton } from "@/components/common/generate-data-button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface Tab {
  label: string;
  info: string; // one-line description shown under the label in the tooltip
  suffix: string; // path suffix under /projects/[id]
  icon: React.ElementType;
}

// Only tabs whose routes exist today. The empty-string suffix targets the
// project landing page, which serves as the Project Overview dashboard.
// Privacy Hub is now its own route at /projects/[id]/privacy-hub.
const TABS: Tab[] = [
  { label: "Overview", info: "Project summary dashboard", suffix: "", icon: LayoutDashboard },
  { label: "Database View", info: "Explore connected schemas", suffix: "database", icon: Database },
  { label: "Connections", info: "Manage data source connections", suffix: "connections", icon: Plug },
  { label: "Discovery", info: "Auto-detect schemas and PII", suffix: "discovery", icon: FileSearch },
  { label: "Privacy Hub", info: "Review unprotected PII and apply masking", suffix: "privacy-hub", icon: Shield },
  { label: "Masking", info: "Configure column-level masking rules", suffix: "masking", icon: Lock },
  { label: "Synthetic", info: "Generate realistic test data", suffix: "synthetic", icon: TestTube },
  { label: "Files", info: "File schemas, viewer, relationships, mappings, and output", suffix: "files", icon: FileBox },
  { label: "Subsetting", info: "Extract referentially-correct slices", suffix: "subsetting", icon: Shuffle },
  { label: "Workflows", info: "Orchestrate multi-step jobs", suffix: "workflows", icon: Workflow },
  { label: "Jobs", info: "View job status and history", suffix: "jobs", icon: ScrollText },
  { label: "Compliance", info: "GDPR / HIPAA / CCPA reports", suffix: "compliance", icon: Network },
  { label: "Ephemeral", info: "Temporary test databases", suffix: "ephemeral", icon: Hourglass },
  { label: "Settings", info: "Project configuration", suffix: "settings", icon: Settings },
];

interface WorkspaceTabBarProps {
  projectId: string;
}

export function WorkspaceTabBar({ projectId }: WorkspaceTabBarProps) {
  const pathname = usePathname();
  const listRef = useRef<HTMLDivElement>(null);

  const isActive = (suffix: string) => {
    const target = suffix
      ? `/projects/${projectId}/${suffix}`
      : `/projects/${projectId}`;
    if (suffix === "") return pathname === target;
    return pathname === target || pathname.startsWith(`${target}/`);
  };

  // Arrow-key navigation within the tab list.
  const onKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const buttons = Array.from(
      listRef.current?.querySelectorAll<HTMLAnchorElement>('[role="tab"]') ?? []
    );
    const idx = buttons.indexOf(document.activeElement as HTMLAnchorElement);
    if (idx < 0) return;
    const next =
      e.key === "ArrowRight" ? (idx + 1) % buttons.length : (idx - 1 + buttons.length) % buttons.length;
    buttons[next].focus();
    e.preventDefault();
  }, []);

  return (
    <TooltipProvider delayDuration={150} skipDelayDuration={200}>
      <div
        className="sticky top-12 z-30 flex items-center justify-between border-b border-black/20 px-4 bg-[hsl(var(--dw-tabs-bg))] text-[hsl(var(--dw-tabs-fg))]"
      >
        <div
          ref={listRef}
          role="tablist"
          aria-label="Workspace sections"
          onKeyDown={onKeyDown}
          className="flex items-center gap-0.5 overflow-x-auto"
        >
          {TABS.map(({ label, info, suffix, icon: Icon }) => {
            const active = isActive(suffix);
            const href = suffix
              ? `/projects/${projectId}/${suffix}`
              : `/projects/${projectId}`;
            return (
              <Tooltip key={suffix || "overview"}>
                <TooltipTrigger asChild>
                  <Link
                    href={href}
                    role="tab"
                    aria-label={label}
                    aria-selected={active}
                    tabIndex={active ? 0 : -1}
                    className={cn(
                      "inline-flex items-center justify-center border-b-2 px-3 py-2 transition-colors",
                      active
                        ? "border-[hsl(var(--dw-tabs-active))] text-white"
                        : "border-transparent text-[hsl(var(--dw-tabs-fg))] opacity-70 hover:opacity-100"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="bottom" sideOffset={4}>
                  <div className="text-xs font-semibold text-foreground">{label}</div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground">{info}</div>
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>

        <div className="pl-3">
          <GenerateDataButton projectId={projectId} />
        </div>
      </div>
    </TooltipProvider>
  );
}
