"use client";

import { useState } from "react";
import { Controller, type Control, type FieldValues, type Path } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

interface FormFieldProps<T extends FieldValues> {
  control: Control<T>;
  name: Path<T>;
  label: string;
  type?: "text" | "number" | "password" | "textarea" | "select";
  placeholder?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  rows?: number;
  className?: string;
  min?: number;
  max?: number;
}

export function FormField<T extends FieldValues>({
  control,
  name,
  label,
  type = "text",
  placeholder,
  required,
  options,
  rows = 3,
  className,
  min,
  max,
}: FormFieldProps<T>) {
  const [showPassword, setShowPassword] = useState(false);
  const errorId = `${String(name)}-error`;

  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState: { error } }) => (
        <div className={className}>
          <label htmlFor={String(name)} className="block text-sm font-medium text-foreground mb-1">
            {label}{required && " *"}
          </label>

          {type === "select" ? (
            <select
              {...field}
              id={String(name)}
              aria-invalid={!!error}
              aria-describedby={error ? errorId : undefined}
              className={cn(
                "w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring",
                error ? "border-destructive" : "border-input"
              )}
            >
              <option value="">{placeholder || "Select..."}</option>
              {options?.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          ) : type === "textarea" ? (
            <textarea
              {...field}
              id={String(name)}
              placeholder={placeholder}
              rows={rows}
              aria-invalid={!!error}
              aria-describedby={error ? errorId : undefined}
              className={cn(
                "w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none",
                error ? "border-destructive" : "border-input"
              )}
            />
          ) : type === "password" ? (
            <div className="relative">
              <input
                {...field}
                id={String(name)}
                type={showPassword ? "text" : "password"}
                placeholder={placeholder}
                aria-invalid={!!error}
                aria-describedby={error ? errorId : undefined}
                className={cn(
                  "w-full rounded-lg border bg-background px-3 py-2 pr-10 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring",
                  error ? "border-destructive" : "border-input"
                )}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          ) : (
            <input
              {...field}
              id={String(name)}
              type={type}
              placeholder={placeholder}
              min={min}
              max={max}
              aria-invalid={!!error}
              aria-describedby={error ? errorId : undefined}
              onChange={(e) => {
                if (type === "number") {
                  field.onChange(e.target.value === "" ? "" : Number(e.target.value));
                } else {
                  field.onChange(e.target.value);
                }
              }}
              className={cn(
                "w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring",
                error ? "border-destructive" : "border-input"
              )}
            />
          )}

          {error && (
            <p id={errorId} role="alert" className="mt-1 text-xs text-destructive">
              {error.message}
            </p>
          )}
        </div>
      )}
    />
  );
}
