"use client";

import { create } from "zustand";

const SIDEBAR_KEY = "datawrangler-sidebar-collapsed";

interface ThemeStoreState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useThemeStore = create<ThemeStoreState>((set) => ({
  sidebarCollapsed:
    typeof window !== "undefined"
      ? localStorage.getItem(SIDEBAR_KEY) === "true"
      : false,

  toggleSidebar: () =>
    set((state) => {
      const next = !state.sidebarCollapsed;
      localStorage.setItem(SIDEBAR_KEY, String(next));
      return { sidebarCollapsed: next };
    }),

  setSidebarCollapsed: (collapsed) => {
    localStorage.setItem(SIDEBAR_KEY, String(collapsed));
    set({ sidebarCollapsed: collapsed });
  },
}));
