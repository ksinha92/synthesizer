"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, X } from "lucide-react";
import { useConnectionStore } from "@/stores/connection-store";
import { cn } from "@/lib/utils";

interface SchemaSelectorProps {
  projectId: string;
  connectionId: string;
  onConfirm: (selectedSchemas: string[]) => void;
  onCancel: () => void;
}

export function SchemaSelector({ projectId, connectionId, onConfirm, onCancel }: SchemaSelectorProps) {
  const { fetchSchemas, schemas, schemasLoading } = useConnectionStore();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const schemaNames = schemas[connectionId] || [];

  useEffect(() => {
    fetchSchemas(projectId, connectionId).then((names) => {
      setSelected(new Set(names));
    });
  }, [projectId, connectionId, fetchSchemas]);

  const toggleSchema = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === schemaNames.length) setSelected(new Set());
    else setSelected(new Set(schemaNames));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-foreground">Select Schemas</h3>
          <button onClick={onCancel} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        {schemasLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Fetching schemas...</span>
          </div>
        ) : schemaNames.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No schemas found. Discovery will scan all available schemas.</p>
        ) : (
          <>
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs text-muted-foreground">{selected.size} of {schemaNames.length} selected</span>
              <button onClick={toggleAll} className="text-xs text-primary hover:underline">
                {selected.size === schemaNames.length ? "Deselect All" : "Select All"}
              </button>
            </div>
            <div className="max-h-60 overflow-y-auto space-y-1 rounded-lg border border-border p-2">
              {schemaNames.map((name) => (
                <button
                  key={name}
                  onClick={() => toggleSchema(name)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                    selected.has(name)
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted"
                  )}
                >
                  <div className={cn(
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                    selected.has(name) ? "border-primary bg-primary" : "border-muted-foreground/40"
                  )}>
                    {selected.has(name) && <Check className="h-3 w-3 text-primary-foreground" />}
                  </div>
                  {name}
                </button>
              ))}
            </div>
          </>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-muted">
            Cancel
          </button>
          <button
            onClick={() => onConfirm(Array.from(selected))}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {schemaNames.length === 0 ? "Run Discovery" : `Discover ${selected.size} Schema${selected.size !== 1 ? "s" : ""}`}
          </button>
        </div>
      </div>
    </div>
  );
}
