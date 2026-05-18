"use client";

import { useState } from "react";
import { Loader2, Play } from "lucide-react";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { useConnectionStore } from "@/stores/connection-store";
import { SchemaSelector } from "@/components/discovery/schema-selector";
import { Select } from "@/components/common/select";

interface RunDiscoveryButtonProps {
  projectId: string;
  onSchemasSelected?: (schemas: string[]) => void;
}

export function RunDiscoveryButton({ projectId, onSchemasSelected }: RunDiscoveryButtonProps) {
  const [selectedConnection, setSelectedConnection] = useState("");
  const [running, setRunning] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [showSchemaSelector, setShowSchemaSelector] = useState(false);
  const { connections } = useConnectionStore();
  const { runDiscovery } = useDiscoveryStore();

  const handleRunClick = () => {
    if (!selectedConnection) return;
    setShowSchemaSelector(true);
  };

  const handleSchemaConfirm = async (selectedSchemas: string[]) => {
    setShowSchemaSelector(false);
    setRunning(true);
    setJobId(null);
    onSchemasSelected?.(selectedSchemas);
    const id = await runDiscovery(projectId, selectedConnection);
    setRunning(false);
    if (id) setJobId(id);
  };

  return (
    <>
      <div className="flex items-center gap-2">
        <Select
          aria-label="Connection to run discovery on"
          fullWidth={false}
          selectSize="md"
          value={selectedConnection}
          onChange={(e) => setSelectedConnection(e.target.value)}
          className="min-w-[260px]"
        >
          <option value="">Select connection…</option>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>{c.name} ({c.connector_type})</option>
          ))}
        </Select>
        <button
          onClick={handleRunClick}
          disabled={!selectedConnection || running}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          {running ? "Running..." : "Run Discovery"}
        </button>
        {jobId && (
          <span className="text-xs text-muted-foreground">Job started: {jobId.slice(0, 8)}...</span>
        )}
      </div>

      {showSchemaSelector && (
        <SchemaSelector
          projectId={projectId}
          connectionId={selectedConnection}
          onConfirm={handleSchemaConfirm}
          onCancel={() => setShowSchemaSelector(false)}
        />
      )}
    </>
  );
}
