"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import dynamic from "next/dynamic";
import { SubsettingConfig } from "@/components/subsetting/subsetting-config";
import { useSubsettingStore } from "@/stores/subsetting-store";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { cn } from "@/lib/utils";

const DependencyGraph = dynamic(
  () => import("@/components/subsetting/dependency-graph").then((m) => ({ default: m.DependencyGraph })),
  { ssr: false, loading: () => <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">Loading graph...</div> }
);

const STRATEGY_COLORS: Record<string, string> = {
  upstream: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  downstream: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  both: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

export default function SubsettingPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { analysis, configs, configsLoading, fetchConfigs, analyze } = useSubsettingStore();
  const { schemas, relationships, fetchResults, fetchRelationships } = useDiscoveryStore();
  const [selectedConfigId, setSelectedConfigId] = useState<string | null>(null);

  useEffect(() => { fetchConfigs(projectId); }, [projectId, fetchConfigs]);

  const selectedConfig = useMemo(
    () => configs.find((c) => c.id === selectedConfigId) ?? null,
    [configs, selectedConfigId]
  );

  // Load discovery results + relationships for the config's source connection so
  // DependencyGraph can render real FK edges. Mirrors discovery/page.tsx.
  useEffect(() => {
    const connId = selectedConfig?.source_connection_id;
    if (!connId) return;
    if (schemas.length === 0) {
      fetchResults(projectId, connId);
    }
  }, [projectId, selectedConfig?.source_connection_id, schemas.length, fetchResults]);

  useEffect(() => {
    if (schemas.length > 0 && relationships.length === 0) {
      fetchRelationships(projectId);
    }
  }, [projectId, schemas.length, relationships.length, fetchRelationships]);

  const rootTables = useMemo<string[]>(() => {
    if (!selectedConfig?.root_tables) return [];
    return selectedConfig.root_tables
      .map((rt) => {
        const name = (rt as { table_name?: unknown }).table_name;
        return typeof name === "string" ? name : null;
      })
      .filter((n): n is string => !!n);
  }, [selectedConfig]);

  const traversalDirection = selectedConfig?.traversal_strategy ?? "upstream";

  const handleSelectConfig = (configId: string) => {
    setSelectedConfigId(configId);
    analyze(projectId, configId);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Data Subsetting</h1>
      <p className="text-sm text-muted-foreground">Create referentially-intact subsets by traversing FK dependency graphs.</p>

      {/* Saved Configs */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Saved Configs</h2>
        {configsLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        ) : configs.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">No subset configs yet. Create one below.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {configs.map((c) => (
              <button
                key={c.id}
                onClick={() => handleSelectConfig(c.id)}
                className={cn(
                  "rounded-lg border p-3 text-left transition-colors hover:bg-muted/50",
                  selectedConfigId === c.id ? "border-primary bg-primary/5" : "border-border bg-card"
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-foreground truncate">{c.name}</span>
                  <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", STRATEGY_COLORS[c.traversal_strategy] || "bg-muted text-muted-foreground")}>
                    {c.traversal_strategy}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {c.target_percentage != null && <span>Target: {c.target_percentage}%</span>}
                  {c.target_row_count != null && <span>Rows: {c.target_row_count.toLocaleString()}</span>}
                  <span>{new Date(c.created_at).toLocaleDateString()}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SubsettingConfig projectId={projectId} />
        {selectedConfig ? (
          <DependencyGraph
            tables={analysis.map((a) => ({ name: a.table_name, row_count: a.full_count }))}
            relationships={relationships.map((r) => ({ source_table: r.source_table, target_table: r.target_table }))}
            rootTables={rootTables}
            traversalDirection={traversalDirection}
            dryRunData={analysis}
          />
        ) : (
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
            Select a config to view dependencies
          </div>
        )}
      </div>
    </div>
  );
}
