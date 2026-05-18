"use client";

import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { api } from "@/hooks/use-api";
import { EmptyState } from "@/components/common/empty-state";

interface AuditEntry { id: string; user_id: string | null; action: string; resource_type: string | null; ip_address: string | null; status_code: number | null; created_at: string; }

export function AuditLogViewer() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLogs = async () => {
      setLoading(true);
      try {
        const data = await api.get<{ logs: AuditEntry[]; total_count: number }>("/api/v1/admin/audit-logs?page=1&page_size=50");
        setLogs(data.logs);
        setTotalCount(data.total_count);
      } catch { /* */ }
      setLoading(false);
    };
    fetchLogs();
  }, []);

  if (!loading && logs.length === 0) {
    return <EmptyState icon={ScrollText} title="No audit entries" description="API actions will be logged here." />;
  }

  const columns: ColumnsType<AuditEntry> = [
    {
      title: "Time",
      dataIndex: "created_at",
      key: "created_at",
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      render: (t: string) => <span className="whitespace-nowrap text-xs">{new Date(t).toLocaleString()}</span>,
      width: 180,
    },
    {
      title: "User",
      dataIndex: "user_id",
      key: "user_id",
      render: (id: string | null) => <span className="font-mono text-xs">{id?.slice(0, 8) || "—"}</span>,
      width: 100,
    },
    {
      title: "Action",
      dataIndex: "action",
      key: "action",
      filters: Array.from(new Set(logs.map((l) => l.action))).map((a) => ({ text: a, value: a })),
      onFilter: (value, record) => record.action === value,
      render: (action: string) => <span className="font-medium">{action}</span>,
    },
    {
      title: "Resource",
      dataIndex: "resource_type",
      key: "resource_type",
      render: (r: string | null) => r || "—",
    },
    {
      title: "Status",
      dataIndex: "status_code",
      key: "status_code",
      render: (code: number | null) => {
        if (!code) return "—";
        return <Tag color={code < 400 ? "green" : "red"}>{code}</Tag>;
      },
      width: 80,
    },
    {
      title: "IP",
      dataIndex: "ip_address",
      key: "ip_address",
      render: (ip: string | null) => <span className="font-mono text-xs">{ip || "—"}</span>,
      width: 120,
    },
  ];

  return (
    <div className="space-y-4">
      <span className="text-xs text-muted-foreground">{totalCount} audit entries</span>
      <div className="ant-scoped">
        <Table<AuditEntry>
          columns={columns}
          dataSource={logs}
          rowKey="id"
          size="small"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `${total} entries` }}
        />
      </div>
    </div>
  );
}
