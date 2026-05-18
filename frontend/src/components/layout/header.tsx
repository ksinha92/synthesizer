"use client";

import { Bot, Menu, Search, User } from "lucide-react";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { NotificationCenter } from "@/components/notifications/notification-center";
import { useAssistantStore } from "@/stores/assistant-store";
import { cn } from "@/lib/utils";

interface HeaderProps {
  onMobileMenuToggle?: () => void;
  sidebarCollapsed: boolean;
}

export function Header({ onMobileMenuToggle, sidebarCollapsed }: HeaderProps) {
  const toggleAssistant = useAssistantStore((s) => s.toggleOpen);
  return (
    <header
      className={cn(
        "fixed top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-card/95 backdrop-blur px-4 transition-all duration-200",
        sidebarCollapsed ? "left-16" : "left-60",
        "max-lg:left-0"
      )}
      style={{ right: 0 }}
    >
      {/* Left: mobile menu + search placeholder */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMobileMenuToggle}
          className="lg:hidden inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:text-foreground"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Cmd+K search placeholder */}
        <button className="hidden md:flex items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted transition-colors">
          <Search className="h-3.5 w-3.5" />
          <span>Search...</span>
          <kbd className="ml-4 inline-flex h-5 items-center rounded border border-border bg-background px-1.5 text-[10px] font-medium text-muted-foreground">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: theme + notifications + user */}
      <div className="flex items-center gap-2">
        <ThemeToggle />

        {/* AI Assistant */}
        <button onClick={toggleAssistant} className="relative inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:text-primary transition-colors" title="AI Assistant" aria-label="Open AI assistant">
          <Bot className="h-4 w-4" />
        </button>

        {/* Notification Center */}
        <NotificationCenter />

        {/* User avatar placeholder */}
        <button className="inline-flex items-center justify-center rounded-full h-8 w-8 bg-primary/10 text-primary hover:bg-primary/20 transition-colors" aria-label="User profile">
          <User className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
