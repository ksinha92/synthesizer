"use client";

import { Shield, Plus } from "lucide-react";
import { useMaskingStore } from "@/stores/masking-store";
import { EmptyState } from "@/components/common/empty-state";

interface MaskingPolicyListProps { projectId: string; onCreateClick: () => void; }

export function MaskingPolicyList({ projectId, onCreateClick }: MaskingPolicyListProps) {
  const { policies, loading } = useMaskingStore();

  if (loading) return <div className="space-y-2">{[1,2].map(i => <div key={i} className="h-20 animate-pulse rounded-lg border border-border bg-muted" />)}</div>;
  if (policies.length === 0) return <EmptyState icon={Shield} title="No masking policies" description="Create a policy to define how PII columns should be masked." action={{ label: "Create Policy", onClick: onCreateClick }} />;

  return (
    <div className="space-y-3">
      {policies.map(p => (
        <div key={p.id} className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-foreground">{p.name}</h3>
              <p className="text-xs text-muted-foreground">{p.description || "No description"}</p>
            </div>
            {p.is_default && <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">Default</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
