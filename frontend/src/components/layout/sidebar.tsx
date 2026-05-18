"use client";

import {
  ChevronLeft,
  ChevronRight,
  FileBox,
  FileSearch,
  Home,
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
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const globalNav: NavItem[] = [
  { label: "Home", href: "/", icon: Home },
  { label: "Projects", href: "/projects", icon: LayoutDashboard },
  { label: "Admin", href: "/admin", icon: Settings },
];

const projectNav: NavItem[] = [
  { label: "Overview", href: "", icon: LayoutDashboard },
  { label: "Connections", href: "connections", icon: Plug },
  { label: "Discovery", href: "discovery", icon: FileSearch },
  { label: "Privacy Hub", href: "privacy-hub", icon: Shield },
  { label: "Masking", href: "masking", icon: Lock },
  { label: "Synthetic", href: "synthetic", icon: TestTube },
  { label: "Files", href: "files", icon: FileBox },
  { label: "Subsetting", href: "subsetting", icon: Shuffle },
  { label: "Workflows", href: "workflows", icon: Workflow },
  { label: "Jobs", href: "jobs", icon: ScrollText },
  { label: "Compliance", href: "compliance", icon: Network },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  projectId?: string;
}

export function Sidebar({ collapsed, onToggle, projectId }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-30 flex h-screen flex-col border-r border-border bg-card transition-all duration-200",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo area */}
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">
          S
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold text-foreground">Synthia</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {/* Global nav */}
        {globalNav.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            isActive={pathname === item.href}
            collapsed={collapsed}
          />
        ))}

        {/* Project-scoped nav */}
        {projectId && (
          <>
            <div className="my-3 border-t border-border" />
            {!collapsed && (
              <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Project
              </p>
            )}
            {projectNav.map((item) => {
              const isOverview = item.href === "";
              const href = isOverview
                ? `/projects/${projectId}`
                : `/projects/${projectId}/${item.href}`;
              const isActive = isOverview
                ? pathname === href
                : pathname.startsWith(href);
              return (
                <NavLink
                  key={item.href || "overview"}
                  item={{ ...item, href }}
                  isActive={isActive}
                  collapsed={collapsed}
                />
              );
            })}
          </>
        )}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="flex h-10 items-center justify-center border-t border-border text-muted-foreground hover:text-foreground transition-colors"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </aside>
  );
}

function NavLink({
  item,
  isActive,
  collapsed,
}: {
  item: NavItem;
  isActive: boolean;
  collapsed: boolean;
}) {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        isActive
          ? "border-l-2 border-primary bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
        collapsed && "justify-center px-0"
      )}
      title={collapsed ? item.label : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{item.label}</span>}
    </Link>
  );
}
