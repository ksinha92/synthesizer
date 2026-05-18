"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ListChecks,
  Loader2,
  ShieldAlert,
} from "lucide-react";

import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { RecommendedGeneratorsModal } from "@/components/privacy-hub/recommended-generators-modal";
import { cn } from "@/lib/utils";

interface Recommendation {
  pii_type: string;
  label: string;
  unprotected_columns: number;
  recommended_generator: string;
}

interface TableBreakdownRow {
  schema_name: string;
  table_name: string;
  total_columns: number;
  sensitive_columns: number;
  protected_columns: number;
  privacy_rating: number;
}

interface PrivacyHubData {
  sensitive_count: number;
  protected_count: number;
  unprotected_count: number;
  recommendations: Recommendation[];
  tables?: TableBreakdownRow[];
}

interface PrivacyHubProps {
  projectId: string;
}

export function PrivacyHub({ projectId }: PrivacyHubProps) {
  const [data, setData] = useState<PrivacyHubData | null>(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState<string | null>(null);
  const [bulk, setBulk] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);

  const fetchHub = async () => {
    setLoading(true);
    try {
      const d = await api.get<PrivacyHubData>(`/api/v1/projects/${projectId}/privacy-hub`);
      setData(d);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHub();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const applyTypes = async (piiTypes: string[]) => {
    if (piiTypes.length === 0) return;
    try {
      const res = await api.post<{ rules_created: number; policy_id: string }>(
        `/api/v1/projects/${projectId}/privacy-hub/apply-all`,
        { pii_types: piiTypes }
      );
      if (res.rules_created === 0) {
        toast.info("No new rules needed — these columns are already protected.");
      } else {
        toast.success(`Created ${res.rules_created} masking rule${res.rules_created === 1 ? "" : "s"}.`);
      }
      await fetchHub();
    } catch {
      toast.error("Apply failed.");
    }
  };

  const handleApplyOne = async (pii: string) => {
    setApplying(pii);
    await applyTypes([pii]);
    setApplying(null);
  };

  const handleApplyAll = async () => {
    if (!data) return;
    setBulk(true);
    await applyTypes(data.recommendations.map((r) => r.pii_type));
    setBulk(false);
  };

  if (loading) {
    return <PrivacyHubSkeleton />;
  }
  if (!data) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
        Privacy Hub unavailable — run discovery on a connection to populate.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Counters */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Counter
          label="Sensitive columns"
          value={data.sensitive_count}
          icon={ShieldAlert}
          accent="brand"
        />
        <Counter
          label="Protected"
          value={data.protected_count}
          icon={CheckCircle2}
          accent="success"
        />
        <Counter
          label="Unprotected"
          value={data.unprotected_count}
          icon={AlertTriangle}
          accent={data.unprotected_count > 0 ? "warning" : "muted"}
        />
      </div>

      {/* Risk bar — protection coverage at a glance (Tonic 11.29.29). */}
      <RiskBar
        protected={data.protected_count}
        unprotected={data.unprotected_count}
        total={data.sensitive_count}
      />

      {/* Database tables breakdown — Tonic 11.29.48 / 11.30.21. Per-table
          PII-vs-protected counts with a single-line privacy rating bar. */}
      {data.tables && data.tables.length > 0 && (
        <PrivacyHubTablesTable rows={data.tables} />
      )}

      <RecommendedGeneratorsModal
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        recommendations={data.recommendations}
        onApply={applyTypes}
      />

      {/* Recommended generators */}
      <div className="rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Recommended generators</h3>
            <p className="text-xs text-muted-foreground">
              {data.recommendations.length === 0
                ? "Nothing left to protect — zero unprotected sensitive columns."
                : `${data.unprotected_count} unprotected column${
                    data.unprotected_count === 1 ? "" : "s"
                  } across ${data.recommendations.length} PII type${
                    data.recommendations.length === 1 ? "" : "s"
                  }.`}
            </p>
          </div>
          {data.recommendations.length > 0 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setReviewOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
              >
                <ListChecks className="h-3.5 w-3.5" />
                Review all
              </button>
              <button
                onClick={handleApplyAll}
                disabled={bulk}
                className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90 disabled:opacity-50"
              >
                {bulk ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                Apply all
              </button>
            </div>
          )}
        </div>
        {data.recommendations.length > 0 && (
          <ul className="divide-y divide-border">
            {data.recommendations.map((r) => (
              <li key={r.pii_type} className="flex items-center gap-3 px-5 py-3">
                <span className="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-[hsl(var(--dw-pill-warning)/0.15)] px-2 text-xs font-semibold text-[hsl(var(--dw-pill-warning))]">
                  {r.unprotected_columns}
                </span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">{r.label}</p>
                  <p className="text-xs text-muted-foreground">
                    Suggested generator:{" "}
                    <code className="font-mono text-[11px] text-foreground">
                      {r.recommended_generator}
                    </code>
                  </p>
                </div>
                <button
                  onClick={() => handleApplyOne(r.pii_type)}
                  disabled={applying === r.pii_type}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50"
                >
                  {applying === r.pii_type ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <>
                      Apply
                      <ChevronRight className="h-3 w-3" />
                    </>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Counter card ───────────────────────────────────────────────────────────
function Counter({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  accent: "brand" | "success" | "warning" | "muted";
}) {
  const accentClass = {
    brand: "text-[hsl(var(--dw-brand))]",
    success: "text-[hsl(var(--dw-pill-success))]",
    warning: "text-[hsl(var(--dw-pill-warning))]",
    muted: "text-muted-foreground",
  }[accent];

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", accentClass)} />
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      </div>
      <p className={cn("mt-2 text-3xl font-semibold tabular-nums", accentClass)}>{value}</p>
    </div>
  );
}

// ── Risk bar ───────────────────────────────────────────────────────────────
/**
 * Inline horizontal protection-coverage bar. Mirrors Tonic Privacy Hub's
 * at-a-glance protected/unprotected ratio (screenshot 11.29.29). Green
 * segment = protected, red = unprotected; the percentages are surfaced
 * to screen readers via aria-label.
 */
function RiskBar({
  protected: protectedCount,
  unprotected,
  total,
}: {
  protected: number;
  unprotected: number;
  total: number;
}) {
  if (total <= 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-xs text-muted-foreground">
        No sensitive columns detected yet.
      </div>
    );
  }

  const pctProtected = Math.round((protectedCount / total) * 100);
  const pctUnprotected = 100 - pctProtected;

  return (
    <div
      className="rounded-lg border border-border bg-card p-4"
      role="img"
      aria-label={`Protection coverage: ${pctProtected}% protected, ${pctUnprotected}% unprotected`}
    >
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-foreground">Protection coverage</span>
        <span
          className={cn(
            "font-mono tabular-nums",
            pctProtected === 100 ? "text-[hsl(var(--dw-pill-success))]" : "text-muted-foreground"
          )}
        >
          {pctProtected}%
        </span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
        {protectedCount > 0 && (
          <div
            className="float-left h-full bg-[hsl(var(--dw-pill-success))]"
            style={{ width: `${pctProtected}%` }}
          />
        )}
        {unprotected > 0 && (
          <div
            className="float-left h-full bg-[hsl(var(--dw-pill-warning))]"
            style={{ width: `${pctUnprotected}%` }}
          />
        )}
      </div>
      <div className="mt-2 flex items-center gap-4 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-[hsl(var(--dw-pill-success))]" />
          {protectedCount} protected
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-[hsl(var(--dw-pill-warning))]" />
          {unprotected} unprotected
        </span>
      </div>
    </div>
  );
}

// ── Per-table breakdown ────────────────────────────────────────────────────
function PrivacyHubTablesTable({ rows }: { rows: TableBreakdownRow[] }) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <header className="flex items-center justify-between border-b border-border px-5 py-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Database tables</h3>
          <p className="text-xs text-muted-foreground">
            Per-table breakdown of PII columns and current protection coverage.
          </p>
        </div>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {rows.length} table{rows.length === 1 ? "" : "s"}
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-muted/40 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Table</th>
              <th className="px-4 py-2 text-right font-medium"># PII</th>
              <th className="px-4 py-2 text-right font-medium">Protected</th>
              <th className="px-4 py-2 text-right font-medium">Unprotected</th>
              <th className="px-4 py-2 text-left font-medium">Privacy rating</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => {
              const unprotected = r.sensitive_columns - r.protected_columns;
              return (
                <tr key={`${r.schema_name}.${r.table_name}`} className="hover:bg-muted/20">
                  <td className="px-4 py-2">
                    <p className="font-medium text-foreground">
                      <span className="text-muted-foreground">{r.schema_name}.</span>
                      {r.table_name}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {r.total_columns} column{r.total_columns === 1 ? "" : "s"}
                    </p>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {r.sensitive_columns}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[hsl(var(--dw-pill-success))]">
                    {r.protected_columns}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-2 text-right tabular-nums",
                      unprotected > 0
                        ? "text-[hsl(var(--dw-pill-warning))]"
                        : "text-muted-foreground"
                    )}
                  >
                    {unprotected}
                  </td>
                  <td className="px-4 py-2">
                    <InlineRiskBar
                      rating={r.privacy_rating}
                      noPii={r.sensitive_columns === 0}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InlineRiskBar({ rating, noPii }: { rating: number; noPii: boolean }) {
  if (noPii) {
    return (
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
        No PII
      </span>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full",
            rating === 100
              ? "bg-[hsl(var(--dw-pill-success))]"
              : rating >= 50
                ? "bg-[hsl(var(--dw-brand))]"
                : "bg-[hsl(var(--dw-pill-warning))]"
          )}
          style={{ width: `${rating}%` }}
        />
      </div>
      <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
        {rating}%
      </span>
    </div>
  );
}

// ── Loading skeleton ───────────────────────────────────────────────────────
function PrivacyHubSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-24 rounded-lg border border-border bg-muted/40" />
        ))}
      </div>
      <div className="h-40 rounded-lg border border-border bg-muted/40" />
    </div>
  );
}
