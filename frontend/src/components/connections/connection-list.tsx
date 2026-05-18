"use client";

import { Database } from "lucide-react";
import { useConnectionStore } from "@/stores/connection-store";
import { ConnectionCard } from "./connection-card";
import { EmptyState } from "@/components/common/empty-state";

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

interface ConnectionListProps {
  projectId: string;
  onAddClick: () => void;
  onEdit: (conn: EditTarget) => void;
}

export function ConnectionList({ projectId, onAddClick, onEdit }: ConnectionListProps) {
  const { connections, loading, testResults, testingIds, testConnection, deleteConnection } = useConnectionStore();

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {[1, 2].map((i) => (
          <div key={i} className="h-36 animate-pulse rounded-lg border border-border bg-muted" />
        ))}
      </div>
    );
  }

  if (connections.length === 0) {
    return (
      <EmptyState
        icon={Database}
        title="No connections yet"
        description="Add your first data source connection to start discovering schemas."
        action={{ label: "Add Connection", onClick: onAddClick }}
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {connections.map((conn) => (
        <ConnectionCard
          key={conn.id}
          id={conn.id}
          name={conn.name}
          connector_type={conn.connector_type}
          host={conn.host}
          port={conn.port}
          database_name={conn.database_name}
          status={conn.status}
          last_tested_at={conn.last_tested_at}
          testing={testingIds.has(conn.id)}
          testResult={testResults[conn.id] || null}
          onTest={() => testConnection(projectId, conn.id)}
          onEdit={() => onEdit({
            id: conn.id,
            name: conn.name,
            connector_type: conn.connector_type,
            host: conn.host,
            port: conn.port,
            database_name: conn.database_name,
            username: conn.username,
            safe_extras: conn.safe_extras,
          })}
          onDelete={() => deleteConnection(projectId, conn.id)}
        />
      ))}
    </div>
  );
}
