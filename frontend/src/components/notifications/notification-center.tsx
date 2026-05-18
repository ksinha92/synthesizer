"use client";

import { useRef, useEffect } from "react";
import { Bell } from "lucide-react";
import { useNotificationStore } from "@/stores/notification-store";
import { NotificationItem } from "./notification-item";
import { cn } from "@/lib/utils";

export function NotificationCenter() {
  const { notifications, unreadCount, isOpen, toggleOpen, markRead, markAllRead } = useNotificationStore();
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (isOpen && panelRef.current && !panelRef.current.contains(e.target as Node)) {
        toggleOpen();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen, toggleOpen]);

  const bellLabel =
    unreadCount > 0
      ? `Open notifications, ${unreadCount} unread`
      : "Open notifications";

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        type="button"
        onClick={toggleOpen}
        aria-label={bellLabel}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        className="relative inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:text-foreground transition-colors"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span aria-hidden="true" className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-[360px] rounded-xl border border-border bg-card shadow-xl z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="text-sm font-semibold text-foreground">Notifications</h3>
            {unreadCount > 0 && (
              <button onClick={markAllRead} className="text-xs text-primary hover:underline">Mark all read</button>
            )}
          </div>

          {/* List */}
          <div className="max-h-[300px] overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-8 text-center text-xs text-muted-foreground">No notifications yet</div>
            ) : (
              <div className="p-1 space-y-0.5">
                {notifications.map((n) => (
                  <NotificationItem key={n.id} {...n} onRead={() => markRead(n.id)} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
