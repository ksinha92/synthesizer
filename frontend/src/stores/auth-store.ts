"use client";

import { create } from "zustand";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface User {
  id: string;
  email: string;
  role: string;
  full_name: string;
  force_password_change?: boolean;
}

type RoleLevel = "viewer" | "editor" | "admin";
const ROLE_RANK: Record<string, number> = {
  viewer: 1,
  editor: 2,
  admin: 3,
  // service_account behaves like admin for in-browser purposes (it never logs in here anyway).
  service_account: 3,
};

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  forcePasswordChange: boolean;

  setUser: (user: User | null) => void;
  logout: () => Promise<void>;
  loadUser: () => Promise<void>;
  login: (email: string, password: string) => Promise<{ forcePasswordChange: boolean }>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  forcePasswordChange: false,

  setUser: (user) =>
    set({
      user,
      isAuthenticated: user !== null,
      isLoading: false,
      forcePasswordChange: !!user?.force_password_change,
    }),

  logout: async () => {
    try {
      await fetch(`${API_URL}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Best-effort cookie clear
    }
    set({ user: null, isAuthenticated: false, isLoading: false, forcePasswordChange: false });
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  },

  loadUser: async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/me`, {
        credentials: "include",
      });
      if (res.ok) {
        const user = (await res.json()) as User;
        set({
          user,
          isAuthenticated: true,
          isLoading: false,
          forcePasswordChange: !!user.force_password_change,
        });
      } else {
        set({ user: null, isAuthenticated: false, isLoading: false, forcePasswordChange: false });
      }
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false, forcePasswordChange: false });
    }
  },

  login: async (email: string, password: string) => {
    const res = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      throw new Error(await extractErrorMessage(res, "Invalid email or password"));
    }
    const payload = await res.json();
    const user: User = payload.user;
    set({
      user,
      isAuthenticated: true,
      isLoading: false,
      forcePasswordChange: !!user.force_password_change,
    });
    return { forcePasswordChange: !!user.force_password_change };
  },

  changePassword: async (currentPassword: string, newPassword: string) => {
    const res = await fetch(`${API_URL}/api/v1/auth/change-password`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!res.ok) {
      throw new Error(await extractErrorMessage(res, "Failed to change password"));
    }
    // Reload `/me` so the store reflects force_password_change=false.
    await get().loadUser();
  },
}));

/**
 * Extract a human-readable error message from a FastAPI error response.
 *
 * The backend wraps HTTPException details via a global exception handler that
 * flattens ``{detail: {error, detail}}`` into ``{error, detail, request_id}``,
 * so the user-facing message lives at ``body.detail`` (a string). Older
 * routes that raise ``HTTPException(detail="...")`` directly land the string
 * at the same key. The nested ``body.detail.detail`` shape never reaches
 * here in practice, but we keep the fallback for robustness.
 */
async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string" && body.detail.length > 0) return body.detail;
    if (typeof body?.detail?.detail === "string") return body.detail.detail;
    if (typeof body?.error === "string") return body.error;
  } catch {
    // Body wasn't JSON — fall through.
  }
  return fallback;
}

/** Returns true when the current user satisfies the minimum role rank. */
export function useHasRole(min: RoleLevel): boolean {
  const role = useAuthStore((s) => s.user?.role);
  if (!role) return false;
  return (ROLE_RANK[role] ?? 0) >= ROLE_RANK[min];
}
