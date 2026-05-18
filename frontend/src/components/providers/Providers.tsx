"use client";

import { Suspense } from "react";
import { ThemeProvider } from "@/components/theme/theme-provider";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { CommandPalette } from "@/components/common/command-palette";
import { ToastContainer } from "@/components/common/toast";

function LoadingFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  );
}

/**
 * Client-side provider chain. Centralized here so the root `layout.tsx` can
 * remain a thin Server Component — Next.js 14 + antd v5 trip a `useContext`
 * null during SSR when client-context-using components are interleaved at
 * the server boundary (see Phase 61 F17).
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        <CommandPalette />
        <Suspense fallback={<LoadingFallback />}>{children}</Suspense>
        <ToastContainer />
      </ErrorBoundary>
    </ThemeProvider>
  );
}
