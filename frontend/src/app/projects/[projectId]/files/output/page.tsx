"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Link2 } from "lucide-react";

import { toast } from "@/components/common/toast";
import { FileOutputPanel } from "@/components/synthetic/file-output-panel";
import { useFileOutputStore, type CrossFileFK } from "@/stores/file-output-store";

const STORAGE_PREFIX = "files-accepted-fks::";

/**
 * Files → Output — file-set builder + generation. Wraps the existing
 * FileOutputPanel and adds a one-click hydrator that pulls accepted
 * relationships from the Relationships tab (stashed in localStorage)
 * into the panel's foreignKeys state, eliminating the need for users to
 * re-enter FK pairs by hand.
 */
export default function FilesOutputPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const addFk = useFileOutputStore((s) => s.addFk);
  const foreignKeys = useFileOutputStore((s) => s.foreignKeys);

  const [acceptedCount, setAcceptedCount] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_PREFIX + projectId);
    if (!raw) {
      setAcceptedCount(0);
      return;
    }
    try {
      const list = JSON.parse(raw) as CrossFileFK[];
      setAcceptedCount(Array.isArray(list) ? list.length : 0);
    } catch {
      setAcceptedCount(0);
    }
  }, [projectId]);

  const hydrate = () => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_PREFIX + projectId);
    if (!raw) return;
    let parsed: CrossFileFK[] = [];
    try {
      parsed = JSON.parse(raw) as CrossFileFK[];
    } catch {
      toast.error("Could not read accepted relationships.");
      return;
    }
    // Filter out any FKs already present in the panel state to avoid
    // duplicates when the user clicks the button twice.
    const existing = new Set(
      foreignKeys.map(
        (f) =>
          `${f.source_file}.${f.source_field}→${f.target_file}.${f.target_field}`,
      ),
    );
    let added = 0;
    for (const fk of parsed) {
      const key = `${fk.source_file}.${fk.source_field}→${fk.target_file}.${fk.target_field}`;
      if (existing.has(key)) continue;
      addFk(fk);
      added += 1;
    }
    toast.success(
      added === 0
        ? "All accepted relationships were already present."
        : `Added ${added} relationship${added === 1 ? "" : "s"}.`,
    );
  };

  return (
    <div className="space-y-3">
      {acceptedCount > 0 && (
        <div className="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-xs">
          <span className="text-muted-foreground">
            {acceptedCount} relationship{acceptedCount === 1 ? "" : "s"} accepted on
            the Relationships tab.
          </span>
          <button
            type="button"
            onClick={hydrate}
            className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 hover:bg-muted/40"
          >
            <Link2 className="h-3 w-3" /> Use accepted relationships
          </button>
        </div>
      )}
      <FileOutputPanel projectId={projectId} />
    </div>
  );
}
