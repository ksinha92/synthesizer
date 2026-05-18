"use client";

import { ChevronRight, Home } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const labelMap: Record<string, string> = {
  projects: "Projects",
  connections: "Connections",
  discovery: "Discovery",
  masking: "Masking",
  synthetic: "Synthetic",
  subsetting: "Subsetting",
  workflows: "Workflows",
  jobs: "Jobs",
  compliance: "Compliance",
  admin: "Admin",
};

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  const crumbs = segments.map((segment, index) => {
    const href = "/" + segments.slice(0, index + 1).join("/");
    const label = labelMap[segment] || (segment.length > 8 ? segment.slice(0, 8) + "..." : segment);
    const isLast = index === segments.length - 1;

    return { href, label, isLast };
  });

  return (
    <nav className="flex items-center gap-1.5 text-sm text-muted-foreground mb-4">
      <Link href="/" className="hover:text-foreground transition-colors">
        <Home className="h-3.5 w-3.5" />
      </Link>
      {crumbs.map(({ href, label, isLast }) => (
        <span key={href} className="flex items-center gap-1.5">
          <ChevronRight className="h-3 w-3" />
          {isLast ? (
            <span className="font-medium text-foreground">{label}</span>
          ) : (
            <Link href={href} className="hover:text-foreground transition-colors">
              {label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}
