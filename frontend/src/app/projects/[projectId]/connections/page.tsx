"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Plus } from "lucide-react";
import { ConnectionList } from "@/components/connections/connection-list";
import { ConnectionFormDrawer } from "@/components/connections/connection-form-drawer";
import { SchemaChangesPanel } from "@/components/connections/schema-changes-panel";
import { useConnectionStore } from "@/stores/connection-store";

interface EditTarget {
  id: string;
  name: string;
  connector_type: string;
  host: string;
  port: number;
  database_name: string;
  username?: string;
  safe_extras?: Record<string, unknown>;
}

export default function ConnectionsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const [showDrawer, setShowDrawer] = useState(false);
  const [editTarget, setEditTarget] = useState<EditTarget | null>(null);
  const fetchConnections = useConnectionStore((s) => s.fetchConnections);
  const connections = useConnectionStore((s) => s.connections);

  useEffect(() => {
    fetchConnections(projectId);
  }, [projectId, fetchConnections]);

  const handleEdit = (conn: EditTarget) => {
    setEditTarget(conn);
    setShowDrawer(true);
  };

  const handleClose = () => {
    setShowDrawer(false);
    setEditTarget(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Connections</h1>
        <button
          onClick={() => { setEditTarget(null); setShowDrawer(true); }}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Connection
        </button>
      </div>

      <ConnectionList projectId={projectId} onAddClick={() => { setEditTarget(null); setShowDrawer(true); }} onEdit={handleEdit} />

      {connections.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Schema changes
          </h2>
          {connections.map((conn) => (
            <SchemaChangesPanel
              key={conn.id}
              projectId={projectId}
              connectionId={conn.id}
              connectionName={conn.name}
            />
          ))}
        </div>
      )}

      <ConnectionFormDrawer
        open={showDrawer}
        onClose={handleClose}
        projectId={projectId}
        editConnection={editTarget}
      />
    </div>
  );
}
