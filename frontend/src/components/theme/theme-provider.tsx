"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import { ConfigProvider, theme as antTheme } from "antd";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

function AntDesignThemeSync({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return <>{children}</>;

  const isDark = resolvedTheme === "dark";

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: {
          colorPrimary: isDark ? "#4A9AE6" : "#1B65A6",
          borderRadius: 8,
          fontFamily: "var(--font-inter), system-ui, sans-serif",
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <AntDesignThemeSync>{children}</AntDesignThemeSync>
    </NextThemesProvider>
  );
}
