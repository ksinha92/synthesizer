"use client";

import { useCallback, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

interface ApiResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

function getRedirectParam(): string {
  if (typeof window === "undefined") return "";
  const current = window.location.pathname + window.location.search;
  return current !== "/login" ? `?redirect=${encodeURIComponent(current)}` : "";
}

let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
  // Deduplicate concurrent refresh attempts
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

async function apiFetch<T>(
  path: string,
  options: ApiOptions = {},
  _isRetry = false,
): Promise<T> {
  const { body, ...rest } = options;

  const res = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...rest.headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    ...rest,
  });

  if (res.status === 401 && !_isRetry) {
    // Try refreshing the access token once
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      return apiFetch<T>(path, options, true);
    }

    const currentPath = typeof window !== "undefined" ? window.location.pathname : "";
    if (currentPath !== "/login") {
      useAuthStore.getState().setUser(null);
      const redirect = getRedirectParam();
      window.location.href = `/login${redirect}`;
    }
    throw new Error("Unauthorized");
  }

  if (res.status === 401) {
    const currentPath = typeof window !== "undefined" ? window.location.pathname : "";
    if (currentPath !== "/login") {
      useAuthStore.getState().setUser(null);
      const redirect = getRedirectParam();
      window.location.href = `/login${redirect}`;
    }
    throw new Error("Unauthorized");
  }

  // Backend enforces force_password_change with a 403 + this error code on
  // every non-auth endpoint. Bounce the user to /change-password so they
  // can't keep hammering APIs that will all 403 until the password rotates.
  if (res.status === 403) {
    const errBody = await res.clone().json().catch(() => null);
    if (errBody?.error === "password_change_required" && typeof window !== "undefined") {
      const here = window.location.pathname;
      if (here !== "/change-password" && here !== "/login") {
        window.location.href = `/change-password?next=${encodeURIComponent(here)}`;
      }
      throw new Error("Password change required");
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }

  if (res.status === 204) return null as T;
  return res.json();
}

export function useApi<T>() {
  const [state, setState] = useState<ApiResult<T>>({
    data: null,
    error: null,
    loading: false,
  });

  const execute = useCallback(
    async (path: string, options: ApiOptions = {}): Promise<T | null> => {
      setState({ data: null, error: null, loading: true });
      try {
        const data = await apiFetch<T>(path, options);
        setState({ data, error: null, loading: false });
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setState({ data: null, error: message, loading: false });
        return null;
      }
    },
    []
  );

  return { ...state, execute };
}

// Convenience methods for direct usage
export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PUT", body }),
  del: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
