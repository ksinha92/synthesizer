"use client";

import { useMemo, useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FaqCategory, FaqEntry } from "@/content/help-content";

interface FaqAccordionProps {
  entries: FaqEntry[];
  categories: FaqCategory[];
}

export function FaqAccordion({ entries, categories }: FaqAccordionProps) {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<FaqCategory | "All">("All");
  const [open, setOpen] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return entries.filter((e) => {
      const matchesCategory = activeCategory === "All" || e.category === activeCategory;
      if (!matchesCategory) return false;
      if (!q) return true;
      return (
        e.question.toLowerCase().includes(q) ||
        e.answer.toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q)
      );
    });
  }, [entries, query, activeCategory]);

  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const grouped = useMemo(() => {
    const m = new Map<FaqCategory, FaqEntry[]>();
    for (const e of filtered) {
      const list = m.get(e.category) ?? [];
      list.push(e);
      m.set(e.category, list);
    }
    return Array.from(m.entries());
  }, [filtered]);

  return (
    <div className="space-y-5">
      {/* Search + category chips */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search questions, e.g. 'webhook' or 'credentials'"
            className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-9 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            aria-label="Search FAQ"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </label>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <button
            type="button"
            onClick={() => setActiveCategory("All")}
            className={cn(
              "rounded-full border px-3 py-1 font-medium transition-colors",
              activeCategory === "All"
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-background text-muted-foreground hover:bg-muted",
            )}
          >
            All
          </button>
          {categories.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setActiveCategory(c)}
              className={cn(
                "rounded-full border px-3 py-1 font-medium transition-colors",
                activeCategory === c
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-background text-muted-foreground hover:bg-muted",
              )}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {filtered.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <p className="text-sm font-medium text-foreground">No matches</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try a different keyword or clear the filter.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {grouped.map(([category, items]) => (
            <section key={category} aria-labelledby={`faq-cat-${category}`}>
              <h3
                id={`faq-cat-${category}`}
                className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                {category}
              </h3>
              <ul className="divide-y divide-border rounded-lg border border-border bg-card">
                {items.map((item) => {
                  const key = `${item.category}::${item.question}`;
                  const isOpen = open.has(key);
                  return (
                    <li key={key}>
                      <button
                        type="button"
                        onClick={() => toggle(key)}
                        aria-expanded={isOpen}
                        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                      >
                        <span className="text-sm font-medium text-foreground">{item.question}</span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                            isOpen && "rotate-180",
                          )}
                          aria-hidden
                        />
                      </button>
                      <div
                        className={cn(
                          "grid overflow-hidden px-4 transition-all duration-200",
                          isOpen ? "grid-rows-[1fr] pb-3 opacity-100" : "grid-rows-[0fr] opacity-0",
                        )}
                      >
                        <div className="min-h-0 text-sm leading-relaxed text-muted-foreground">
                          {item.answer}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
