"use client";

import { useState } from "react";
import { ArrowRight, Plus, Trash2, X } from "lucide-react";
import { useWorkflowStore } from "@/stores/workflow-store";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { cn } from "@/lib/utils";


// Phase 59 F11: quality_check has been removed from the palette.
const NODE_TYPES = [
  { value: "discovery", label: "Discover", color: "bg-blue-500" },
  { value: "masking", label: "Mask", color: "bg-amber-500" },
  { value: "synthetic", label: "Generate", color: "bg-green-500" },
  { value: "subsetting", label: "Subset", color: "bg-purple-500" },
] as const;

interface WorkflowNode {
  id: string;
  type: string;
}

interface WorkflowEditorProps { open: boolean; onClose: () => void; projectId: string; }

export function WorkflowEditor({ open, onClose, projectId }: WorkflowEditorProps) {
  const [name, setName] = useState("");
  const [nodes, setNodes] = useState<WorkflowNode[]>([
    { id: "n1", type: "discovery" },
    { id: "n2", type: "subsetting" },
    { id: "n3", type: "masking" },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { createWorkflow } = useWorkflowStore();

  const addNode = () => {
    const id = `n${Date.now()}`;
    setNodes([...nodes, { id, type: "masking" }]);
  };

  const removeNode = (id: string) => {
    if (nodes.length <= 1) return;
    setNodes(nodes.filter((n) => n.id !== id));
  };

  const updateNodeType = (id: string, type: string) => {
    setNodes(nodes.map((n) => (n.id === id ? { ...n, type } : n)));
  };

  const buildDAG = () => {
    const dagNodes = nodes.map((n, i) => ({
      id: n.id,
      type: n.type,
      config: {},
      position: { x: 100 + i * 200, y: 100 },
    }));
    const edges = nodes.slice(0, -1).map((n, i) => ({
      source_node_id: n.id,
      target_node_id: nodes[i + 1].id,
    }));
    return { nodes: dagNodes, edges };
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    setError("");
    try {
      await createWorkflow(projectId, { name: name.trim(), dag_definition: buildDAG() });
      setName("");
      setNodes([{ id: "n1", type: "discovery" }, { id: "n2", type: "subsetting" }, { id: "n3", type: "masking" }]);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create");
    }
    setSaving(false);
  };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50" onClick={onClose} />
      <AccessibleDialog open={open} onClose={onClose} titleId="workflow-editor-title" className="fixed inset-y-0 right-0 z-50 w-full max-w-full sm:max-w-[600px] border-l border-border bg-card shadow-xl overflow-y-auto">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 id="workflow-editor-title" className="text-lg font-semibold text-foreground">Create Workflow</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>

        <div className="px-6 py-4 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Workflow Name *</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Nightly Data Refresh" className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm" />
          </div>

          {/* Node builder */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="block text-xs font-medium text-foreground">Pipeline Steps</label>
              <button onClick={addNode} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">
                <Plus className="h-3 w-3" /> Add Step
              </button>
            </div>

            <div className="space-y-2">
              {nodes.map((node, idx) => {
                const typeDef = NODE_TYPES.find((t) => t.value === node.type);
                return (
                  <div key={node.id} className="flex items-center gap-2">
                    {idx > 0 && (
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0 -ml-1 mr-0" />
                    )}
                    <span className="text-xs text-muted-foreground w-5 shrink-0">{idx + 1}.</span>
                    <div className={cn("h-2.5 w-2.5 rounded-full shrink-0", typeDef?.color || "bg-gray-400")} />
                    <select
                      value={node.type}
                      onChange={(e) => updateNodeType(node.id, e.target.value)}
                      className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                    >
                      {NODE_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => removeNode(node.id)}
                      disabled={nodes.length <= 1}
                      className="text-muted-foreground hover:text-destructive disabled:opacity-30"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Visual preview */}
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-[10px] text-muted-foreground mb-2">Pipeline Preview</p>
            <div className="flex items-center gap-1.5 flex-wrap">
              {nodes.map((node, idx) => {
                const typeDef = NODE_TYPES.find((t) => t.value === node.type);
                return (
                  <div key={node.id} className="flex items-center gap-1.5">
                    <span className={cn("rounded-md px-2.5 py-1 text-xs font-medium text-white", typeDef?.color || "bg-gray-500")}>
                      {typeDef?.label || node.type}
                    </span>
                    {idx < nodes.length - 1 && <ArrowRight className="h-3 w-3 text-muted-foreground" />}
                  </div>
                );
              })}
            </div>
          </div>

          {error && <p className="text-xs text-destructive" role="alert">{error}</p>}
        </div>

        <div className="border-t border-border px-6 py-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground">Cancel</button>
          <button onClick={handleSave} disabled={!name.trim() || nodes.length === 0 || saving} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
            {saving ? "Creating..." : "Create Workflow"}
          </button>
        </div>
      </AccessibleDialog>
    </>
  );
}
