"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  Lightbulb,
  ListChecks,
  Settings2,
  Terminal,
  TriangleAlert,
  X,
  type LucideIcon,
} from "lucide-react";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { cn } from "@/lib/utils";
import { getGuide, type ConnectorGuide, type GuideStep } from "@/content/connector-guides";
import { HandshakeAnimation } from "@/components/connections/handshake-animation";

interface ConnectorSetupDialogProps {
  connectorValue: string;
  open: boolean;
  onClose: () => void;
  onUseConnector?: (value: string) => void;
}

type TabKey = "overview" | "prereqs" | "setup" | "test" | "troubleshoot";

const TABS: Array<{ key: TabKey; label: string; icon: LucideIcon }> = [
  { key: "overview", label: "Overview", icon: Lightbulb },
  { key: "prereqs", label: "Prerequisites", icon: ListChecks },
  { key: "setup", label: "Setup", icon: Settings2 },
  { key: "test", label: "Test", icon: Terminal },
  { key: "troubleshoot", label: "Troubleshoot", icon: TriangleAlert },
];

export function ConnectorSetupDialog({
  connectorValue,
  open,
  onClose,
  onUseConnector,
}: ConnectorSetupDialogProps) {
  const guide = getGuide(connectorValue);
  const [tab, setTab] = useState<TabKey>("overview");
  const titleId = `connector-setup-${connectorValue}-title`;

  if (!open) return null;
  if (!guide) {
    return (
      <>
        <div aria-hidden="true" className="fixed inset-0 z-[55] bg-black/50" onClick={onClose} />
        <AccessibleDialog
          open={open}
          onClose={onClose}
          titleId={titleId}
          className="fixed inset-x-0 top-[15%] z-[60] mx-auto w-[92%] max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl"
        >
          <h2 id={titleId} className="text-sm font-semibold text-foreground">
            No setup guide
          </h2>
          <p className="mt-2 text-xs text-muted-foreground">
            We don&rsquo;t have an interactive guide for this connector yet. The standard
            connection form still works — fill in host, port, and credentials.
          </p>
          <button
            type="button"
            onClick={onClose}
            className="mt-4 rounded-md border border-border bg-background px-3 py-1.5 text-xs hover:bg-muted/50"
          >
            Close
          </button>
        </AccessibleDialog>
      </>
    );
  }

  return (
    <>
      <div aria-hidden="true" className="fixed inset-0 z-[55] bg-black/50" onClick={onClose} />
      <AccessibleDialog
        open={open}
        onClose={onClose}
        titleId={titleId}
        className="fixed inset-x-0 top-[6%] z-[60] mx-auto flex w-[92%] max-w-4xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
      >
        <div style={{ maxHeight: "88vh" }} className="flex flex-col">
          {/* Header */}
          <header className="border-b border-border bg-gradient-to-br from-card to-muted/10 px-6 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Connector setup guide
                </p>
                <h2 id={titleId} className="mt-0.5 text-xl font-semibold text-foreground">
                  {guide.label}
                </h2>
                <p className="mt-1 max-w-2xl text-xs text-muted-foreground">{guide.summary}</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close connector setup guide"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Tabs */}
            <nav className="-mb-2 mt-4 flex flex-wrap gap-1" aria-label="Setup steps">
              {TABS.map((t) => {
                const Icon = t.icon;
                const active = tab === t.key;
                return (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setTab(t.key)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                      active
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground",
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {t.label}
                  </button>
                );
              })}
            </nav>
          </header>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {tab === "overview" && <OverviewTab guide={guide} />}
            {tab === "prereqs" && <PrereqsTab items={guide.prerequisites} />}
            {tab === "setup" && <SetupTab steps={guide.setup} />}
            {tab === "test" && (
              <TestTab
                command={guide.test.command}
                lang={guide.test.lang}
                note={guide.test.note}
              />
            )}
            {tab === "troubleshoot" && <TroubleshootTab items={guide.troubleshoot} />}
          </div>

          {/* Footer */}
          <footer className="flex flex-col gap-2 border-t border-border bg-muted/10 px-6 py-3 text-xs sm:flex-row sm:items-center sm:justify-between">
            <span className="text-muted-foreground">
              Default endpoint: <span className="font-mono text-foreground">{guide.defaults.host}:{guide.defaults.port}</span>
            </span>
            <div className="flex items-center gap-2">
              {onUseConnector && (
                <button
                  type="button"
                  onClick={() => {
                    onUseConnector(connectorValue);
                    onClose();
                  }}
                  className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Use {guide.label}
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-border bg-background px-3 py-1 text-xs hover:bg-muted/50"
              >
                Close
              </button>
            </div>
          </footer>
        </div>
      </AccessibleDialog>
    </>
  );
}

// ── Tab bodies ────────────────────────────────────────────────────────

function OverviewTab({ guide }: { guide: ConnectorGuide }) {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          What happens when you connect
        </h3>
        <p className="mt-2 text-sm text-foreground">
          Synthia opens a TCP connection on{" "}
          <span className="font-mono text-[12px]">{guide.defaults.port}</span>, authenticates with
          the credentials you provide, and runs a lightweight SELECT against the catalog to
          confirm reachability. Once saved, the credentials are encrypted at rest with Fernet.
        </p>
        <div className="mt-4 rounded-lg border border-border bg-background p-3 text-xs">
          <div className="grid grid-cols-2 gap-x-3 gap-y-2">
            <span className="text-muted-foreground">Default host</span>
            <span className="font-mono text-foreground">{guide.defaults.host}</span>
            <span className="text-muted-foreground">Default port</span>
            <span className="font-mono text-foreground">{guide.defaults.port}</span>
            <span className="text-muted-foreground">Example database</span>
            <span className="font-mono text-foreground">{guide.defaults.placeholderDb}</span>
          </div>
        </div>
      </div>
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Connection handshake
        </h3>
        <div className="mt-2 h-44">
          <HandshakeAnimation port={guide.defaults.port} dbLabel={guide.label} />
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Each step runs in order. If any one fails, Synthia surfaces the error in the connection
          test panel instead of saving.
        </p>
      </div>
    </div>
  );
}

function PrereqsTab({ items }: { items: string[] }) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Before you start
      </h3>
      <ul className="space-y-2">
        {items.map((p, i) => (
          <li key={i} className="flex gap-2 rounded-lg border border-border bg-background p-3 text-sm text-foreground">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden />
            <span>{p}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SetupTab({ steps }: { steps: GuideStep[] }) {
  return (
    <ol className="space-y-3">
      {steps.map((s, i) => (
        <li
          key={s.title}
          className="relative overflow-hidden rounded-xl border border-border bg-background p-4"
        >
          <div className="flex items-start gap-3">
            <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <h4 className="text-sm font-semibold text-foreground">{s.title}</h4>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{s.body}</p>
              {s.code && (
                <div className="mt-3">
                  <CodeBlock value={s.code.value} lang={s.code.lang} />
                </div>
              )}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function TestTab({
  command,
  lang,
  note,
}: {
  command: string;
  lang: "bash" | "sql";
  note: string;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Run this from your laptop first
      </h3>
      <CodeBlock value={command} lang={lang} />
      <p className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
        <Lightbulb className="mr-1 inline-block h-3.5 w-3.5 -translate-y-0.5 text-amber-500" />
        {note}
      </p>
    </div>
  );
}

function TroubleshootTab({
  items,
}: {
  items: Array<{ error: string; fix: string }>;
}) {
  return (
    <ul className="space-y-3">
      {items.map((item, i) => (
        <li key={i} className="overflow-hidden rounded-xl border border-amber-500/30 bg-amber-500/[0.04]">
          <div className="flex items-start gap-3 px-4 py-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <div>
              <p className="text-sm font-mono text-foreground">{item.error}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.fix}</p>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ── Code block with copy-to-clipboard ──────────────────────────────────

function CodeBlock({ value, lang }: { value: string; lang: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — silently no-op */
    }
  };
  return (
    <div className="relative rounded-lg border border-border bg-[hsl(var(--background))]">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        <span>{lang}</span>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? "Copied" : "Copy to clipboard"}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-emerald-500" /> Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" /> Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto px-3 py-2 text-[11px] leading-relaxed text-foreground">
        <code className="font-mono">{value}</code>
      </pre>
    </div>
  );
}
