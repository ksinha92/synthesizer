"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { EngineSelector } from "@/components/synthetic/engine-selector";
import { ConfigForm } from "@/components/synthetic/config-form";
import { PreviewTable } from "@/components/synthetic/preview-table";
import { QualityReport } from "@/components/synthetic/quality-report";
import { NLPPromptForm } from "@/components/synthetic/nlp-prompt-form";
import { GenerationPlanEditor } from "@/components/synthetic/generation-plan-editor";
import { Select } from "@/components/common/select";
import { useSyntheticStore } from "@/stores/synthetic-store";
import { useConnectionStore } from "@/stores/connection-store";

/**
 * Synthetic Data Generation — DB-only after the Files IA migration.
 * Everything file-related (schemas, viewer, browse, relationships,
 * mappings, output) lives under the dedicated Files workspace area.
 */
export default function SyntheticPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { previewData, previewLoading, selectedEngine } = useSyntheticStore();
  const lastConfigId = useSyntheticStore((s) => s.lastConfigId);
  const { connections, fetchConnections } = useConnectionStore();
  const [selectedConnection, setSelectedConnection] = useState("");
  const [nlpPlan, setNlpPlan] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetchConnections(projectId);
  }, [projectId, fetchConnections]);

  const isLLM = selectedEngine === "llm";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">
          Synthetic Data Generation
        </h1>
        <p className="text-xs text-muted-foreground">
          Generate synthetic data into a connected database. File-based
          generation has moved to the Files workspace.
        </p>
      </header>

      <EngineSelector />

      {isLLM && (
        <Select
          label="Source Connection"
          fullWidth={false}
          value={selectedConnection}
          onChange={(e) => setSelectedConnection(e.target.value)}
          className="min-w-[260px]"
          selectSize="md"
        >
          <option value="">Select connection…</option>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      )}

      {isLLM ? (
        <>
          <NLPPromptForm
            projectId={projectId}
            connectionId={selectedConnection}
            onPlanGenerated={setNlpPlan}
          />
          {nlpPlan && (
            <GenerationPlanEditor
              plan={nlpPlan}
              projectId={projectId}
              connectionId={selectedConnection}
            />
          )}
        </>
      ) : (
        <>
          <ConfigForm projectId={projectId} />
          <PreviewTable data={previewData} loading={previewLoading} />
          <QualityReport projectId={projectId} configId={lastConfigId} />
        </>
      )}
    </div>
  );
}
