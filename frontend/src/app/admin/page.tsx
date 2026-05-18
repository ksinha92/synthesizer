"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { AuditLogViewer } from "@/components/admin/audit-log-viewer";
import { RBACManager } from "@/components/admin/rbac-manager";
import { LLMSettingsPanel } from "@/components/admin/llm-settings";
import { WebhookManager } from "@/components/admin/webhook-manager";
import { EncryptionKeyRotation } from "@/components/admin/encryption-key-rotation";
import { DeadLetterQueue } from "@/components/admin/dead-letter-queue";
import { cn } from "@/lib/utils";

type Tab = "audit" | "rbac" | "ai" | "webhooks" | "security" | "dlq";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("audit");

  const tabs: { key: Tab; label: string }[] = [
    { key: "audit", label: "Audit Log" },
    { key: "rbac", label: "Access Control" },
    { key: "ai", label: "AI Settings" },
    { key: "webhooks", label: "Webhooks" },
    { key: "security", label: "Security" },
    { key: "dlq", label: "Dead Letter Queue" },
  ];

  return (
    <AppShell>
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Admin</h1>

        <div className="flex items-center gap-1 border-b border-border overflow-x-auto">
          {tabs.map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)} className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap",
              activeTab === tab.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            )}>
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "audit" && <AuditLogViewer />}
        {activeTab === "rbac" && <RBACManager />}
        {activeTab === "ai" && <LLMSettingsPanel />}
        {activeTab === "webhooks" && <WebhookManager />}
        {activeTab === "security" && <EncryptionKeyRotation />}
        {activeTab === "dlq" && <DeadLetterQueue />}
      </div>
    </AppShell>
  );
}
