"use client";

import { create } from "zustand";

const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours
const MAX_NOTIFICATIONS = 50;

interface Notification {
  id: string;
  // ``warning`` exists for terminal-but-partial outcomes (currently only
  // ``completed_with_warnings`` jobs use it). It must not collapse into
  // ``failed`` — the bundle is downloadable and the operator's call to
  // action is "review skipped rules", not "the job exploded".
  type: "completed" | "failed" | "info" | "warning";
  message: string;
  projectId?: string;
  jobId?: string;
  read: boolean;
  createdAt: string;
}

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  isOpen: boolean;
  toggleOpen: () => void;
  addNotification: (n: Omit<Notification, "id" | "read" | "createdAt">) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
}

function getStorageKey(): string {
  if (typeof window === "undefined") return "dw-notifications";
  try {
    const authState = JSON.parse(localStorage.getItem("auth-store") || "{}");
    const userId = authState?.state?.user?.id;
    return userId ? `dw-notifications-${userId}` : "dw-notifications";
  } catch {
    return "dw-notifications";
  }
}

function loadNotifications(): Notification[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(getStorageKey());
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Notification[];
    const cutoff = Date.now() - TTL_MS;
    return parsed.filter((n) => new Date(n.createdAt).getTime() > cutoff).slice(0, MAX_NOTIFICATIONS);
  } catch {
    return [];
  }
}

function persistNotifications(notifications: Notification[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(getStorageKey(), JSON.stringify(notifications));
  } catch {
    // Quota exceeded or SSR — silently ignore
  }
}

const initial = loadNotifications();

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: initial,
  unreadCount: initial.filter((n) => !n.read).length,
  isOpen: false,

  toggleOpen: () => set((s) => ({ isOpen: !s.isOpen })),

  addNotification: (n) => set((s) => {
    const notif: Notification = {
      ...n,
      id: `notif-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      read: false,
      createdAt: new Date().toISOString(),
    };
    const updated = [notif, ...s.notifications].slice(0, MAX_NOTIFICATIONS);
    persistNotifications(updated);
    return { notifications: updated, unreadCount: updated.filter((n) => !n.read).length };
  }),

  markRead: (id) => set((s) => {
    const updated = s.notifications.map((n) => n.id === id ? { ...n, read: true } : n);
    persistNotifications(updated);
    return { notifications: updated, unreadCount: updated.filter((n) => !n.read).length };
  }),

  markAllRead: () => set((s) => {
    const updated = s.notifications.map((n) => ({ ...n, read: true }));
    persistNotifications(updated);
    return { notifications: updated, unreadCount: 0 };
  }),
}));
