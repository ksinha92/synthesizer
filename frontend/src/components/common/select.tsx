"use client";

import { forwardRef } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Styled wrapper around a native <select>. Keeps native semantics + a11y
 * (screen reader, keyboard, mobile virtual picker) while normalising the
 * visual treatment across pages — historically the project used a mix of
 * `text-sm`, `text-xs`, varying padding, and inconsistent border tokens.
 *
 * The visible chevron is decorative; the underlying <select> still renders
 * the platform's native indicator on focus.
 */
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  /** When true, the select takes the full width of its parent. */
  fullWidth?: boolean;
  /** Optional label shown above the select. */
  label?: string;
  /** Optional helper / error text shown below the select. */
  helper?: string;
  /** Render with the error state styling. */
  invalid?: boolean;
  /** Size variant — defaults to "sm" to match toolbars/filters. */
  selectSize?: "sm" | "md";
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, children, fullWidth = true, label, helper, invalid, selectSize = "sm", id, ...rest },
  ref,
) {
  const reactId = useId(id, rest.name);

  const sizing = selectSize === "sm"
    ? "h-8 px-2.5 pr-7 text-xs"
    : "h-9 px-3 pr-8 text-sm";

  return (
    <div className={cn(fullWidth ? "w-full" : "inline-flex")}>
      {label && (
        <label htmlFor={reactId} className="block text-xs font-medium text-foreground mb-1">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={reactId}
          ref={ref}
          aria-invalid={invalid || undefined}
          className={cn(
            "appearance-none rounded-md border bg-background text-foreground transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring",
            invalid ? "border-destructive" : "border-input hover:border-muted-foreground/40",
            fullWidth && "w-full",
            sizing,
            className,
          )}
          {...rest}
        >
          {children}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
        />
      </div>
      {helper && (
        <p className={cn("mt-1 text-[11px]", invalid ? "text-destructive" : "text-muted-foreground")}>
          {helper}
        </p>
      )}
    </div>
  );
});

// Tiny inline helper so the wrapper can synthesise stable ids when the
// caller doesn't pass one. Avoids importing React's useId at module top
// when we want to keep this file lean.
function useId(provided: string | undefined, fallbackName?: string): string | undefined {
  if (provided) return provided;
  if (fallbackName) return `select-${fallbackName}`;
  return undefined;
}
