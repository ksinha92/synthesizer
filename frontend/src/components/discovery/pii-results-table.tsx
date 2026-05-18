"use client";

import { useState } from "react";
import { AlertTriangle, FileSearch } from "lucide-react";
import { Table, Tag, Progress } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useDiscoveryStore } from "@/stores/discovery-store";
import { PIIBadge } from "./pii-badge";
import { ScanResultsSummary } from "./scan-results-summary";
import { EmptyState } from "@/components/common/empty-state";

const PII_TYPES = ["email", "phone", "ssn", "credit_card", "ip_address", "person_name", "address", "date_of_birth", "medical_record", "financial_account", "other"];
const CLASSIFICATIONS = ["auto_classified", "needs_review", "manually_classified", "dismissed"];

interface PIIColumn {
  id: string;
  column_name: string;
  data_type: string;
  pii_type: string;
  confidence: number;
  detector: string;
  classification: string;
}

export function PIIResultsTable({ projectId }: { projectId: string }) {
  const { piiColumns, piiLoading, overrideClassification } = useDiscoveryStore();
  const [overrideCol, setOverrideCol] = useState<string | null>(null);
  const [newType, setNewType] = useState("");
  const [note, setNote] = useState("");

  if (piiLoading) return <div className="py-8 text-center text-sm text-muted-foreground">Loading PII results...</div>;
  if (piiColumns.length === 0) return <EmptyState icon={FileSearch} title="No PII detections" description="Run discovery on a connection to detect PII columns." />;

  const columns: ColumnsType<PIIColumn> = [
    {
      title: "Column",
      dataIndex: "column_name",
      key: "column_name",
      sorter: (a, b) => a.column_name.localeCompare(b.column_name),
      render: (name: string, record) => (
        <div>
          <span className="text-sm font-medium">{name}</span>
          <br />
          <span className="text-xs text-gray-500 font-mono">{record.data_type}</span>
        </div>
      ),
    },
    {
      title: "PII Type",
      dataIndex: "pii_type",
      key: "pii_type",
      filters: PII_TYPES.map((t) => ({ text: t.replace("_", " "), value: t })),
      onFilter: (value, record) => record.pii_type === value,
      render: (type: string, record) => (
        <PIIBadge piiType={type} confidence={record.confidence} classification={record.classification} size="md" />
      ),
    },
    {
      title: "Confidence",
      dataIndex: "confidence",
      key: "confidence",
      sorter: (a, b) => a.confidence - b.confidence,
      render: (conf: number) => (
        <div className="flex items-center gap-2">
          <Progress
            percent={Math.round(conf * 100)}
            size="small"
            strokeColor={conf >= 0.65 ? "#EF4444" : conf >= 0.4 ? "#F59E0B" : "#9CA3AF"}
            showInfo={false}
            style={{ width: 60 }}
          />
          <span className="text-xs">{Math.round(conf * 100)}%</span>
        </div>
      ),
    },
    {
      title: "Detector",
      dataIndex: "detector",
      key: "detector",
    },
    {
      title: "Status",
      dataIndex: "classification",
      key: "classification",
      filters: CLASSIFICATIONS.map((c) => ({ text: c.replace("_", " "), value: c })),
      onFilter: (value, record) => record.classification === value,
      render: (cls: string) => (
        <Tag color={cls === "auto_classified" ? "green" : cls === "needs_review" ? "orange" : cls === "manually_classified" ? "blue" : "default"}>
          {cls.replace("_", " ")}
        </Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      align: "right" as const,
      render: (_: unknown, record: PIIColumn) => (
        <button
          onClick={() => setOverrideCol(record.id)}
          className="text-xs text-blue-600 hover:underline"
        >
          Override
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <ScanResultsSummary columns={piiColumns as PIIColumn[]} />

      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{piiColumns.length} PII columns detected</span>
      </div>

      <div className="ant-scoped">
        <Table<PIIColumn>
          columns={columns}
          dataSource={piiColumns as PIIColumn[]}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `${total} columns` }}
        />
      </div>
    </div>
  );
}
