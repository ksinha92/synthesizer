"use client";

import { useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_RETRIES = 5;
const BASE_DELAY = 1000;
const MAX_DELAY = 30000;

interface SSEState<T> {
  data: T | null;
  connected: boolean;
  reconnecting: boolean;
  error: string | null;
}

export function useSSE<T = Record<string, unknown>>(path: string, enabled: boolean): SSEState<T> {
  const [state, setState] = useState<SSEState<T>>({ data: null, connected: false, reconnecting: false, error: null });
  const abortRef = useRef<AbortController | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);

  useEffect(() => {
    if (!enabled) {
      if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
      if (retryRef.current) { clearTimeout(retryRef.current); retryRef.current = null; }
      retryCountRef.current = 0;
      setState((s) => ({ ...s, connected: false, reconnecting: false }));
      return;
    }

    const connect = async (controller: AbortController) => {
      try {
        const res = await fetch(`${API_URL}${path}`, {
          credentials: "include",
          headers: { Accept: "text/event-stream" },
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          setState((s) => ({ ...s, connected: false, reconnecting: false, error: `HTTP ${res.status}` }));
          scheduleRetry(controller);
          return;
        }

        // Connected successfully — reset retry counter
        retryCountRef.current = 0;
        setState((s) => ({ ...s, connected: true, reconnecting: false, error: null }));

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const parsed = JSON.parse(line.slice(6)) as T;
                setState({ data: parsed, connected: true, reconnecting: false, error: null });
              } catch {
                // Ignore non-JSON data lines
              }
            }
          }
        }

        // Stream ended normally — try to reconnect
        setState((s) => ({ ...s, connected: false }));
        scheduleRetry(controller);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setState((s) => ({ ...s, connected: false, error: "Connection lost" }));
        scheduleRetry(controller);
      }
    };

    const scheduleRetry = (controller: AbortController) => {
      if (controller.signal.aborted) return;
      if (retryCountRef.current >= MAX_RETRIES) {
        setState((s) => ({ ...s, reconnecting: false, error: `Connection lost after ${MAX_RETRIES} retries` }));
        return;
      }
      const delay = Math.min(BASE_DELAY * Math.pow(2, retryCountRef.current), MAX_DELAY);
      retryCountRef.current++;
      setState((s) => ({ ...s, reconnecting: true }));
      retryRef.current = setTimeout(() => {
        if (!controller.signal.aborted) connect(controller);
      }, delay);
    };

    const controller = new AbortController();
    abortRef.current = controller;
    connect(controller);

    return () => {
      controller.abort();
      abortRef.current = null;
      if (retryRef.current) { clearTimeout(retryRef.current); retryRef.current = null; }
    };
  }, [path, enabled]);

  return state;
}
