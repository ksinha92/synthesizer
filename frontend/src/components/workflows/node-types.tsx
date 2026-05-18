"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { FileSearch, Lock, Shuffle, TestTube } from "lucide-react";
import { cn } from "@/lib/utils";

const NODE_STYLES: Record<string, { bg: string; border: string; icon: typeof FileSearch }> = {
  discovery: { bg: "bg-blue-500/10", border: "border-blue-500/30", icon: FileSearch },
  masking: { bg: "bg-orange-500/10", border: "border-orange-500/30", icon: Lock },
  synthetic: { bg: "bg-green-500/10", border: "border-green-500/30", icon: TestTube },
  subsetting: { bg: "bg-purple-500/10", border: "border-purple-500/30", icon: Shuffle },
};

const STATUS_DOT: Record<string, string> = {
  pending: "bg-gray-400",
  running: "bg-blue-500 animate-pulse",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

function WorkflowNode({ data, selected }: NodeProps) {
  const nodeType = (data as any).nodeType || "discovery";
  const status = (data as any).status || "pending";
  const label = (data as any).label || nodeType;
  const style = NODE_STYLES[nodeType] || NODE_STYLES.discovery;
  const Icon = style.icon;

  return (
    <div className={cn(
      "rounded-lg border-2 px-4 py-3 min-w-[140px] shadow-sm transition-all",
      style.bg, style.border,
      selected && "ring-2 ring-primary ring-offset-2 ring-offset-background"
    )}>
      {nodeType !== "discovery" && (
        <Handle type="target" position={Position.Top} className="!bg-foreground/50 !w-3 !h-3 !border-2 !border-background" />
      )}

      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-foreground" />
        <span className="text-sm font-medium text-foreground capitalize">{label}</span>
        <span className={cn("h-2 w-2 rounded-full ml-auto", STATUS_DOT[status])} />
      </div>

      {(data as any).configSummary && (
        <p className="text-[10px] text-muted-foreground mt-1 truncate">{(data as any).configSummary}</p>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-foreground/50 !w-3 !h-3 !border-2 !border-background" />
    </div>
  );
}

export const nodeTypes = {
  discovery: memo(WorkflowNode),
  masking: memo(WorkflowNode),
  synthetic: memo(WorkflowNode),
  subsetting: memo(WorkflowNode),
};
