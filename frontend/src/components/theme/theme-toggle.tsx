"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

type ThemeToggleVariant = "shell" | "surface";

/**
 * Theme switcher.
 *
 * - "shell"   — for the always-dark global nav. Uses --dw-shell-* tokens so
 *               it reads against the dark navbar regardless of theme.
 * - "surface" — for surfaces that themselves switch between light and dark
 *               (auth pages, modals). Uses --foreground / --muted-foreground
 *               so it stays legible in both modes.
 */
export function ThemeToggle({
  variant = "shell",
}: {
  variant?: ThemeToggleVariant;
}) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return <div className="h-7 w-[98px]" />;

  const options = [
    { value: "light", icon: Sun, label: "Light" },
    { value: "dark", icon: Moon, label: "Dark" },
    { value: "system", icon: Monitor, label: "System" },
  ] as const;

  const containerCls =
    variant === "shell"
      ? "flex items-center gap-0.5 rounded-md border border-white/10 bg-white/[0.04] p-0.5"
      : "flex items-center gap-0.5 rounded-md border border-border bg-card p-0.5 shadow-sm";

  const activeCls =
    variant === "shell"
      ? "bg-white/15 text-[hsl(var(--dw-shell-fg))] shadow-sm"
      : "bg-muted text-foreground shadow-sm";

  const idleCls =
    variant === "shell"
      ? "text-[hsl(var(--dw-shell-muted))] hover:bg-white/5 hover:text-[hsl(var(--dw-shell-fg))]"
      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground";

  return (
    <div className={containerCls}>
      {options.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          type="button"
          onClick={() => setTheme(value)}
          aria-label={`${label} theme`}
          aria-pressed={theme === value}
          className={cn(
            "inline-flex items-center justify-center rounded-sm px-2 py-1 text-xs font-medium transition-colors",
            theme === value ? activeCls : idleCls
          )}
          title={label}
        >
          <Icon className="h-3.5 w-3.5" />
        </button>
      ))}
    </div>
  );
}
