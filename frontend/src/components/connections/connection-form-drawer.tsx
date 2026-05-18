"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronDown, ChevronUp, Loader2, X, Zap } from "lucide-react";

import { api } from "@/hooks/use-api";

import { useConnectionStore } from "@/stores/connection-store";
import { FormField } from "@/components/common/form-field";
import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { ConnectorTileGrid, defaultPortFor } from "@/components/connections/connector-tile-grid";
import {
  ConnectionFieldset,
  buildConnectionPayload,
  connectionFieldsetSchema,
  parseConnectionPayload,
  type ConnectionFieldsetValues,
} from "@/components/connections/connection-fieldset";

const DEFAULT_CONNECTION_VALUES: ConnectionFieldsetValues = {
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
};
import { cn } from "@/lib/utils";

interface EditConnection {
  id: string;
  name: string;
  connector_type: string;
  host: string;
  port: number;
  database_name: string;
  username?: string;
  /** Backend-redacted ``extra_params`` (secret keys come back as ``""``).
   * Drives full form hydration via {@link parseConnectionPayload}, which
   * prevents enterprise-auth fields from being silently wiped on edit. */
  safe_extras?: Record<string, unknown>;
}

interface ConnectionFormDrawerProps {
  open: boolean;
  onClose: () => void;
  projectId: string;
  editConnection?: EditConnection | null;
}

export function ConnectionFormDrawer({ open, onClose, projectId, editConnection }: ConnectionFormDrawerProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean } | null>(null);

  const { createConnection, updateConnection } = useConnectionStore();

  const isEditing = !!editConnection;

  const { control, handleSubmit, reset, watch, setValue } = useForm<ConnectionFieldsetValues>({
    resolver: zodResolver(connectionFieldsetSchema),
    defaultValues: editConnection
      ? parseConnectionPayload(DEFAULT_CONNECTION_VALUES, editConnection)
      : { ...DEFAULT_CONNECTION_VALUES },
  });

  // Defensive re-hydration: even when the list passes safe_extras, fetch
  // the canonical record from GET /connections/{id} on open. Two reasons:
  // (1) the list endpoint may grow a slim variant that drops extras, and
  // (2) the user may have edited the connection in another tab between
  // list-fetch and edit-click. Without this fetch a stale list lets the
  // edit-save wipe newer config.
  useEffect(() => {
    if (!open || !isEditing || !editConnection) return;
    let cancelled = false;
    (async () => {
      try {
        const fresh = await api.get<{
          name: string;
          connector_type: string;
          host: string;
          port: number;
          database_name: string;
          username: string;
          safe_extras: Record<string, unknown>;
        }>(`/api/v1/projects/${projectId}/connections/${editConnection.id}`);
        if (cancelled) return;
        reset(parseConnectionPayload(DEFAULT_CONNECTION_VALUES, fresh));
      } catch {
        // Fall back to whatever the list supplied — better than a blank form.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, isEditing, editConnection, projectId, reset]);

  if (!open) return null;

  const connectorType = watch("connectorType");

  const handleSave = handleSubmit(async (data) => {
    setSaving(true);
    const payload = buildConnectionPayload(data);
    const result = isEditing
      ? await updateConnection(projectId, editConnection!.id, payload)
      : await createConnection(projectId, payload);
    setSaving(false);
    if (result) {
      resetAndClose();
    }
  });

  const handleTest = handleSubmit(async (data) => {
    setTesting(true);
    setTestResult(null);
    // The backend has no dry-run test endpoint, so test = create-then-test
    // — same behaviour the standalone drawer has had since Phase 5.
    const conn = await createConnection(projectId, buildConnectionPayload(data));
    if (conn) {
      try {
        const { api } = await import("@/hooks/use-api");
        const res = await api.post<{ success: boolean }>(
          `/api/v1/projects/${projectId}/connections/${conn.id}/test`
        );
        setTestResult(res);
      } catch {
        setTestResult({ success: false });
      }
    }
    setTesting(false);
  });

  const resetAndClose = () => {
    reset();
    setTestResult(null);
    setShowAdvanced(false);
    onClose();
  };

  const handleTypeChange = (type: string) => {
    setValue("connectorType", type);
    const def = defaultPortFor(type);
    if (def !== undefined) setValue("port", def);
    setTestResult(null);
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50" onClick={resetAndClose} />
      <AccessibleDialog
        open={open}
        onClose={resetAndClose}
        titleId="connection-drawer-title"
        className="fixed inset-y-0 right-0 z-50 w-full max-w-full sm:max-w-[560px] border-l border-border bg-card shadow-xl overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 id="connection-drawer-title" className="text-lg font-semibold text-foreground">
            {isEditing ? "Edit Connection" : "Add Connection"}
          </h2>
          <button onClick={resetAndClose} className="text-muted-foreground hover:text-foreground" aria-label="Close drawer">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-5">
          <ConnectorTileGrid
            selected={connectorType}
            onSelect={handleTypeChange}
            step="Step 1 · Source"
          />

          <ConnectionFieldset
            control={control}
            connectorType={connectorType}
            advanced={
              <>
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
                >
                  {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  Advanced Options
                </button>
                {showAdvanced && (
                  <FormField
                    control={control}
                    name="extraParams"
                    label="Extra Parameters (JSON)"
                    type="textarea"
                    rows={3}
                  />
                )}
              </>
            }
          />

          {testResult && (
            <div
              className={cn(
                "rounded-lg px-4 py-2.5 text-sm",
                testResult.success
                  ? "bg-green-500/10 text-green-700 dark:text-green-400"
                  : "bg-red-500/10 text-red-700 dark:text-red-400"
              )}
            >
              {testResult.success ? "Connection successful!" : "Connection failed. Check your settings."}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-6 py-4 flex items-center gap-2">
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            {testing ? "Testing..." : "Test Connection"}
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={resetAndClose}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "Saving..." : isEditing ? "Update" : "Save"}
          </button>
        </div>
      </AccessibleDialog>
    </>
  );
}
