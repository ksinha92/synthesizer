"use client";

import { FileSearch, Lock, Shuffle, TestTube } from "lucide-react";
import { cn } from "@/lib/utils";

const NODE_TYPES = [
  { type: "discovery", label: "Discover", icon: FileSearch, color: "text-blue-500" },
  { type: "masking", label: "Mask", icon: Lock, color: "text-orange-500" },
  { type: "synthetic", label: "Generate", icon: TestTube, color: "text-green-500" },
  { type: "subsetting", label: "Subset", icon: Shuffle, color: "text-purple-500" },
];

export function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <div className="w-[160px] shrink-0 border-r border-border bg-card p-3 space-y-2">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Nodes</p>
      {NODE_TYPES.map(({ type, label, icon: Icon, color }) => (
        <div
          key={type}
          draggable
          onDragStart={(e) => onDragStart(e, type)}
          className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 cursor-grab hover:bg-muted transition-colors active:cursor-grabbing"
        >
          <Icon className={cn("h-4 w-4", color)} />
          <span className="text-xs font-medium text-foreground">{label}</span>
        </div>
      ))}
    </div>
  );
}
