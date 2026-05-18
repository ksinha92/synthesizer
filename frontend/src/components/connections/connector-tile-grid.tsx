"use client";

import { useState } from "react";
import { Cloud, Database, Info, Leaf, Server, Snowflake } from "lucide-react";

import { cn } from "@/lib/utils";
import { ConnectorSetupDialog } from "@/components/connections/connector-setup-dialog";

// Tonic-style categorised connector picker. All 9 connectors are live and
// fully wired — see backend/app/infrastructure/connectors/registry.py for
// the matching server-side implementations.
type ConnectorCategory = "application_db" | "warehouse" | "file";
interface Connector {
  value: string;
  label: string;
  category: ConnectorCategory;
  icon: React.ElementType;
  defaultPort: number;
}

export const CONNECTOR_TYPES: readonly Connector[] = [
  { value: "postgresql", label: "PostgreSQL", category: "application_db", icon: Database, defaultPort: 5432 },
  { value: "mysql", label: "MySQL", category: "application_db", icon: Database, defaultPort: 3306 },
  { value: "mongodb", label: "MongoDB", category: "application_db", icon: Leaf, defaultPort: 27017 },
  { value: "oracle", label: "Oracle", category: "application_db", icon: Database, defaultPort: 1521 },
  { value: "sqlserver", label: "SQL Server", category: "application_db", icon: Database, defaultPort: 1433 },
  { value: "db2", label: "IBM DB2", category: "application_db", icon: Server, defaultPort: 50000 },
  { value: "snowflake", label: "Snowflake", category: "warehouse", icon: Snowflake, defaultPort: 443 },
  { value: "redshift", label: "Redshift", category: "warehouse", icon: Cloud, defaultPort: 5439 },
  { value: "databricks", label: "Databricks", category: "warehouse", icon: Cloud, defaultPort: 443 },
] as const;

const CATEGORY_LABEL: Record<ConnectorCategory, string> = {
  application_db: "Application databases",
  warehouse: "Data warehouses",
  file: "Files",
};

const CATEGORY_ORDER: ConnectorCategory[] = ["application_db", "warehouse", "file"];

/**
 * Return the default port for a connector value, or undefined if unknown.
 * Used by the standalone Add Connection drawer and the wizard to keep the
 * port field in sync with the picker selection.
 */
export function defaultPortFor(connectorValue: string): number | undefined {
  return CONNECTOR_TYPES.find((c) => c.value === connectorValue)?.defaultPort;
}

interface ConnectorTileGridProps {
  selected: string;
  onSelect: (value: string) => void;
  step?: string;
  title?: string;
}

export function ConnectorTileGrid({
  selected,
  onSelect,
  step,
  title = "Connector Type",
}: ConnectorTileGridProps) {
  // Which connector's setup-guide popup is open, if any. Independent of the
  // tile's `selected` state so the user can preview setup for a connector
  // without committing to it as the form's selection.
  const [guideFor, setGuideFor] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <label className="block text-sm font-medium text-foreground">{title}</label>
        {step && (
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {step}
          </span>
        )}
      </div>
      <div className="space-y-4">
        {CATEGORY_ORDER.map((category) => {
          const live = CONNECTOR_TYPES.filter((c) => c.category === category);
          if (live.length === 0) return null;
          return (
            <div key={category}>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {CATEGORY_LABEL[category]}
              </p>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {live.map((t) => {
                  const Icon = t.icon;
                  const isSelected = selected === t.value;
                  return (
                    <div
                      key={t.value}
                      className={cn(
                        "group relative aspect-square rounded-lg border bg-background transition-all",
                        isSelected
                          ? "border-primary shadow-sm ring-1 ring-primary/30"
                          : "border-border hover:border-primary/40 hover:bg-muted/30",
                      )}
                    >
                      {/* Tile button — selects this connector. */}
                      <button
                        type="button"
                        onClick={() => onSelect(t.value)}
                        aria-pressed={isSelected}
                        className="flex h-full w-full flex-col items-center justify-center gap-1.5 rounded-lg p-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                      >
                        <Icon
                          className={cn(
                            "h-6 w-6",
                            isSelected
                              ? "text-primary"
                              : "text-muted-foreground group-hover:text-foreground",
                          )}
                        />
                        <span
                          className={cn(
                            "text-[11px] font-medium",
                            isSelected ? "text-primary" : "text-foreground",
                          )}
                        >
                          {t.label}
                        </span>
                      </button>

                      {/* Info button — opens the setup-guide popup without
                          selecting the connector. Stops propagation so a
                          click here doesn't also toggle the tile. */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setGuideFor(t.value);
                        }}
                        aria-label={`Setup guide for ${t.label}`}
                        className="absolute right-1 top-1 inline-flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                      >
                        <Info className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Single dialog instance, switches on which connector was requested. */}
      {guideFor && (
        <ConnectorSetupDialog
          connectorValue={guideFor}
          open={guideFor !== null}
          onClose={() => setGuideFor(null)}
          onUseConnector={(v) => onSelect(v)}
        />
      )}
    </div>
  );
}
