"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Database,
  FileSearch,
  Home,
  Hourglass,
  LayoutDashboard,
  Lock,
  Network,
  ScrollText,
  Search,
  Settings,
  Shield,
  ShieldAlert,
  Shuffle,
  TestTube,
  Workflow,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface PaletteEntry {
  label: string;
  href: string;
  icon: React.ElementType;
  keywords: string;
  scope: "global" | "project";
}

// Global entries — always present, point at existing top-level routes.
const GLOBAL_PAGES = [
  { label: "Dashboard", path: "/", icon: Home, keywords: "home overview" },
  { label: "Projects", path: "/projects", icon: LayoutDashboard, keywords: "project list" },
  { label: "Generator Presets", path: "/generator-presets", icon: Wrench, keywords: "templates presets generator" },
  { label: "Sensitivity Rules", path: "/sensitivity-rules", icon: ShieldAlert, keywords: "pii classification rules" },
  { label: "Admin", path: "/admin", icon: Settings, keywords: "audit rbac users settings" },
] as const;

// Project-scoped entries — only shown when the user is currently inside a
// project. Each `suffix` is appended to `/projects/{currentProjectId}`.
const PROJECT_PAGES = [
  { label: "Overview", suffix: "", icon: LayoutDashboard, keywords: "summary dashboard" },
  { label: "Database View", suffix: "database", icon: Database, keywords: "schema tables" },
  { label: "Connections", suffix: "connections", icon: Database, keywords: "source database connection" },
  { label: "Discovery", suffix: "discovery", icon: FileSearch, keywords: "schema pii detect" },
  { label: "Privacy Hub", suffix: "privacy-hub", icon: Shield, keywords: "pii privacy unprotected review" },
  { label: "Masking", suffix: "masking", icon: Lock, keywords: "mask redact hash encrypt" },
  { label: "Synthetic", suffix: "synthetic", icon: TestTube, keywords: "generate faker data" },
  { label: "Subsetting", suffix: "subsetting", icon: Shuffle, keywords: "subset filter graph" },
  { label: "Workflows", suffix: "workflows", icon: Workflow, keywords: "pipeline dag automate" },
  { label: "Jobs", suffix: "jobs", icon: ScrollText, keywords: "job status progress" },
  { label: "Compliance", suffix: "compliance", icon: Network, keywords: "hipaa gdpr ccpa report" },
  { label: "Ephemeral", suffix: "ephemeral", icon: Hourglass, keywords: "temporary test database" },
  { label: "Settings", suffix: "settings", icon: Settings, keywords: "project config" },
] as const;

// Extract the current project's UUID from the URL if we're inside one.
// Matches `/projects/<id>` or `/projects/<id>/<anything>`. Returns null on
// the projects list itself or any non-project route.
function currentProjectId(pathname: string): string | null {
  const m = pathname.match(/^\/projects\/([^/]+)(?:\/|$)/);
  if (!m) return null;
  const id = m[1];
  // The list page is `/projects` (no segment after) — already filtered out
  // by the regex above. Guard against accidental literal "projects" matches.
  return id === "projects" ? null : id;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
      setQuery("");
      setSelected(0);
    }
  }, [open]);

  // Compose the palette entries with hrefs resolved against the current
  // location. Only include project-scoped entries when the user is inside
  // a project — otherwise their URLs would 404.
  const entries: PaletteEntry[] = useMemo(() => {
    const projectId = currentProjectId(pathname);
    const globals: PaletteEntry[] = GLOBAL_PAGES.map((p) => ({
      label: p.label,
      href: p.path,
      icon: p.icon,
      keywords: p.keywords,
      scope: "global",
    }));
    if (!projectId) return globals;
    const projectScoped: PaletteEntry[] = PROJECT_PAGES.map((p) => ({
      label: p.label,
      href: p.suffix ? `/projects/${projectId}/${p.suffix}` : `/projects/${projectId}`,
      icon: p.icon,
      keywords: p.keywords,
      scope: "project",
    }));
    return [...globals, ...projectScoped];
  }, [pathname]);

  if (!open) return null;

  const filtered = entries.filter((p) => {
    const q = query.toLowerCase().trim();
    return !q || p.label.toLowerCase().includes(q) || p.keywords.includes(q);
  });

  const handleSelect = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSelected((s) => Math.min(s + 1, filtered.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
    if (e.key === "Enter" && filtered[selected]) { handleSelect(filtered[selected].href); }
  };

  const projectId = currentProjectId(pathname);

  return (
    <>
      <div className="fixed inset-0 z-[60] bg-black/50" onClick={() => setOpen(false)} />
      <div className="fixed inset-x-0 top-[20%] z-[60] mx-auto w-full max-w-lg">
        <div className="rounded-xl border border-border bg-card shadow-2xl overflow-hidden">
          <div className="flex items-center gap-2 border-b border-border px-4 py-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setSelected(0); }}
              onKeyDown={handleKeyDown}
              placeholder={
                projectId
                  ? "Search pages in this project or globally..."
                  : "Search pages... (open a project for project-scoped pages)"
              }
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">ESC</kbd>
          </div>
          <div className="max-h-64 overflow-y-auto p-1">
            {filtered.map((page, i) => (
              <button
                key={page.href}
                onClick={() => handleSelect(page.href)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  i === selected ? "bg-primary/10 text-primary" : "text-foreground hover:bg-muted"
                )}
              >
                <page.icon className="h-4 w-4 shrink-0" />
                <span className="flex-1 text-left">{page.label}</span>
                {page.scope === "project" && (
                  <span className="text-[10px] text-muted-foreground">in project</span>
                )}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="px-3 py-4 text-center text-sm text-muted-foreground">No results</p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
