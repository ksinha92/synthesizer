"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { z } from "zod";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  FileSearch,
  Loader2,
  Lock,
  Play,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { useProjectStore } from "@/stores/project-store";
import { FormField } from "@/components/common/form-field";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { ConnectorTileGrid, defaultPortFor } from "@/components/connections/connector-tile-grid";
import {
  ConnectionFieldset,
  buildConnectionPayload,
  connectionFieldsetSchema,
  type ConnectionFieldsetValues,
} from "@/components/connections/connection-fieldset";
import { cn } from "@/lib/utils";

interface CreateProjectWizardProps {
  open: boolean;
  onClose: () => void;
}

type WizardStep = "details" | "connector" | "connection" | "discovery" | "confirm";

const STEP_ORDER: WizardStep[] = ["details", "connector", "connection", "discovery", "confirm"];
const STEP_TITLE: Record<WizardStep, string> = {
  details: "Project details",
  connector: "Pick a source",
  connection: "Connect your data",
  discovery: "Run discovery?",
  confirm: "Confirm and create",
};

const detailsSchema = z.object({
  name: z.string().trim().min(1, "Project name is required").max(100, "Name must be 100 characters or less"),
  description: z.string().max(500, "Description must be 500 characters or less").optional().default(""),
});
type DetailsValues = z.infer<typeof detailsSchema>;

/**
 * Tonic-style New Project Wizard (screenshots 11.21.49 → 11.23.21).
 *
 * Five steps owned by a single state machine; submits atomically via the
 * extended POST /api/v1/projects endpoint that accepts
 * ``initial_connection`` and ``run_discovery``. The whole tree (project +
 * connection + optional discovery job row) commits or nothing does — see
 * backend/app/api/v1/projects.py::create_project.
 *
 * Reuses three existing primitives so behaviour stays identical to the
 * standalone Add Connection drawer: ConnectorTileGrid (category tiles +
 * "Coming Soon"), ConnectionFieldset (the body fields), and
 * buildConnectionPayload (Snowflake host synthesis + extras merge).
 */
export function CreateProjectWizard({ open, onClose }: CreateProjectWizardProps) {
  const router = useRouter();
  const createProjectAtomic = useProjectStore((s) => s.createProjectAtomic);

  const [step, setStep] = useState<WizardStep>("details");
  const [skipConnection, setSkipConnection] = useState(false);
  const [runDiscovery, setRunDiscovery] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const detailsForm = useForm<DetailsValues>({
    resolver: zodResolver(detailsSchema),
    defaultValues: { name: "", description: "" },
  });

  const connectionForm = useForm<ConnectionFieldsetValues>({
    resolver: zodResolver(connectionFieldsetSchema),
    defaultValues: {
      connectorType: "postgresql",
      name: "",
      host: "",
      port: 5432,
      databaseName: "",
      username: "",
      password: "",
      account: "",
      warehouse: "",
      role: "",
      snowflakeAuthMode: "password",
      snowflakePrivateKeyPem: "",
      snowflakePrivateKeyPassphrase: "",
      snowflakeOauthToken: "",
      snowflakeOauthRefreshToken: "",
      snowflakeOauthClientId: "",
      snowflakeOauthClientSecret: "",
      snowflakeOauthTokenEndpoint: "",
      snowflakeOktaUrl: "",
      snowflakePrivateKeyPemHasStored: false,
      snowflakeOauthTokenHasStored: false,
      snowflakeOauthRefreshTokenHasStored: false,
      snowflakeOauthClientSecretHasStored: false,
      oracleAzureAdTokenHasStored: false,
      sqlserverAzureAdTokenHasStored: false,
      databricksAccessTokenHasStored: false,
      databricksClientSecretHasStored: false,
      oracleServiceName: "",
      oracleWalletPath: "",
      oraclePdb: "",
      oracleAuthMode: "password",
      oracleAzureAdToken: "",
      sqlserverInstance: "",
      sqlserverAuthMode: "password",
      sqlserverAzureAdToken: "",
      sqlserverPyodbcDriver: "ODBC Driver 18 for SQL Server",
      redshiftAuthMode: "password",
      redshiftIamClusterId: "",
      redshiftIamDbUser: "",
      redshiftAwsRegion: "us-east-1",
      databricksHttpPath: "",
      databricksAuthMode: "token",
      databricksAccessToken: "",
      databricksClientId: "",
      databricksClientSecret: "",
      mongoAuthMechanism: "",
      mongoAuthSource: "",
      mongoReplicaSet: "",
      mongoMaxSampleSize: 100,
      mongoMaxDocDepth: 2,
      mongoGssapiServiceName: "",
      mongoAwsSessionToken: "",
      db2Security: "SERVER",
      db2Platform: "luw",
      db2LdapPlugin: "IBMLDAPauthserver",
      db2KrbPlugin: "IBMkrb5",
      snowflakeQueryTag: "",
      snowflakeStatementTimeoutSeconds: 300,
      mysqlAuthPlugin: "",
      sslEnabled: false,
      sslTrustServerCert: false,
      sslCaCertPath: "",
      sslClientCertPath: "",
      sslClientKeyPath: "",
      kerberosEnabled: false,
      kerberosPrincipal: "",
      localSchemas: "",
      blockOnSchemaChange: false,
      extraParams: "{}",
    },
  });

  if (!open) return null;

  const stepIdx = STEP_ORDER.indexOf(step);
  const isFirst = stepIdx === 0;
  const isLast = stepIdx === STEP_ORDER.length - 1;
  const connectorType = connectionForm.watch("connectorType");

  const handleClose = () => {
    detailsForm.reset();
    connectionForm.reset();
    setStep("details");
    setSkipConnection(false);
    setRunDiscovery(false);
    setShowAdvanced(false);
    setServerError(null);
    onClose();
  };

  // Advancing skips the connection/discovery steps when the user opted to
  // create a bare project, so the wizard always lands on Confirm last.
  const nextStep = (): WizardStep => {
    if (step === "details") return skipConnection ? "confirm" : "connector";
    if (step === "connector") return "connection";
    if (step === "connection") return "discovery";
    if (step === "discovery") return "confirm";
    return "confirm";
  };

  const prevStep = (): WizardStep => {
    if (step === "confirm") return skipConnection ? "details" : "discovery";
    if (step === "discovery") return "connection";
    if (step === "connection") return "connector";
    if (step === "connector") return "details";
    return "details";
  };

  // Per-step validation. We can't just call form.handleSubmit on Next
  // because the connection form isn't fully filled until the user finishes
  // step 3. trigger() runs only the fields visible on the current step.
  const handleNext = async () => {
    setServerError(null);
    if (step === "details") {
      const ok = await detailsForm.trigger();
      if (!ok) return;
    }
    if (step === "connection") {
      const ok = await connectionForm.trigger();
      if (!ok) return;
    }
    setStep(nextStep());
  };

  const handleConnectorChange = (type: string) => {
    connectionForm.setValue("connectorType", type);
    const def = defaultPortFor(type);
    if (def !== undefined) connectionForm.setValue("port", def);
  };

  const handleCreate = async () => {
    setSubmitting(true);
    setServerError(null);

    const details = detailsForm.getValues();
    const includeConnection = !skipConnection;
    const connData = includeConnection ? connectionForm.getValues() : null;
    const connectionPayload = connData ? buildConnectionPayload(connData) : null;

    const project = await createProjectAtomic({
      name: details.name,
      description: details.description || undefined,
      initial_connection: connectionPayload,
      run_discovery: includeConnection && runDiscovery,
    });

    setSubmitting(false);

    if (!project) {
      // Toast surfaced inside the store; leave the user on Confirm so they
      // can retry without re-typing.
      setServerError("Could not create project — see the toast for details.");
      return;
    }

    handleClose();

    // Routing decision: if discovery was queued, drop the user on Jobs so
    // they see the running job; if they only added a connection, drop on
    // Connections to confirm; otherwise land on the project Privacy Hub.
    if (project.discovery_job_id) {
      router.push(`/projects/${project.id}/jobs`);
    } else if (project.connection_id) {
      router.push(`/projects/${project.id}/connections`);
    } else {
      router.push(`/projects/${project.id}`);
    }
  };

  // Next must stay clickable even with an empty name — clicking it is what
  // triggers the zod validation that surfaces "Project name is required".
  // Pre-disabling the button hides that error and confuses screen readers.
  const isNextDisabled = submitting;

  return (
    <>
      {/* z-[60] sits above the floating AI Assistant bubble + OnboardingWizard
          (both z-40/50) so the wizard's footer buttons stay hittable. The
          original create-project drawer had the same overlap and Playwright
          flaked on it in CI. */}
      <div className="fixed inset-0 z-[55] bg-black/40" onClick={handleClose} aria-hidden="true" />
      <AccessibleDialog
        open={open}
        onClose={handleClose}
        titleId="create-project-title"
        className="fixed inset-y-0 right-0 z-[60] flex w-full max-w-3xl flex-col border-l border-border bg-card shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-border px-6 py-4">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Sparkles className="h-3 w-3 text-[hsl(var(--dw-brand))]" />
              New project
            </div>
            <h2 id="create-project-title" className="mt-1 text-lg font-semibold text-foreground">
              {STEP_TITLE[step]}
            </h2>
            <StepDots current={stepIdx} total={STEP_ORDER.length} />
          </div>
          <button
            onClick={handleClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close wizard"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex flex-1 min-h-0 divide-x divide-border">
          <section className="flex-1 overflow-y-auto px-6 py-5">
            {step === "details" && (
              <StepDetails
                form={detailsForm}
                skipConnection={skipConnection}
                onToggleSkip={setSkipConnection}
              />
            )}
            {step === "connector" && (
              <ConnectorTileGrid
                selected={connectorType}
                onSelect={handleConnectorChange}
                step={`Step 2 of ${STEP_ORDER.length}`}
                title="Pick your data source"
              />
            )}
            {step === "connection" && (
              <ConnectionFieldset
                control={connectionForm.control}
                connectorType={connectorType}
                advanced={
                  <>
                    <button
                      type="button"
                      onClick={() => setShowAdvanced((v) => !v)}
                      className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
                    >
                      {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      Advanced Options
                    </button>
                    {showAdvanced && (
                      <FormField
                        control={connectionForm.control}
                        name="extraParams"
                        label="Extra Parameters (JSON)"
                        type="textarea"
                        rows={3}
                      />
                    )}
                  </>
                }
              />
            )}
            {step === "discovery" && (
              <StepDiscovery enabled={runDiscovery} onToggle={setRunDiscovery} />
            )}
            {step === "confirm" && (
              <StepConfirm
                details={detailsForm.getValues()}
                connection={skipConnection ? null : connectionForm.getValues()}
                runDiscovery={runDiscovery}
                serverError={serverError}
              />
            )}
          </section>

          <PromoRail />
        </div>

        <footer className="flex items-center justify-between gap-2 border-t border-border px-6 py-3">
          <button
            type="button"
            onClick={() => setStep(prevStep())}
            disabled={isFirst || submitting}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Cancel
            </button>
            {isLast ? (
              <button
                type="button"
                onClick={handleCreate}
                disabled={submitting}
                className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Create Project
              </button>
            ) : (
              <button
                type="button"
                onClick={handleNext}
                disabled={isNextDisabled}
                className="inline-flex items-center gap-1.5 rounded-md bg-gradient-to-r from-[hsl(var(--dw-cta-from))] to-[hsl(var(--dw-cta-to))] px-3 py-1.5 text-xs font-semibold text-white shadow hover:opacity-90 disabled:opacity-50"
              >
                Next
                <ArrowRight className="h-3 w-3" />
              </button>
            )}
          </div>
        </footer>
      </AccessibleDialog>
    </>
  );
}

// ── Step indicator ─────────────────────────────────────────────────────────
function StepDots({ current, total }: { current: number; total: number }) {
  return (
    <ol aria-label="Wizard progress" className="mt-2 flex items-center gap-1.5">
      {Array.from({ length: total }, (_, i) => (
        <li
          key={i}
          aria-current={i === current ? "step" : undefined}
          className={cn(
            "h-1.5 w-6 rounded-full transition-colors",
            i < current
              ? "bg-[hsl(var(--dw-pill-success))]"
              : i === current
                ? "bg-[hsl(var(--dw-brand))]"
                : "bg-muted"
          )}
        />
      ))}
    </ol>
  );
}

// ── Step 1: Details ────────────────────────────────────────────────────────
function StepDetails({
  form,
  skipConnection,
  onToggleSkip,
}: {
  form: ReturnType<typeof useForm<DetailsValues>>;
  skipConnection: boolean;
  onToggleSkip: (v: boolean) => void;
}) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Projects organise your connections, discovery, generators and jobs.
      </p>
      <FormField control={form.control} name="name" label="Name" required placeholder="My TDM Project" />
      <FormField
        control={form.control}
        name="description"
        label="Description"
        type="textarea"
        placeholder="Optional description..."
        rows={3}
      />
      <label className="flex items-start gap-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-xs">
        <input
          type="checkbox"
          checked={skipConnection}
          onChange={(e) => onToggleSkip(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          <span className="font-medium text-foreground">Skip connection setup</span>
          <span className="block text-muted-foreground">
            Create an empty project now and add a connection later from the workspace.
          </span>
        </span>
      </label>
    </div>
  );
}

// ── Step 4: Discovery ──────────────────────────────────────────────────────
function StepDiscovery({ enabled, onToggle }: { enabled: boolean; onToggle: (v: boolean) => void }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Discovery introspects your schema and detects PII columns. It runs in the background — you can always
        trigger it manually later from the Discovery tab.
      </p>
      <label className="flex items-start gap-3 rounded-md border border-border bg-muted/20 p-4">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          className="mt-1 h-4 w-4"
        />
        <span>
          <span className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <FileSearch className="h-3.5 w-3.5 text-[hsl(var(--dw-brand))]" />
            Run discovery as soon as the project is created
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            We'll queue a discovery job against the connection you just configured and route you to the
            Jobs tab so you can watch the progress.
          </span>
        </span>
      </label>
    </div>
  );
}

// ── Step 5: Confirm ────────────────────────────────────────────────────────
function StepConfirm({
  details,
  connection,
  runDiscovery,
  serverError,
}: {
  details: DetailsValues;
  connection: ConnectionFieldsetValues | null;
  runDiscovery: boolean;
  serverError: string | null;
}) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Review the run. Nothing is written until you press <span className="font-medium text-foreground">Create Project</span>.
      </p>

      <SummaryGroup title="Project">
        <SummaryRow label="Name" value={details.name || "—"} />
        {details.description && <SummaryRow label="Description" value={details.description} />}
      </SummaryGroup>

      <SummaryGroup title="Connection">
        {connection ? (
          <>
            <SummaryRow label="Type" value={connection.connectorType} />
            <SummaryRow label="Name" value={connection.name} />
            <SummaryRow
              label={connection.connectorType === "snowflake" ? "Account" : "Host"}
              value={connection.connectorType === "snowflake" ? connection.account : connection.host}
            />
            <SummaryRow label="Database" value={connection.databaseName} />
            <SummaryRow label="Port" value={String(connection.port)} />
            <SummaryRow label="Username" value={connection.username} />
          </>
        ) : (
          <SummaryRow label="Connection" value="Skipped — add one later" />
        )}
      </SummaryGroup>

      {connection && (
        <SummaryGroup title="Discovery">
          <SummaryRow label="Run on create" value={runDiscovery ? "Yes" : "No"} />
        </SummaryGroup>
      )}

      {serverError && (
        <p className="text-sm text-destructive" role="alert">
          {serverError}
        </p>
      )}
    </div>
  );
}

function SummaryGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
        {title}
      </h3>
      <dl className="divide-y divide-border rounded-md border border-border">{children}</dl>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-3 gap-3 px-3 py-2 text-xs">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="col-span-2 font-medium text-foreground break-all">{value}</dd>
    </div>
  );
}

// ── Right rail — 4 promo cards mirroring Tonic 11.22.25 ────────────────────
function PromoRail() {
  return (
    <aside className="w-72 shrink-0 overflow-y-auto bg-muted/10 px-5 py-5 space-y-4">
      <PromoCard
        icon={Lock}
        title="Data too sensitive to leave production?"
        body="Connect read-only. Generators replace values on output — your source is never written to."
      />
      <PromoCard
        icon={ShieldCheck}
        title="HIPAA / GDPR / CCPA compliant"
        body="Every run produces an audit trail and a downloadable compliance report. Settings live on the Compliance tab."
      />
      <PromoCard
        icon={Sparkles}
        title="Use a sample dataset"
        body="No connection yet? Spin up a synthetic dataset so the team can prototype against realistic shapes."
      />
      <PromoCard
        icon={Copy}
        title="Create a child workspace"
        body="Clone an existing project's connections, masking policies, and webhooks from the Projects list to bootstrap a new one."
      />
    </aside>
  );
}

function PromoCard({
  icon: Icon,
  title,
  body,
  disabled,
}: {
  icon: React.ElementType;
  title: string;
  body: string;
  disabled?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-3",
        disabled && "opacity-60"
      )}
      aria-disabled={disabled || undefined}
    >
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-[hsl(var(--dw-brand))]" />
        <p className="text-xs font-medium text-foreground">{title}</p>
        {disabled && (
          <span className="rounded-full bg-muted px-1.5 text-[8px] uppercase tracking-wide text-muted-foreground">
            Soon
          </span>
        )}
      </div>
      <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">{body}</p>
    </div>
  );
}

// Sentinel — referenced by lint when icons get tree-shaken out.
const _used = { Check };
void _used;
