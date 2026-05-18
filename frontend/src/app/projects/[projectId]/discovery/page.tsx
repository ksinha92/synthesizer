"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { SchemaExplorer } from "@/components/discovery/schema-explorer";
import { PIIResultsTable } from "@/components/discovery/pii-results-table";
import { RunDiscoveryButton } from "@/components/discovery/run-discovery-button";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { useConnectionStore } from "@/stores/connection-store";
import { cn } from "@/lib/utils";
import dynamic from "next/dynamic";

const RelationshipGraph = dynamic(
  () => import("@/components/discovery/relationship-graph").then((m) => ({ default: m.RelationshipGraph })),
  { ssr: false, loading: () => <div className="h-96 flex items-center justify-center text-sm text-muted-foreground">Loading graph...</div> }
);

type Tab = "schema" | "pii" | "graph";

export default function DiscoveryPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [activeTab, setActiveTab] = useState<Tab>("schema");
  const [selectedSchemaNames, setSelectedSchemaNames] = useState<string[]>([]);
  const { schemas, fetchPII, relationships, fetchRelationships, deleteRelationship } = useDiscoveryStore();
  const fetchConnections = useConnectionStore((s) => s.fetchConnections);

  const filteredSchemas = selectedSchemaNames.length > 0
    ? schemas.filter((s) => selectedSchemaNames.includes(s.schema_name))
    : schemas;

  useEffect(() => {
    fetchConnections(projectId);
  }, [projectId, fetchConnections]);

  useEffect(() => {
    if (activeTab === "pii" && schemas.length > 0) {
      fetchPII(projectId, schemas[0].id);
    }
    if (activeTab === "graph") {
      fetchRelationships(projectId);
    }
  }, [activeTab, schemas, fetchPII, fetchRelationships, projectId]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "schema", label: "Schema Explorer" },
    { key: "pii", label: "PII Results" },
    { key: "graph", label: "Relationship Graph" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Discovery</h1>
        <RunDiscoveryButton projectId={projectId} onSchemasSelected={setSelectedSchemaNames} />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === tab.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "schema" && <SchemaExplorer projectId={projectId} />}
      {activeTab === "pii" && <PIIResultsTable projectId={projectId} />}
      {activeTab === "graph" && (
        <RelationshipGraph
          tables={filteredSchemas.flatMap((s) => s.tables.map((t) => ({ name: t.table_name, row_count: t.row_count })))}
          relationships={relationships}
          onNodeClick={() => { setActiveTab("schema"); }}
          onDeleteRelationship={(id) => deleteRelationship(projectId, id)}
        />
      )}
    </div>
  );
}
