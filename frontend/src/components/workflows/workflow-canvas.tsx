"use client";

import { useCallback, useRef, useState } from "react";
import {
  ReactFlow,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Code, Eye, Loader2, Play, Save } from "lucide-react";
import { nodeTypes } from "./node-types";
import { NodePalette } from "./node-palette";
import { NodeConfigPanel } from "./node-config-panel";
import { cn } from "@/lib/utils";

// Edge compatibility rules (must match backend domain/workflow/services.py).
// Phase 59 F11: quality_check has been removed.
const EDGE_RULES: Record<string, Set<string>> = {
  discovery: new Set(["masking", "synthetic", "subsetting"]),
  masking: new Set(),
  synthetic: new Set(["masking"]),
  subsetting: new Set(["masking", "synthetic"]),
};

// Aliases from the pre-rename palette. Normalize on load so DAGs saved before the
// rename keep rendering (and re-save in the new vocabulary). The legacy
// ``export`` alias previously mapped to ``quality_check`` — both are gone.
const NODE_TYPE_ALIASES: Record<string, string> = {
  discover: "discovery",
  mask: "masking",
  generate: "synthetic",
  subset: "subsetting",
};

const canonicalizeNodeType = (t: string): string => NODE_TYPE_ALIASES[t] ?? t;

interface WorkflowCanvasProps {
  initialDag: { nodes: any[]; edges: any[] };
  onSave: (dag: { nodes: any[]; edges: any[] }) => Promise<void>;
  onExecute: () => Promise<void>;
}

export function WorkflowCanvas({ initialDag, onSave, onExecute }: WorkflowCanvasProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  const initialNodes: Node[] = (initialDag.nodes || []).map((n: any) => {
    const canonical = canonicalizeNodeType(n.type);
    return {
      id: n.id,
      type: canonical,
      position: n.position || { x: 0, y: 0 },
      data: { nodeType: canonical, label: canonical, config: n.config || {}, status: "pending" },
    };
  });

  const initialEdges: Edge[] = (initialDag.edges || []).map((e: any, i: number) => ({
    id: `e-${i}`,
    source: e.source_node_id || e.source,
    target: e.target_node_id || e.target,
    animated: true,
  }));

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [viewMode, setViewMode] = useState<"visual" | "code">("visual");
  const [jsonText, setJsonText] = useState("");
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);

  const onConnect = useCallback((connection: Connection) => {
    const sourceNode = nodes.find((n) => n.id === connection.source);
    const targetNode = nodes.find((n) => n.id === connection.target);
    if (!sourceNode || !targetNode) return;

    const sourceType = (sourceNode.data as any).nodeType || sourceNode.type;
    const targetType = (targetNode.data as any).nodeType || targetNode.type;
    const allowed = EDGE_RULES[sourceType];
    if (!allowed || !allowed.has(targetType)) return; // Invalid edge — silently reject

    setEdges((eds) => addEdge({ ...connection, animated: true }, eds));
  }, [nodes, setEdges]);

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    const rawType = event.dataTransfer.getData("application/reactflow");
    if (!rawType) return;
    const nodeType = canonicalizeNodeType(rawType);

    const bounds = reactFlowWrapper.current?.getBoundingClientRect();
    if (!bounds) return;

    const newNode: Node = {
      id: `node-${Date.now()}`,
      type: nodeType,
      position: { x: event.clientX - bounds.left - 70, y: event.clientY - bounds.top - 20 },
      data: { nodeType, label: nodeType, config: {}, status: "pending" },
    };
    setNodes((nds) => [...nds, newNode]);
  }, [setNodes]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onNodeClick = useCallback((_: any, node: Node) => setSelectedNode(node), []);

  const updateNodeConfig = useCallback((nodeId: string, config: Record<string, unknown>) => {
    setNodes((nds) => nds.map((n) => n.id === nodeId ? { ...n, data: { ...n.data, config } } : n));
  }, [setNodes]);

  const buildDag = () => ({
    nodes: nodes.map((n) => ({
      id: n.id, type: (n.data as any).nodeType || n.type,
      config: (n.data as any).config || {}, position: n.position,
    })),
    edges: edges.map((e) => ({ source_node_id: e.source, target_node_id: e.target })),
  });

  const handleSave = async () => {
    setSaving(true);
    const dag = viewMode === "visual" ? buildDag() : JSON.parse(jsonText || JSON.stringify(buildDag()));
    await onSave(dag);
    setSaving(false);
  };

  const handleExecute = async () => {
    setExecuting(true);
    await onExecute();
    setExecuting(false);
  };

  const toggleMode = () => {
    if (viewMode === "visual") {
      setJsonText(JSON.stringify(buildDag(), null, 2));
      setViewMode("code");
    } else {
      try {
        const dag = JSON.parse(jsonText);
        setNodes(dag.nodes.map((n: any) => {
          const canonical = canonicalizeNodeType(n.type);
          return {
            id: n.id, type: canonical, position: n.position || { x: 0, y: 0 },
            data: { nodeType: canonical, label: canonical, config: n.config || {}, status: "pending" },
          };
        }));
        setEdges(dag.edges.map((e: any, i: number) => ({
          id: `e-${i}`, source: e.source_node_id, target: e.target_node_id, animated: true,
        })));
      } catch { /* keep current */ }
      setViewMode("visual");
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] rounded-lg border border-border overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-2">
        <div className="flex items-center gap-0.5 rounded-lg border border-border p-0.5">
          <button onClick={() => { if (viewMode !== "visual") toggleMode(); }} className={cn("rounded-md p-1.5", viewMode === "visual" ? "bg-muted" : "")}><Eye className="h-3.5 w-3.5" /></button>
          <button onClick={() => { if (viewMode !== "code") toggleMode(); }} className={cn("rounded-md p-1.5", viewMode === "code" ? "bg-muted" : "")}><Code className="h-3.5 w-3.5" /></button>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleSave} disabled={saving} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50">
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save
          </button>
          <button onClick={handleExecute} disabled={executing} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
            {executing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />} Execute
          </button>
        </div>
      </div>

      {/* Canvas / Code */}
      <div className="flex flex-1 overflow-hidden">
        {viewMode === "visual" ? (
          <>
            <NodePalette />
            <div ref={reactFlowWrapper} className="flex-1" onDrop={onDrop} onDragOver={onDragOver}>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                fitView
                className="bg-background"
              >
                <Background />
                <Controls />
                <MiniMap />
              </ReactFlow>
            </div>
          </>
        ) : (
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            className="flex-1 bg-background p-4 text-xs font-mono text-foreground resize-none focus:outline-none"
          />
        )}
      </div>

      {/* Config panel */}
      {viewMode === "visual" && (
        <NodeConfigPanel
          node={selectedNode as any}
          onUpdate={updateNodeConfig}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
