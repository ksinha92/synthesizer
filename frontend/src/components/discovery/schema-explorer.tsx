"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown, Table2, Columns3, Search } from "lucide-react";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { PIIDot } from "./pii-badge";
import { ColumnDetail } from "./column-detail";
import { cn } from "@/lib/utils";

export function SchemaExplorer({ projectId }: { projectId: string }) {
  const { schemas, selectedColumn, selectColumn, overrideClassification, loading } = useDiscoveryStore();
  const [search, setSearch] = useState("");
  const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(new Set());
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  const toggleSchema = (id: string) => {
    const next = new Set(expandedSchemas);
    next.has(id) ? next.delete(id) : next.add(id);
    setExpandedSchemas(next);
  };

  const toggleTable = (id: string) => {
    const next = new Set(expandedTables);
    next.has(id) ? next.delete(id) : next.add(id);
    setExpandedTables(next);
  };

  if (loading) {
    return <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">Loading schema...</div>;
  }

  if (schemas.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        No discovery results yet. Run discovery on a connection first.
      </div>
    );
  }

  const filterMatch = (name: string) => !search || name.toLowerCase().includes(search.toLowerCase());

  return (
    <div className="flex h-[calc(100vh-200px)] rounded-lg border border-border overflow-hidden">
      {/* Tree (left) */}
      <div className="w-[300px] shrink-0 border-r border-border overflow-y-auto bg-card">
        <div className="sticky top-0 z-10 border-b border-border bg-card p-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter columns..."
              className="w-full rounded-md border border-input bg-background pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        </div>

        <div className="p-1">
          {schemas.map((schema) => (
            <div key={schema.id}>
              <button
                onClick={() => toggleSchema(schema.id)}
                className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
              >
                {expandedSchemas.has(schema.id) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                {schema.schema_name}
              </button>

              {expandedSchemas.has(schema.id) && schema.tables.map((table) => (
                <div key={table.id} className="pl-4">
                  <button
                    onClick={() => toggleTable(table.id)}
                    className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-xs text-foreground hover:bg-muted"
                  >
                    {expandedTables.has(table.id) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    <Table2 className="h-3 w-3 text-muted-foreground" />
                    <span className="truncate">{table.table_name}</span>
                    <span className="ml-auto text-[10px] text-muted-foreground">{table.row_count}</span>
                  </button>

                  {expandedTables.has(table.id) && table.columns.filter((c) => filterMatch(c.column_name)).map((col) => (
                    <button
                      key={col.id}
                      onClick={() => selectColumn(col)}
                      className={cn(
                        "flex w-full items-center gap-1.5 rounded-md px-2 py-1 pl-10 text-xs hover:bg-muted",
                        selectedColumn?.id === col.id ? "bg-primary/10 text-primary" : "text-muted-foreground"
                      )}
                    >
                      <Columns3 className="h-3 w-3 shrink-0" />
                      <span className="truncate">{col.column_name}</span>
                      <span className="ml-auto text-[10px] opacity-60">{col.data_type}</span>
                      <PIIDot piiType={col.pii_type} confidence={col.pii_confidence} />
                    </button>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Detail (right) */}
      <div className="flex-1 overflow-y-auto bg-background">
        <ColumnDetail
          column={selectedColumn}
          onOverride={(colId, type, note) => overrideClassification(projectId, colId, type, note)}
        />
      </div>
    </div>
  );
}
