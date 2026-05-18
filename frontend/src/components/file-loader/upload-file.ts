"use client";

/**
 * Multipart upload helper — companion to ``api`` from ``use-api.ts``.
 *
 * ``api.post`` forces ``Content-Type: application/json`` and stringifies
 * the body, which the browser refuses to set a boundary on. File uploads
 * have to skip that path and let the browser pick its own multipart
 * boundary; this helper does that while preserving the project's auth +
 * cookie + 401-retry semantics.
 */

import { useAuthStore } from "@/stores/auth-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
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

function redirectToLoginIfNeeded() {
  const currentPath =
    typeof window !== "undefined" ? window.location.pathname : "";
  if (currentPath !== "/login") {
    useAuthStore.getState().setUser(null);
    const redirect =
      currentPath && currentPath !== "/login"
        ? `?redirect=${encodeURIComponent(
            currentPath + (typeof window !== "undefined" ? window.location.search : ""),
          )}`
        : "";
    if (typeof window !== "undefined") {
      window.location.href = `/login${redirect}`;
    }
  }
}

/**
 * POST a multipart form to the backend. Accepts:
 *  - ``file``: required — the file to upload (form field name "file")
 *  - ``extras``: optional additional form fields (e.g. ``{limit: "100"}``)
 *  - ``query``: optional query-string parameters
 *
 * Returns the parsed JSON response (or null for 204). Throws an Error
 * with the backend's ``detail`` when the response is not OK.
 */
export async function uploadFile<T = unknown>(
  path: string,
  {
    file,
    extras,
    query,
    method = "POST",
    fieldName = "file",
  }: {
    file?: File;
    extras?: Record<string, string | number | boolean>;
    query?: Record<string, string | number | boolean | undefined>;
    method?: "POST" | "PATCH";
    fieldName?: string;
  },
  _isRetry = false,
): Promise<T | null> {
  const form = new FormData();
  if (file) form.append(fieldName, file);
  if (extras) {
    for (const [k, v] of Object.entries(extras)) {
      form.append(k, String(v));
    }
  }
  let qs = "";
  if (query) {
    const pairs = Object.entries(query)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
    if (pairs.length) qs = `?${pairs.join("&")}`;
  }

  const res = await fetch(`${API_URL}${path}${qs}`, {
    method,
    credentials: "include",
    // IMPORTANT: do NOT set Content-Type. The browser writes
    // ``multipart/form-data; boundary=…`` automatically; setting it
    // manually breaks the boundary header.
    body: form,
  });

  if (res.status === 401 && !_isRetry) {
    const refreshed = await attemptTokenRefresh();
    if (refreshed) {
      return uploadFile<T>(path, { file, extras, query, method, fieldName }, true);
    }
    redirectToLoginIfNeeded();
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail =
      (err && (err.detail?.detail || err.detail || err.error)) || `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (res.status === 204) return null;
  return res.json();
}
