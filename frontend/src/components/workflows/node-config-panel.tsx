"use client";

import { X } from "lucide-react";

interface NodeConfigPanelProps {
  node: { id: string; type: string; data: Record<string, unknown> } | null;
  onUpdate: (nodeId: string, config: Record<string, unknown>) => void;
  onClose: () => void;
}

// Pre-rename aliases — keep so a legacy DAG opened in this panel still matches a branch.
// Phase 59 F11: quality_check (and its ``export`` alias) have been removed.
const NODE_TYPE_ALIASES: Record<string, string> = {
  discover: "discovery",
  mask: "masking",
  generate: "synthetic",
  subset: "subsetting",
};

export function NodeConfigPanel({ node, onUpdate, onClose }: NodeConfigPanelProps) {
  if (!node) return null;

  const config = (node.data as any).config || {};
  const nodeType = NODE_TYPE_ALIASES[node.type] ?? node.type;

  return (
    <div className="h-[200px] border-t border-border bg-card p-4 overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-foreground capitalize">Configure: {nodeType}</h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>

      <div className="space-y-3 text-sm">
        {nodeType === "discovery" && (
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Connection ID</label>
            <input type="text" value={config.connection_id || ""} onChange={e => onUpdate(node.id, { ...config, connection_id: e.target.value })} placeholder="UUID" className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono" />
          </div>
        )}
        {nodeType === "masking" && (
          <>
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">Policy ID</label>
              <input type="text" value={config.policy_id || ""} onChange={e => onUpdate(node.id, { ...config, policy_id: e.target.value })} placeholder="UUID" className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono" />
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">Connection ID</label>
              <input type="text" value={config.connection_id || ""} onChange={e => onUpdate(node.id, { ...config, connection_id: e.target.value })} placeholder="UUID" className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono" />
            </div>
          </>
        )}
        {nodeType === "synthetic" && (
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Config ID</label>
            <input type="text" value={config.config_id || ""} onChange={e => onUpdate(node.id, { ...config, config_id: e.target.value })} placeholder="UUID" className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono" />
          </div>
        )}
        {nodeType === "subsetting" && (
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Subset Config ID</label>
            <input type="text" value={config.config_id || ""} onChange={e => onUpdate(node.id, { ...config, config_id: e.target.value })} placeholder="UUID" className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono" />
          </div>
        )}
      </div>
    </div>
  );
}
