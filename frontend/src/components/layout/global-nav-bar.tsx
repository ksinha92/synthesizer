"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  HelpCircle,
  LayoutDashboard,
  Menu,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  User,
  Wrench,
  X,
} from "lucide-react";

import { NotificationCenter } from "@/components/notifications/notification-center";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

type RoleLevel = "viewer" | "editor" | "admin";
const ROLE_RANK: Record<string, number> = { viewer: 1, editor: 2, admin: 3, service_account: 3 };

interface NavItem {
  label: string;
  info: string; // one-line description shown under the label in the tooltip
  href: string;
  icon: React.ElementType;
  minRole?: RoleLevel;
}

// Feature navigation — workspace-level tools. Help lives in the right-side
// cluster as a dedicated help button (it's documentation, not a workspace
// surface), so it doesn't dilute the feature nav.
const NAV: NavItem[] = [
  { label: "Projects", info: "Browse and manage all projects", href: "/projects", icon: LayoutDashboard },
  { label: "Generator Presets", info: "Reusable synthetic data templates", href: "/generator-presets", icon: Wrench, minRole: "editor" },
  { label: "Sensitivity Rules", info: "Define PII detection patterns", href: "/sensitivity-rules", icon: ShieldAlert, minRole: "editor" },
  { label: "Admin", info: "Users, settings, audit logs", href: "/admin", icon: Settings, minRole: "admin" },
];

function filterByRole(items: NavItem[], role: string | undefined): NavItem[] {
  const rank = role ? ROLE_RANK[role] ?? 0 : 0;
  return items.filter((it) => !it.minRole || rank >= ROLE_RANK[it.minRole]);
}

interface GlobalNavBarProps {
  onAssistantClick?: () => void;
}

export function GlobalNavBar({ onAssistantClick }: GlobalNavBarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const role = useAuthStore((s) => s.user?.role);
  const email = useAuthStore((s) => s.user?.email);
  const logout = useAuthStore((s) => s.logout);
  const visibleNav = filterByRole(NAV, role);

  return (
    <TooltipProvider delayDuration={150} skipDelayDuration={200}>
    <nav
      aria-label="Global navigation"
      className="sticky top-0 z-40 border-b border-black/30 bg-[hsl(var(--dw-shell-bg))] text-[hsl(var(--dw-shell-fg))]"
    >
      <div className="flex h-12 items-center justify-between px-4 text-sm">
      {/* Left: brand + nav */}
      <div className="flex items-center gap-6">
        {/* Mobile menu trigger — hides above md */}
        <button
          type="button"
          aria-label="Open navigation menu"
          aria-controls="global-mobile-menu"
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((v) => !v)}
          className="md:hidden inline-flex items-center justify-center rounded-md p-1.5 text-[hsl(var(--dw-shell-muted))] hover:bg-white/5 hover:text-[hsl(var(--dw-shell-fg))]"
        >
          {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>

        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <Sparkles className="h-4 w-4 text-[hsl(var(--dw-brand))]" />
          <span>Synthia</span>
        </Link>

        <ul className="hidden md:flex items-center gap-1">
          {visibleNav.map(({ label, info, href, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <li key={href}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link
                      href={href}
                      aria-label={label}
                      className={cn(
                        "inline-flex items-center justify-center rounded-md p-1.5 transition-colors",
                        "text-[hsl(var(--dw-shell-muted))] hover:text-[hsl(var(--dw-shell-fg))] hover:bg-white/5",
                        active && "text-[hsl(var(--dw-shell-fg))] bg-white/5"
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
              </li>
            );
          })}
        </ul>
      </div>

      {/* Right: search / theme / notifications / assistant / user.
          On <md viewports the segmented ThemeToggle (~96px) and the
          command palette button overflow the bar, so they're hidden there;
          the command palette is still reachable via ⌘K, and the theme
          toggle stays available inside the user menu / mobile drawer
          on small screens. */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Open command palette"
          title="Search (⌘K)"
          onClick={() => {
            // CommandPalette listens for ⌘K globally; synthesize the event.
            const ev = new KeyboardEvent("keydown", { key: "k", metaKey: true });
            window.dispatchEvent(ev);
          }}
          className="hidden sm:inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-[hsl(var(--dw-shell-muted))] hover:bg-white/5 hover:text-[hsl(var(--dw-shell-fg))]"
        >
          <Search className="h-3.5 w-3.5" />
          <kbd className="text-[10px] font-mono">⌘K</kbd>
        </button>
        <div className="hidden md:flex">
          <ThemeToggle />
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <Link
              href="/help"
              aria-label="Help and documentation"
              className={cn(
                "rounded-md p-1.5 transition-colors",
                "text-[hsl(var(--dw-shell-muted))] hover:text-[hsl(var(--dw-shell-fg))] hover:bg-white/5",
                pathname.startsWith("/help") &&
                  "text-[hsl(var(--dw-shell-fg))] bg-white/5",
              )}
            >
              <HelpCircle className="h-4 w-4" />
            </Link>
          </TooltipTrigger>
          <TooltipContent side="bottom" sideOffset={4}>
            <div className="text-xs font-semibold text-foreground">Help</div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              Guides, onboarding, FAQ
            </div>
          </TooltipContent>
        </Tooltip>
        <NotificationCenter />
        {onAssistantClick && (
          <button
            type="button"
            onClick={onAssistantClick}
            aria-label="Open AI assistant"
            className="rounded-md p-1.5 text-[hsl(var(--dw-shell-muted))] hover:bg-white/5 hover:text-[hsl(var(--dw-shell-fg))]"
          >
            <Bot className="h-4 w-4" />
          </button>
        )}
        <div className="relative">
          <button
            type="button"
            aria-label="User menu"
            aria-haspopup="menu"
            aria-expanded={userMenuOpen}
            onClick={() => setUserMenuOpen((v) => !v)}
            className="rounded-md p-1.5 text-[hsl(var(--dw-shell-muted))] hover:bg-white/5 hover:text-[hsl(var(--dw-shell-fg))]"
          >
            <User className="h-4 w-4" />
          </button>
          {userMenuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-9 z-50 min-w-[220px] overflow-hidden rounded-md border border-border bg-card text-card-foreground shadow-xl ring-1 ring-black/5 dark:ring-white/5"
              onMouseLeave={() => setUserMenuOpen(false)}
            >
              <div className="px-3 py-2.5 text-xs bg-card">
                <div className="font-semibold text-card-foreground truncate">
                  {email ?? "Not signed in"}
                </div>
                {role && (
                  <div className="mt-0.5 text-[11px] text-muted-foreground capitalize">
                    {role}
                  </div>
                )}
              </div>
              <div className="border-t border-border" />
              <Link
                role="menuitem"
                href="/change-password"
                onClick={() => setUserMenuOpen(false)}
                className="block px-3 py-2 text-xs text-card-foreground hover:bg-muted hover:text-foreground"
              >
                Change password
              </Link>
              <div className="border-t border-border" />
              <button
                role="menuitem"
                type="button"
                onClick={() => {
                  setUserMenuOpen(false);
                  logout();
                }}
                className="block w-full text-left px-3 py-2 text-xs font-medium text-destructive hover:bg-destructive/10"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
      </div>

      {/* Mobile drawer — keeps full labels since touch has no hover. Help is
          appended after the feature nav because it lives in the right-side
          cluster on desktop. */}
      {mobileOpen && (
        <ul
          id="global-mobile-menu"
          className="md:hidden border-t border-black/30 px-3 py-2 text-sm"
        >
          {visibleNav.map(({ label, href, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors",
                    "text-[hsl(var(--dw-shell-muted))] hover:text-[hsl(var(--dw-shell-fg))] hover:bg-white/5",
                    active && "text-[hsl(var(--dw-shell-fg))] bg-white/5"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </Link>
              </li>
            );
          })}
          <li className="mt-1 border-t border-black/30 pt-1">
            <Link
              href="/help"
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors",
                "text-[hsl(var(--dw-shell-muted))] hover:text-[hsl(var(--dw-shell-fg))] hover:bg-white/5",
                pathname.startsWith("/help") &&
                  "text-[hsl(var(--dw-shell-fg))] bg-white/5",
              )}
            >
              <HelpCircle className="h-3.5 w-3.5" />
              Help &amp; documentation
            </Link>
          </li>
        </ul>
      )}
    </nav>
    </TooltipProvider>
  );
}
