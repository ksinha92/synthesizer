"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  FileSearch,
  Lock,
  Play,
  Shuffle,
  TestTube,
  Workflow,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface Verb {
  label: string;
  icon: React.ElementType;
  pathSuffix: string;
}

const VERBS: Verb[] = [
  { label: "Run Discovery", icon: FileSearch, pathSuffix: "discovery" },
  { label: "Generate Synthetic", icon: TestTube, pathSuffix: "synthetic" },
  { label: "Apply Masking", icon: Lock, pathSuffix: "masking" },
  { label: "Run Subset", icon: Shuffle, pathSuffix: "subsetting" },
  { label: "Execute Workflow", icon: Workflow, pathSuffix: "workflows" },
];

const DEFAULT_VERB = VERBS.find((v) => v.pathSuffix === "synthetic")!;

interface GenerateDataButtonProps {
  projectId: string;
}

export function GenerateDataButton({ projectId }: GenerateDataButtonProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const navigate = (suffix: string) => {
    router.push(`/projects/${projectId}/${suffix}`);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        onClick={() => navigate(DEFAULT_VERB.pathSuffix)}
        className="inline-flex items-center gap-1.5 rounded-l-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow-sm ring-1 ring-inset ring-white/10 transition hover:brightness-110 hover:shadow-md"
      >
        <Play className="h-3.5 w-3.5" />
        Generate Data
      </button>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center rounded-r-md border-l border-white/20 bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-2 py-1.5 text-white ring-1 ring-inset ring-white/10 transition hover:brightness-110"
      >
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <ul
          role="menu"
          className="absolute right-0 top-full z-50 mt-1.5 w-56 rounded-md border border-border bg-card py-1 shadow-xl ring-1 ring-black/5"
        >
          {VERBS.map(({ label, icon: Icon, pathSuffix }) => (
            <li key={pathSuffix} role="none">
              <button
                role="menuitem"
                onClick={() => navigate(pathSuffix)}
                className="group flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-muted"
              >
                <Icon className="h-3.5 w-3.5 text-[hsl(var(--primary))] transition-colors group-hover:text-[hsl(var(--dw-brand))]" />
                {label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
