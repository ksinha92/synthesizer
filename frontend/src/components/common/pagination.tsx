"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  pageSize: number;
  totalCount: number;
  onPageChange: (page: number) => void;
}

function getPageRange(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "ellipsis")[] = [1];

  if (current > 3) pages.push("ellipsis");

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) pages.push("ellipsis");

  pages.push(total);

  return pages;
}

export function Pagination({ page, pageSize, totalCount, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(totalCount / pageSize);
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalCount);
  const range = getPageRange(page, totalPages);

  return (
    <div className="flex items-center justify-between border-t border-border pt-4 mt-4">
      <p className="text-sm text-muted-foreground">
        Showing {start}-{end} of {totalCount}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className={cn(
            "inline-flex items-center justify-center rounded-md p-2 text-sm",
            page <= 1 ? "text-muted-foreground/50 cursor-not-allowed" : "text-muted-foreground hover:text-foreground hover:bg-muted"
          )}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        {range.map((item, idx) =>
          item === "ellipsis" ? (
            <span key={`ellipsis-${idx}`} className="px-2 text-sm text-muted-foreground">...</span>
          ) : (
            <button
              key={item}
              onClick={() => onPageChange(item)}
              className={cn(
                "inline-flex items-center justify-center rounded-md px-3 py-1.5 text-sm font-medium",
                page === item ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
              )}
            >
              {item}
            </button>
          )
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className={cn(
            "inline-flex items-center justify-center rounded-md p-2 text-sm",
            page >= totalPages ? "text-muted-foreground/50 cursor-not-allowed" : "text-muted-foreground hover:text-foreground hover:bg-muted"
          )}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
