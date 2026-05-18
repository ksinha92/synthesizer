"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, Loader2, Play } from "lucide-react";
import { useSyntheticStore } from "@/stores/synthetic-store";
import { useConnectionStore } from "@/stores/connection-store";
import { FormField } from "@/components/common/form-field";
import { ConfirmGenerateDrawer } from "@/components/synthetic/confirm-generate-drawer";

const configSchema = z.object({
  name: z.string().trim().optional().default(""),
  connectionId: z.string().min(1, "Source connection is required"),
  rowCount: z.coerce.number().int("Must be a whole number").min(1, "Minimum 1 row").max(100000, "Maximum 100,000 rows"),
  seed: z.string().optional().default(""),
});

type ConfigFormData = z.infer<typeof configSchema>;

interface ConfigFormProps {
  projectId: string;
}

export function ConfigForm({ projectId }: ConfigFormProps) {
  const [configId, setConfigId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const { connections } = useConnectionStore();
  const { createConfig, preview, generate, previewLoading, generating } = useSyntheticStore();

  const { control, getValues, watch } = useForm<ConfigFormData>({
    resolver: zodResolver(configSchema),
    defaultValues: { name: "", connectionId: "", rowCount: 100, seed: "" },
  });

  const connectionId = watch("connectionId");
  const rowCount = watch("rowCount");
  const configName = watch("name");
  const seedValue = watch("seed");
  const connection = connections.find((c) => c.id === connectionId);

  const getOrCreateConfig = async (): Promise<string | null> => {
    if (configId) return configId;
    const vals = getValues();
    const config = await createConfig(projectId, {
      name: vals.name || "Preview Config",
      source_connection_id: vals.connectionId,
      generation_method: "faker",
      row_count: vals.rowCount,
      config: vals.seed ? { seed: Number(vals.seed) } : {},
      tables: [],
    });
    if (config) {
      setConfigId(config.id);
      return config.id;
    }
    return null;
  };

  const handlePreview = async () => {
    const cid = await getOrCreateConfig();
    if (cid) await preview(projectId, cid);
  };

  // The Generate button now opens a Tonic-style pre-flight drawer instead
  // of firing immediately. Confirm runs the actual job — keeps the existing
  // create-config-on-demand flow intact.
  const handleConfirmGenerate = async () => {
    const cid = await getOrCreateConfig();
    if (cid) {
      const jid = await generate(projectId, cid);
      if (jid) setJobId(jid);
    }
    setConfirmOpen(false);
  };

  const connOptions = connections.map((c) => ({ value: c.id, label: c.name }));

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-5">
      <h3 className="text-sm font-semibold text-foreground">Configuration</h3>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField control={control} name="name" label="Config Name" placeholder="My generation config" />
        <FormField control={control} name="connectionId" label="Source Connection" type="select" required options={connOptions} placeholder="Select connection..." />
        <FormField control={control} name="rowCount" label="Row Count" type="number" min={1} max={100000} />
        <FormField control={control} name="seed" label="Seed (optional)" type="number" placeholder="For reproducible output" />
      </div>

      <div className="flex items-center gap-2 pt-2">
        <button
          onClick={handlePreview}
          disabled={!connectionId || previewLoading}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
        >
          {previewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
          Preview (10 rows)
        </button>
        <button
          onClick={() => setConfirmOpen(true)}
          disabled={!connectionId || generating}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          Generate
        </button>
        {jobId && <span className="text-xs text-muted-foreground">Job: {jobId.slice(0, 8)}...</span>}
      </div>

      <ConfirmGenerateDrawer
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleConfirmGenerate}
        generating={generating}
        configName={configName || "Preview Config"}
        connectionName={connection?.name ?? "—"}
        rowCount={Number(rowCount) || 0}
        engine="faker"
        seed={seedValue || undefined}
        outputMode="same_database"
        warning={
          Number(rowCount) > 50000
            ? "Generating more than 50,000 rows can take several minutes; the job will run in the background."
            : undefined
        }
      />
    </div>
  );
}
