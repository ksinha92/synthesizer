"use client";

import { useEffect } from "react";
import { create } from "zustand";
import { CheckCircle, XCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Toast {
  id: string;
  type: "success" | "error" | "info";
  message: string;
}

interface ToastState {
  toasts: Toast[];
  addToast: (type: Toast["type"], message: string) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (type, message) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`;
    set((s) => ({ toasts: [...s.toasts, { id, type, message }].slice(-5) }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 3500);
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

// Convenience functions
export const toast = {
  success: (msg: string) => useToastStore.getState().addToast("success", msg),
  error: (msg: string) => useToastStore.getState().addToast("error", msg),
  info: (msg: string) => useToastStore.getState().addToast("info", msg),
};

const ICONS = { success: CheckCircle, error: XCircle, info: Info };
const COLORS = {
  success: "border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-400",
  error: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400",
  info: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-400",
};

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] space-y-2 max-w-sm" aria-live="polite">
      {toasts.map((t) => {
        const Icon = ICONS[t.type];
        return (
          <div
            key={t.id}
            className={cn(
              "flex items-center gap-2.5 rounded-lg border px-4 py-3 shadow-lg animate-in slide-in-from-right-5 fade-in duration-200",
              COLORS[t.type]
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <p className="text-sm flex-1">{t.message}</p>
            <button onClick={() => removeToast(t.id)} className="shrink-0 opacity-60 hover:opacity-100">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
