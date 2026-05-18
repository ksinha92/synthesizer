"use client";

import { Controller, type Control } from "react-hook-form";
import { z } from "zod";

import { FormField } from "@/components/common/form-field";

/**
 * Shared schema for any form collecting a connection — the standalone Add
 * Connection drawer and the New Project Wizard's connection step both build
 * a useForm() against this exact shape so the rendered fields, validation
 * errors, and `buildConnectionPayload` output stay identical between the
 * two surfaces.
 *
 * The schema covers all 9 connector types. Per-connector required-field
 * logic lives in the superRefine block at the bottom so the type is still
 * fully inferred — every field is part of the same form state regardless
 * of which connector is selected.
 */
export const connectionFieldsetSchema = z
  .object({
    connectorType: z.string().default("postgresql"),
    name: z.string().trim().min(1, "Name is required"),
    host: z.string().trim().default(""),
    port: z.coerce
      .number()
      .int()
      .min(1, "Port must be 1–65535")
      .max(65535, "Port must be 1–65535"),
    databaseName: z.string().trim().min(1, "Database is required"),
    username: z.string().trim().default(""),
    password: z.string().default(""),

    // Snowflake-specific
    account: z.string().trim().default(""),
    warehouse: z.string().trim().default(""),
    role: z.string().trim().default(""),
    snowflakeAuthMode: z.enum(["password", "key_pair", "oauth", "okta", "externalbrowser"]).default("password"),
    snowflakePrivateKeyPem: z.string().default(""),
    snowflakePrivateKeyPassphrase: z.string().default(""),
    snowflakeOauthToken: z.string().default(""),
    snowflakeOauthRefreshToken: z.string().default(""),
    snowflakeOauthClientId: z.string().default(""),
    snowflakeOauthClientSecret: z.string().default(""),
    snowflakeOauthTokenEndpoint: z.string().default(""),
    snowflakeOktaUrl: z.string().default(""),
    // "Has stored" flags — set by parseConnectionPayload when the safe_extras
    // payload from the backend includes a redacted secret key (value="").
    // Their presence tells validation "the secret is already saved server-
    // side, blank input means 'keep current'". Not sent to the backend.
    snowflakePrivateKeyPemHasStored: z.boolean().default(false),
    snowflakeOauthTokenHasStored: z.boolean().default(false),
    snowflakeOauthRefreshTokenHasStored: z.boolean().default(false),
    snowflakeOauthClientSecretHasStored: z.boolean().default(false),

    // Oracle-specific
    oracleServiceName: z.string().trim().default(""),
    oracleWalletPath: z.string().trim().default(""),
    oraclePdb: z.string().trim().default(""),
    oracleAuthMode: z.enum(["password", "kerberos", "azure_ad"]).default("password"),
    oracleAzureAdToken: z.string().default(""),
    oracleAzureAdTokenHasStored: z.boolean().default(false),

    // SQL Server-specific
    sqlserverInstance: z.string().trim().default(""),
    sqlserverAuthMode: z.enum(["password", "azure_ad", "windows"]).default("password"),
    sqlserverAzureAdToken: z.string().default(""),
    sqlserverAzureAdTokenHasStored: z.boolean().default(false),
    sqlserverPyodbcDriver: z.string().default("ODBC Driver 18 for SQL Server"),

    // Redshift-specific
    redshiftAuthMode: z.enum(["password", "iam"]).default("password"),
    redshiftIamClusterId: z.string().trim().default(""),
    redshiftIamDbUser: z.string().trim().default(""),
    redshiftAwsRegion: z.string().trim().default("us-east-1"),

    // Databricks-specific
    databricksHttpPath: z.string().trim().default(""),
    databricksAuthMode: z.enum(["token", "oauth_m2m"]).default("token"),
    databricksAccessToken: z.string().default(""),
    databricksAccessTokenHasStored: z.boolean().default(false),
    databricksClientId: z.string().trim().default(""),
    databricksClientSecret: z.string().default(""),
    databricksClientSecretHasStored: z.boolean().default(false),

    // MongoDB-specific
    mongoAuthMechanism: z.enum([
      "",
      "SCRAM-SHA-256",
      "SCRAM-SHA-1",
      "MONGODB-X509",
      "GSSAPI",
      "MONGODB-AWS",
    ]).default(""),
    mongoAuthSource: z.string().trim().default(""),
    mongoReplicaSet: z.string().trim().default(""),
    mongoMaxSampleSize: z.coerce.number().int().min(1).max(10000).default(100),
    mongoMaxDocDepth: z.coerce.number().int().min(1).max(10).default(2),
    mongoGssapiServiceName: z.string().trim().default(""),
    mongoAwsSessionToken: z.string().default(""),

    // DB2-specific
    db2Security: z.enum(["SERVER", "SSL", "KERBEROS", "LDAP"]).default("SERVER"),
    db2Platform: z.enum(["luw", "zos"]).default("luw"),
    db2LdapPlugin: z.string().default("IBMLDAPauthserver"),
    db2KrbPlugin: z.string().default("IBMkrb5"),

    // Snowflake observability + billing
    snowflakeQueryTag: z.string().trim().default(""),
    snowflakeStatementTimeoutSeconds: z.coerce.number().int().min(1).max(86400).default(300),

    // MySQL — server-specified auth plugin override (8.0+ uses caching_sha2)
    mysqlAuthPlugin: z.string().trim().default(""),

    // SSL/security toggles common to many connectors
    sslEnabled: z.boolean().default(false),
    sslTrustServerCert: z.boolean().default(false),
    sslCaCertPath: z.string().trim().default(""),
    sslClientCertPath: z.string().trim().default(""),
    sslClientKeyPath: z.string().trim().default(""),

    // Kerberos
    kerberosEnabled: z.boolean().default(false),
    kerberosPrincipal: z.string().trim().default(""),

    // Discovery scoping + drift detection
    localSchemas: z.string().trim().default(""),
    blockOnSchemaChange: z.boolean().default(false),

    extraParams: z
      .string()
      .refine(
        (v) => {
          try {
            JSON.parse(v);
            return true;
          } catch {
            return false;
          }
        },
        { message: "Must be valid JSON" }
      )
      .default("{}"),
  })
  .superRefine((data, ctx) => {
    const ct = data.connectorType;

    // Snowflake fronts its host via the account name; all other connectors
    // require an explicit host.
    if (ct !== "snowflake" && !data.host) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Host is required", path: ["host"] });
    }

    // ── Snowflake ────────────────────────────────────────────────────────
    if (ct === "snowflake") {
      if (!data.account)
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Account is required", path: ["account"] });
      if (!data.warehouse)
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Warehouse is required", path: ["warehouse"] });

      if (data.snowflakeAuthMode === "key_pair" && !data.snowflakePrivateKeyPem && !data.snowflakePrivateKeyPemHasStored) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Private key PEM is required for key-pair auth",
          path: ["snowflakePrivateKeyPem"],
        });
      }
      if (data.snowflakeAuthMode === "oauth") {
        // OAuth accepts EITHER a static access token OR the refresh-token
        // quad. A redacted blank with HasStored=true counts as "present"
        // because the backend will preserve it on save.
        const hasStatic = !!data.snowflakeOauthToken || data.snowflakeOauthTokenHasStored;
        const hasRefreshQuad =
          (!!data.snowflakeOauthRefreshToken || data.snowflakeOauthRefreshTokenHasStored) &&
          !!data.snowflakeOauthClientId &&
          (!!data.snowflakeOauthClientSecret || data.snowflakeOauthClientSecretHasStored) &&
          !!data.snowflakeOauthTokenEndpoint;
        if (!hasStatic && !hasRefreshQuad) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message:
              "Supply either an OAuth access token OR the full refresh-token quad (refresh token + client id + client secret + token endpoint).",
            path: ["snowflakeOauthToken"],
          });
        }
      }
      if (data.snowflakeAuthMode === "okta" && !data.snowflakeOktaUrl) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Okta org URL is required (e.g. https://my-org.okta.com)",
          path: ["snowflakeOktaUrl"],
        });
      }
    }

    // ── Databricks ───────────────────────────────────────────────────────
    if (ct === "databricks") {
      if (!data.databricksHttpPath)
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "HTTP path is required",
          path: ["databricksHttpPath"],
        });
      if (data.databricksAuthMode === "token") {
        if (!data.databricksAccessToken && !data.databricksAccessTokenHasStored)
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "Personal Access Token is required",
            path: ["databricksAccessToken"],
          });
      } else if (data.databricksAuthMode === "oauth_m2m") {
        if (!data.databricksClientId)
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "Client ID is required for M2M OAuth",
            path: ["databricksClientId"],
          });
        if (!data.databricksClientSecret && !data.databricksClientSecretHasStored)
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "Client Secret is required for M2M OAuth",
            path: ["databricksClientSecret"],
          });
      }
    }

    // ── Redshift IAM ─────────────────────────────────────────────────────
    if (ct === "redshift" && data.redshiftAuthMode === "iam") {
      if (!data.redshiftIamClusterId)
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Cluster ID is required for IAM auth",
          path: ["redshiftIamClusterId"],
        });
      if (!data.redshiftIamDbUser)
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "DB user is required for IAM auth",
          path: ["redshiftIamDbUser"],
        });
    }

    // ── Oracle Azure AD ─────────────────────────────────────────────────
    if (
      ct === "oracle" &&
      data.oracleAuthMode === "azure_ad" &&
      !data.oracleAzureAdToken &&
      !data.oracleAzureAdTokenHasStored
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Azure AD access token is required",
        path: ["oracleAzureAdToken"],
      });
    }

    // ── SQL Server Azure AD ─────────────────────────────────────────────
    if (
      ct === "sqlserver" &&
      data.sqlserverAuthMode === "azure_ad" &&
      !data.sqlserverAzureAdToken &&
      !data.sqlserverAzureAdTokenHasStored
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Azure AD access token is required",
        path: ["sqlserverAzureAdToken"],
      });
    }

    // ── Username requirement ─────────────────────────────────────────────
    // A username is needed only for auth modes that actually use one.
    // Token / IAM / key-based / OAuth / Kerberos (OS ticket cache) /
    // Windows-Integrated all derive identity from elsewhere.
    // Snowflake intentionally NOT exempted — every snowflake-connector-python
    // auth mode (password, key_pair, oauth, okta, externalbrowser) requires
    // ``user=`` to be set, so the form has to collect it regardless.
    const usernameNotNeeded =
      // Token-style: Databricks PAT + M2M, never use username
      ct === "databricks" ||
      // Redshift IAM uses db_user from extras
      (ct === "redshift" && data.redshiftAuthMode === "iam") ||
      // SQL Server Azure AD uses token; Windows uses Trusted_Connection
      (ct === "sqlserver" && (data.sqlserverAuthMode === "azure_ad" || data.sqlserverAuthMode === "windows")) ||
      // Oracle Kerberos uses externalauth; Azure AD username is "Principal"
      (ct === "oracle" && data.oracleAuthMode === "kerberos") ||
      // DB2 Kerberos uses OS ticket cache; LDAP still needs username
      (ct === "db2" && data.db2Security === "KERBEROS") ||
      // Global Postgres Kerberos toggle
      data.kerberosEnabled;

    if (!usernameNotNeeded && !data.username) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Username is required",
        path: ["username"],
      });
    }
  });

export type ConnectionFieldsetValues = z.infer<typeof connectionFieldsetSchema>;

interface ConnectionFieldsetProps {
  /** Bound to a useForm() built against ``connectionFieldsetSchema``. */
  control: Control<ConnectionFieldsetValues>;
  /** Which connector tile is currently selected. Drives which auth /
   * connection fields render. */
  connectorType: string;
  /** Optional advanced area appended below the SSL/Kerberos source-settings
   * block — typically the JSON extras editor + a disclosure toggle. */
  advanced?: React.ReactNode;
}

/**
 * The fieldset rendered after a connector tile is picked. Each connector
 * gets the basic identity + database fields, then a per-connector block,
 * then the shared SSL/Kerberos/localSchemas section.
 */
export function ConnectionFieldset({ control, connectorType, advanced }: ConnectionFieldsetProps) {
  return (
    <div className="space-y-4">
      <FormField
        control={control}
        name="name"
        label="Connection Name"
        required
        placeholder="Production Replica"
      />

      <ConnectorIdentityFields control={control} connectorType={connectorType} />

      <ConnectorAuthFields control={control} connectorType={connectorType} />

      <SourceSettingsBlock control={control} connectorType={connectorType} />

      {advanced}
    </div>
  );
}

// ── Identity (host + database + per-connector overrides) ──────────────────
function ConnectorIdentityFields({
  control,
  connectorType,
}: {
  control: Control<ConnectionFieldsetValues>;
  connectorType: string;
}) {
  if (connectorType === "snowflake") {
    return (
      <>
        <FormField control={control} name="account" label="Account" required placeholder="xy12345.us-east-1" />
        <FormField control={control} name="warehouse" label="Warehouse" required placeholder="COMPUTE_WH" />
        <FormField control={control} name="role" label="Role" placeholder="SYSADMIN" />
        <div className="grid grid-cols-2 gap-3">
          <FormField control={control} name="port" label="Port" type="number" min={1} max={65535} />
          <FormField control={control} name="databaseName" label="Database" required placeholder="ANALYTICS_DB" />
        </div>
      </>
    );
  }

  return (
    <>
      <FormField control={control} name="host" label="Host" required placeholder="localhost" />
      <div className="grid grid-cols-2 gap-3">
        <FormField control={control} name="port" label="Port" type="number" min={1} max={65535} />
        <FormField
          control={control}
          name="databaseName"
          label={connectorType === "databricks" ? "Catalog" : "Database"}
          required
          placeholder={connectorType === "databricks" ? "main" : "mydb"}
        />
      </div>
      {connectorType === "oracle" && (
        <>
          <FormField control={control} name="oracleServiceName" label="Service Name" placeholder="ORCLPDB1" />
          <FormField
            control={control}
            name="oraclePdb"
            label="Pluggable Database (PDB) — optional"
            placeholder="FINPDB1"
          />
          <FormField control={control} name="oracleWalletPath" label="Oracle Wallet Path (optional)" placeholder="/etc/oracle/wallet" />
        </>
      )}
      {connectorType === "sqlserver" && (
        <FormField control={control} name="sqlserverInstance" label="Named Instance (optional)" placeholder="SQLEXPRESS" />
      )}
      {connectorType === "databricks" && (
        <FormField
          control={control}
          name="databricksHttpPath"
          label="HTTP Path"
          required
          placeholder="/sql/1.0/warehouses/abcdef1234567890"
        />
      )}
    </>
  );
}

// ── Auth (per-connector: password / key-pair / OAuth / IAM / Azure AD / token) ──
function ConnectorAuthFields({
  control,
  connectorType,
}: {
  control: Control<ConnectionFieldsetValues>;
  connectorType: string;
}) {
  if (connectorType === "snowflake") {
    return (
      <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
        <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Authentication
        </legend>
        <div className="space-y-2 pt-1">
          <Controller
            control={control}
            name="snowflakeAuthMode"
            render={({ field }) => (
              <select
                value={field.value}
                onChange={field.onChange}
                className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
              >
                <option value="password">Password</option>
                <option value="key_pair">Key-pair (recommended for production)</option>
                <option value="oauth">OAuth (token or refresh-token flow)</option>
                <option value="okta">Okta SAML SSO</option>
                <option value="externalbrowser">External browser SSO (desktop only)</option>
              </select>
            )}
          />
          <Controller
            control={control}
            name="snowflakeAuthMode"
            render={({ field }) => (
              <>
                <FormField control={control} name="username" label="Username" required placeholder="SVC_DATAWRANGLER" />
                {field.value === "password" && (
                  <FormField control={control} name="password" label="Password" type="password" />
                )}
                {field.value === "key_pair" && (
                  <>
                    <Controller
                      control={control}
                      name="snowflakePrivateKeyPem"
                      render={({ field: pemField }) => (
                        <label className="block text-xs">
                          <span className="font-medium text-foreground">Private Key (PEM)</span>
                          <textarea
                            value={pemField.value}
                            onChange={pemField.onChange}
                            rows={5}
                            placeholder="-----BEGIN PRIVATE KEY-----..."
                            className="mt-1 block w-full rounded border border-border bg-background p-2 font-mono text-[11px]"
                          />
                        </label>
                      )}
                    />
                    <FormField
                      control={control}
                      name="snowflakePrivateKeyPassphrase"
                      label="Key Passphrase (optional)"
                      type="password"
                    />
                  </>
                )}
                {field.value === "oauth" && (
                  <>
                    <Controller
                      control={control}
                      name="snowflakeOauthToken"
                      render={({ field: tokField }) => (
                        <label className="block text-xs">
                          <span className="font-medium text-foreground">OAuth access token (or leave blank if using refresh)</span>
                          <textarea
                            value={tokField.value}
                            onChange={tokField.onChange}
                            rows={3}
                            placeholder="ya29.A0AfH6..."
                            className="mt-1 block w-full rounded border border-border bg-background p-2 font-mono text-[11px]"
                          />
                        </label>
                      )}
                    />
                    <details className="text-xs">
                      <summary className="cursor-pointer text-muted-foreground">Auto-refresh (recommended for production)</summary>
                      <div className="mt-2 space-y-2 pl-2">
                        <FormField
                          control={control}
                          name="snowflakeOauthRefreshToken"
                          label="Refresh token"
                          type="password"
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <FormField control={control} name="snowflakeOauthClientId" label="Client ID" />
                          <FormField
                            control={control}
                            name="snowflakeOauthClientSecret"
                            label="Client Secret"
                            type="password"
                          />
                        </div>
                        <FormField
                          control={control}
                          name="snowflakeOauthTokenEndpoint"
                          label="Token endpoint"
                          placeholder="https://idp.example.com/oauth2/token"
                        />
                      </div>
                    </details>
                  </>
                )}
                {field.value === "okta" && (
                  <>
                    <FormField
                      control={control}
                      name="snowflakeOktaUrl"
                      label="Okta org URL"
                      required
                      placeholder="https://my-org.okta.com"
                    />
                    <FormField
                      control={control}
                      name="password"
                      label="Okta password"
                      type="password"
                    />
                  </>
                )}
                {field.value === "externalbrowser" && (
                  <p className="rounded bg-amber-50 px-2 py-1 text-[11px] text-amber-900">
                    External browser SSO only works from a desktop process — it cannot
                    open a browser from the Synthia server. Use the OAuth token
                    flow for production discovery jobs.
                  </p>
                )}
              </>
            )}
          />
        </div>
      </fieldset>
    );
  }

  if (connectorType === "databricks") {
    return (
      <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
        <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Authentication
        </legend>
        <div className="space-y-2 pt-1">
          <Controller
            control={control}
            name="databricksAuthMode"
            render={({ field }) => (
              <select
                value={field.value}
                onChange={field.onChange}
                className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
              >
                <option value="token">Personal Access Token (PAT)</option>
                <option value="oauth_m2m">M2M OAuth (service principal)</option>
              </select>
            )}
          />
          <Controller
            control={control}
            name="databricksAuthMode"
            render={({ field }) =>
              field.value === "oauth_m2m" ? (
                <>
                  <FormField control={control} name="databricksClientId" label="Client ID" required />
                  <FormField
                    control={control}
                    name="databricksClientSecret"
                    label="Client Secret"
                    required
                    type="password"
                  />
                </>
              ) : (
                <FormField
                  control={control}
                  name="databricksAccessToken"
                  label="Personal Access Token (PAT)"
                  required
                  type="password"
                  placeholder="dapi••••••••••••••••"
                />
              )
            }
          />
        </div>
      </fieldset>
    );
  }

  if (connectorType === "redshift") {
    return (
      <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
        <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Authentication
        </legend>
        <div className="space-y-2 pt-1">
          <Controller
            control={control}
            name="redshiftAuthMode"
            render={({ field }) => (
              <select
                value={field.value}
                onChange={field.onChange}
                className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
              >
                <option value="password">Password</option>
                <option value="iam">IAM (cluster ID + DB user)</option>
              </select>
            )}
          />
          <Controller
            control={control}
            name="redshiftAuthMode"
            render={({ field }) =>
              field.value === "iam" ? (
                <>
                  <FormField control={control} name="redshiftIamClusterId" label="Cluster ID" required />
                  <FormField control={control} name="redshiftIamDbUser" label="DB User" required />
                  <FormField control={control} name="redshiftAwsRegion" label="AWS Region" />
                </>
              ) : (
                <>
                  <FormField control={control} name="username" label="Username" required />
                  <FormField control={control} name="password" label="Password" type="password" />
                </>
              )
            }
          />
        </div>
      </fieldset>
    );
  }

  if (connectorType === "sqlserver") {
    return (
      <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
        <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Authentication
        </legend>
        <div className="space-y-2 pt-1">
          <Controller
            control={control}
            name="sqlserverAuthMode"
            render={({ field }) => (
              <select
                value={field.value}
                onChange={field.onChange}
                className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
              >
                <option value="password">SQL auth (username + password)</option>
                <option value="azure_ad">Azure AD access token</option>
                <option value="windows">Windows Integrated / Kerberos (Trusted_Connection)</option>
              </select>
            )}
          />
          <Controller
            control={control}
            name="sqlserverAuthMode"
            render={({ field }) =>
              field.value === "azure_ad" ? (
                <>
                  <FormField
                    control={control}
                    name="sqlserverAzureAdToken"
                    label="Azure AD Access Token"
                    required
                    type="password"
                    placeholder="eyJ0eXAiOi…"
                  />
                  <FormField
                    control={control}
                    name="sqlserverPyodbcDriver"
                    label="ODBC Driver name"
                    placeholder="ODBC Driver 18 for SQL Server"
                  />
                </>
              ) : field.value === "windows" ? (
                <p className="rounded bg-blue-50 px-2 py-1 text-[11px] text-blue-900">
                  Uses the OS-level Windows/Kerberos session (Trusted_Connection=yes).
                  The worker must be domain-joined with a valid TGT.
                </p>
              ) : (
                <>
                  <FormField control={control} name="username" label="Username" required />
                  <FormField control={control} name="password" label="Password" type="password" />
                </>
              )
            }
          />
        </div>
      </fieldset>
    );
  }

  if (connectorType === "mongodb") {
    return (
      <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
        <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Authentication
        </legend>
        <div className="space-y-2 pt-1">
          <FormField control={control} name="username" label="Username" />
          <FormField control={control} name="password" label="Password" type="password" />
          <Controller
            control={control}
            name="mongoAuthMechanism"
            render={({ field }) => (
              <label className="block text-xs">
                <span className="font-medium text-foreground">Auth mechanism</span>
                <select
                  value={field.value}
                  onChange={field.onChange}
                  className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-sm"
                >
                  <option value="">Auto-negotiate</option>
                  <option value="SCRAM-SHA-256">SCRAM-SHA-256 (recommended)</option>
                  <option value="SCRAM-SHA-1">SCRAM-SHA-1 (legacy)</option>
                  <option value="MONGODB-X509">X.509 client certificate</option>
                  <option value="GSSAPI">GSSAPI / Kerberos</option>
                  <option value="MONGODB-AWS">AWS IAM</option>
                </select>
              </label>
            )}
          />
          <Controller
            control={control}
            name="mongoAuthMechanism"
            render={({ field }) =>
              field.value === "GSSAPI" ? (
                <FormField
                  control={control}
                  name="mongoGssapiServiceName"
                  label="GSSAPI service name (optional)"
                  placeholder="mongodb"
                />
              ) : field.value === "MONGODB-AWS" ? (
                <FormField
                  control={control}
                  name="mongoAwsSessionToken"
                  label="AWS session token (optional)"
                  type="password"
                />
              ) : field.value === "MONGODB-X509" ? (
                <p className="rounded bg-blue-50 px-2 py-1 text-[11px] text-blue-900">
                  X.509 auth uses the client certificate + key configured below in
                  Source Settings. The user is derived from the cert subject.
                </p>
              ) : (
                <></>
              )
            }
          />
          <FormField control={control} name="mongoAuthSource" label="Auth Source DB (optional)" placeholder="admin" />
          <FormField control={control} name="mongoReplicaSet" label="Replica Set (optional)" placeholder="rs0" />
          <div className="grid grid-cols-2 gap-3">
            <FormField control={control} name="mongoMaxSampleSize" label="Sample size" type="number" min={1} max={10000} />
            <FormField control={control} name="mongoMaxDocDepth" label="Max nesting depth" type="number" min={1} max={10} />
          </div>
        </div>
      </fieldset>
    );
  }

  if (connectorType === "db2") {
    return (
      <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
        <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Authentication
        </legend>
        <div className="space-y-2 pt-1">
          <Controller
            control={control}
            name="db2Platform"
            render={({ field }) => (
              <label className="block text-xs">
                <span className="font-medium text-foreground">DB2 platform</span>
                <select
                  value={field.value}
                  onChange={field.onChange}
                  className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-sm"
                >
                  <option value="luw">DB2 LUW (Linux/Unix/Windows)</option>
                  <option value="zos">DB2 for z/OS (mainframe)</option>
                </select>
              </label>
            )}
          />
          <Controller
            control={control}
            name="db2Security"
            render={({ field }) => (
              <label className="block text-xs">
                <span className="font-medium text-foreground">Security mechanism</span>
                <select
                  value={field.value}
                  onChange={field.onChange}
                  className="mt-1 w-full rounded border border-border bg-background px-2 py-1 text-sm"
                >
                  <option value="SERVER">Server (username/password)</option>
                  <option value="SSL">SSL + username/password</option>
                  <option value="KERBEROS">Kerberos (OS ticket cache)</option>
                  <option value="LDAP">LDAP (IBM LDAP plugin)</option>
                </select>
              </label>
            )}
          />
          <FormField control={control} name="username" label="Username" />
          <FormField control={control} name="password" label="Password" type="password" />
        </div>
      </fieldset>
    );
  }

  if (connectorType === "oracle") {
    return (
      <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
        <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Authentication
        </legend>
        <div className="space-y-2 pt-1">
          <Controller
            control={control}
            name="oracleAuthMode"
            render={({ field }) => (
              <select
                value={field.value}
                onChange={field.onChange}
                className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
              >
                <option value="password">Password</option>
                <option value="kerberos">Kerberos (OS ticket cache)</option>
                <option value="azure_ad">Azure AD (access token)</option>
              </select>
            )}
          />
          <Controller
            control={control}
            name="oracleAuthMode"
            render={({ field }) =>
              field.value === "azure_ad" ? (
                <>
                  <FormField control={control} name="username" label="Principal" required />
                  <FormField
                    control={control}
                    name="oracleAzureAdToken"
                    label="Azure AD Access Token"
                    required
                    type="password"
                  />
                </>
              ) : field.value === "kerberos" ? (
                <p className="rounded bg-blue-50 px-2 py-1 text-[11px] text-blue-900">
                  Uses externalauth — make sure ``kinit`` has run and KRB5CCNAME is set
                  on the worker host.
                </p>
              ) : (
                <>
                  <FormField control={control} name="username" label="Username" required />
                  <FormField control={control} name="password" label="Password" type="password" />
                </>
              )
            }
          />
        </div>
      </fieldset>
    );
  }

  if (connectorType === "mysql") {
    return (
      <>
        <FormField control={control} name="username" label="Username" required placeholder="root" />
        <FormField control={control} name="password" label="Password" type="password" />
        <FormField
          control={control}
          name="mysqlAuthPlugin"
          label="Auth plugin (optional)"
          placeholder="caching_sha2_password / mysql_native_password"
        />
      </>
    );
  }

  // postgresql — plain username + password
  return (
    <>
      <FormField control={control} name="username" label="Username" required placeholder="postgres" />
      <FormField control={control} name="password" label="Password" type="password" />
    </>
  );
}

// ── Source-settings block (SSL, Kerberos, schema filter, drift detection) ──
function SourceSettingsBlock({
  control,
  connectorType,
}: {
  control: Control<ConnectionFieldsetValues>;
  connectorType: string;
}) {
  const supportsKerberos = ["postgresql", "db2"].includes(connectorType);
  return (
    <fieldset className="rounded-md border border-border bg-muted/10 px-3 py-2.5">
      <legend className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Source settings
      </legend>
      <div className="space-y-1.5 pt-1">
        <ToggleRow
          control={control}
          name="sslEnabled"
          label="Enable SSL/TLS"
          help="Encrypt traffic between Synthia and the source database."
        />
        <ToggleRow
          control={control}
          name="sslTrustServerCert"
          label="Trust server certificate"
          help="Skip certificate verification. Use only for non-production environments."
        />
        {supportsKerberos && (
          <ToggleRow
            control={control}
            name="kerberosEnabled"
            label="Enable Kerberos auth"
            help="Replaces username/password with a Kerberos principal handshake."
          />
        )}
        <ToggleRow
          control={control}
          name="blockOnSchemaChange"
          label="Block generation if schema changes"
          help="Halt synthetic/masking jobs if the live schema drifts from the last persisted discovery snapshot."
        />
      </div>

      <div className="mt-2 space-y-2">
        <FormField
          control={control}
          name="sslCaCertPath"
          label="CA certificate path (optional)"
          placeholder="/etc/ssl/certs/ca-bundle.crt"
        />
        <div className="grid grid-cols-2 gap-2">
          <FormField control={control} name="sslClientCertPath" label="Client cert path" placeholder="" />
          <FormField control={control} name="sslClientKeyPath" label="Client key path" placeholder="" />
        </div>
        {supportsKerberos && (
          <FormField
            control={control}
            name="kerberosPrincipal"
            label="Kerberos principal"
            placeholder="user@REALM.AMERITAS.LOCAL"
          />
        )}
        <FormField
          control={control}
          name="localSchemas"
          label="Local schemas"
          placeholder="public, audit, billing"
        />
      </div>
    </fieldset>
  );
}

function ToggleRow({
  control,
  name,
  label,
  help,
}: {
  control: Control<ConnectionFieldsetValues>;
  name: "sslEnabled" | "sslTrustServerCert" | "kerberosEnabled" | "blockOnSchemaChange";
  label: string;
  help: string;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <label className="flex items-start gap-2 cursor-pointer text-xs">
          <input
            type="checkbox"
            checked={!!field.value}
            onChange={(e) => field.onChange(e.target.checked)}
            onBlur={field.onBlur}
            ref={field.ref}
            className="mt-0.5"
          />
          <span>
            <span className="font-medium text-foreground">{label}</span>
            <span className="block text-[11px] text-muted-foreground">{help}</span>
          </span>
        </label>
      )}
    />
  );
}

/**
 * Turn a form-values blob into the payload shape the backend expects.
 *
 * Snowflake gets host synthesised from the account. Per-connector auth
 * data lands in ``extra_params`` (e.g. ``http_path``, ``access_token``,
 * ``private_key_pem``) so the backend connector reads it from one place.
 */
export function buildConnectionPayload(data: ConnectionFieldsetValues): Record<string, unknown> {
  const ct = data.connectorType;
  const isSnowflake = ct === "snowflake";

  const extra: Record<string, unknown> = {};

  // SSL / TLS
  if (data.sslEnabled) extra.ssl = true;
  if (data.sslTrustServerCert) extra.ssl_trust_server_cert = true;
  if (data.sslCaCertPath) extra.ssl_ca_cert_path = data.sslCaCertPath;
  if (data.sslClientCertPath) extra.ssl_client_cert_path = data.sslClientCertPath;
  if (data.sslClientKeyPath) extra.ssl_client_key_path = data.sslClientKeyPath;

  // Kerberos
  if (data.kerberosEnabled) extra.kerberos = true;
  if (data.kerberosPrincipal) extra.kerberos_principal = data.kerberosPrincipal;

  // Discovery scope + drift
  if (data.blockOnSchemaChange) extra.block_on_schema_change = true;
  if (data.localSchemas.trim()) {
    extra.local_schemas = data.localSchemas
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  // Per-connector
  if (isSnowflake) {
    extra.account = data.account;
    extra.warehouse = data.warehouse;
    if (data.role) extra.role = data.role;
    extra.auth_mode = data.snowflakeAuthMode;
    if (data.snowflakeAuthMode === "key_pair") {
      extra.private_key_pem = data.snowflakePrivateKeyPem;
      if (data.snowflakePrivateKeyPassphrase) extra.private_key_passphrase = data.snowflakePrivateKeyPassphrase;
    }
    if (data.snowflakeAuthMode === "oauth") {
      if (data.snowflakeOauthToken) extra.oauth_token = data.snowflakeOauthToken;
      if (data.snowflakeOauthRefreshToken) extra.oauth_refresh_token = data.snowflakeOauthRefreshToken;
      if (data.snowflakeOauthClientId) extra.oauth_client_id = data.snowflakeOauthClientId;
      if (data.snowflakeOauthClientSecret) extra.oauth_client_secret = data.snowflakeOauthClientSecret;
      if (data.snowflakeOauthTokenEndpoint) extra.oauth_token_endpoint = data.snowflakeOauthTokenEndpoint;
    }
    if (data.snowflakeAuthMode === "okta" && data.snowflakeOktaUrl) {
      extra.okta_url = data.snowflakeOktaUrl;
    }
  }
  if (ct === "oracle") {
    if (data.oracleServiceName) extra.service_name = data.oracleServiceName;
    if (data.oraclePdb) extra.oracle_pdb = data.oraclePdb;
    if (data.oracleWalletPath) extra.oracle_wallet_path = data.oracleWalletPath;
    extra.auth_mode = data.oracleAuthMode;
    if (data.oracleAuthMode === "azure_ad" && data.oracleAzureAdToken) {
      extra.azure_ad_token = data.oracleAzureAdToken;
    }
  }
  if (ct === "sqlserver") {
    if (data.sqlserverInstance) extra.instance = data.sqlserverInstance;
    extra.auth_mode = data.sqlserverAuthMode;
    if (data.sqlserverAuthMode === "azure_ad") {
      extra.azure_ad_token = data.sqlserverAzureAdToken;
      if (data.sqlserverPyodbcDriver) extra.pyodbc_driver = data.sqlserverPyodbcDriver;
    }
  }
  if (ct === "redshift") {
    extra.auth_mode = data.redshiftAuthMode;
    if (data.redshiftAuthMode === "iam") {
      extra.iam_cluster_id = data.redshiftIamClusterId;
      extra.iam_db_user = data.redshiftIamDbUser;
      extra.aws_region = data.redshiftAwsRegion;
    }
  }
  if (ct === "databricks") {
    extra.http_path = data.databricksHttpPath;
    extra.auth_mode = data.databricksAuthMode;
    if (data.databricksAuthMode === "oauth_m2m") {
      extra.databricks_client_id = data.databricksClientId;
      extra.databricks_client_secret = data.databricksClientSecret;
    } else {
      extra.access_token = data.databricksAccessToken;
    }
  }
  if (ct === "mongodb") {
    if (data.mongoAuthMechanism) extra.auth_mechanism = data.mongoAuthMechanism;
    if (data.mongoAuthSource) extra.auth_source = data.mongoAuthSource;
    if (data.mongoReplicaSet) extra.replica_set = data.mongoReplicaSet;
    extra.max_sample_size = data.mongoMaxSampleSize;
    extra.max_doc_depth = data.mongoMaxDocDepth;
    if (data.mongoGssapiServiceName) extra.gssapi_service_name = data.mongoGssapiServiceName;
    if (data.mongoAwsSessionToken) extra.aws_session_token = data.mongoAwsSessionToken;
  }
  if (ct === "db2") {
    extra.db2_security = data.db2Security;
    extra.db2_platform = data.db2Platform;
    if (data.db2Security === "KERBEROS") {
      extra.kerberos = true;
      extra.db2_krb_plugin = data.db2KrbPlugin;
    } else if (data.db2Security === "LDAP") {
      extra.ldap_enabled = true;
      extra.db2_ldap_plugin = data.db2LdapPlugin;
    } else if (data.db2Security === "SSL") {
      extra.ssl = true;
    }
  }
  if (ct === "mysql" && data.mysqlAuthPlugin) {
    extra.auth_plugin = data.mysqlAuthPlugin;
  }
  if (isSnowflake) {
    if (data.snowflakeQueryTag) extra.query_tag = data.snowflakeQueryTag;
    if (data.snowflakeStatementTimeoutSeconds) {
      extra.statement_timeout_seconds = data.snowflakeStatementTimeoutSeconds;
    }
  }

  // Free-form JSON extras (advanced)
  try {
    const extras = JSON.parse(data.extraParams || "{}");
    Object.assign(extra, extras);
  } catch {
    // Validated upstream by zod; treat parse failure as "no extras".
  }

  return {
    name: data.name,
    connector_type: ct,
    host: isSnowflake ? `${data.account}.snowflakecomputing.com` : data.host,
    port: data.port,
    database_name: data.databaseName,
    username: data.username,
    password: data.password,
    extra_params: extra,
  };
}

/**
 * Reverse of ``buildConnectionPayload`` — turn a persisted connection (plus
 * its ``safe_extras`` from the backend) back into the form-values shape so
 * the edit drawer can hydrate every field.
 *
 * Without this, opening an edit drawer would default every enterprise auth
 * field to empty; saving would then send those empties to the backend and
 * wipe the stored config (the "edit-save wipes enterprise auth" bug).
 *
 * Defaults from ``base`` are taken from {@link DEFAULT_CONNECTION_VALUES}
 * passed by the caller — that keeps this helper agnostic to which surface
 * (drawer vs wizard) is hosting the form.
 */
export function parseConnectionPayload(
  base: ConnectionFieldsetValues,
  connection: {
    connector_type: string;
    name: string;
    host: string;
    port: number;
    database_name: string;
    username?: string;
    safe_extras?: Record<string, unknown>;
  }
): ConnectionFieldsetValues {
  const e = (connection.safe_extras || {}) as Record<string, unknown>;
  const str = (k: string, fallback = "") => (typeof e[k] === "string" ? (e[k] as string) : fallback);
  const num = (k: string, fallback: number) =>
    typeof e[k] === "number" ? (e[k] as number) : fallback;
  const bool = (k: string) => Boolean(e[k]);
  const list = (k: string) => {
    const v = e[k];
    if (Array.isArray(v)) return v.join(", ");
    if (typeof v === "string") return v;
    return "";
  };
  // Secret keys come back from the backend with their value replaced by ``""``
  // — the KEY presence is what tells us "this secret is stored server-side".
  // We use this to populate the *HasStored flags so validation knows blank
  // input means "preserve" rather than "missing".
  const hasStored = (k: string) => Object.prototype.hasOwnProperty.call(e, k);

  const ct = connection.connector_type;
  const isSnowflake = ct === "snowflake";

  return {
    ...base,
    connectorType: ct,
    name: connection.name,
    // Snowflake stores host as ``<account>.snowflakecomputing.com``; the
    // account field is the canonical identity, so we leave host empty and
    // hydrate account from extras.
    host: isSnowflake ? "" : connection.host,
    port: connection.port,
    databaseName: connection.database_name,
    username: connection.username || "",
    password: "",  // Password is never returned; form treats blank as "preserve"
    // Snowflake
    account: str("account"),
    warehouse: str("warehouse"),
    role: str("role"),
    snowflakeAuthMode: (str("auth_mode", "password") as ConnectionFieldsetValues["snowflakeAuthMode"]) || "password",
    snowflakePrivateKeyPem: "",  // secret, redacted
    snowflakePrivateKeyPassphrase: "",
    snowflakeOauthToken: "",
    snowflakeOauthRefreshToken: "",
    snowflakeOauthClientId: str("oauth_client_id"),
    snowflakeOauthClientSecret: "",
    snowflakeOauthTokenEndpoint: str("oauth_token_endpoint"),
    snowflakeOktaUrl: str("okta_url"),
    snowflakePrivateKeyPemHasStored: hasStored("private_key_pem"),
    snowflakeOauthTokenHasStored: hasStored("oauth_token"),
    snowflakeOauthRefreshTokenHasStored: hasStored("oauth_refresh_token"),
    snowflakeOauthClientSecretHasStored: hasStored("oauth_client_secret"),
    snowflakeQueryTag: str("query_tag"),
    snowflakeStatementTimeoutSeconds: num("statement_timeout_seconds", 300),
    // Oracle
    oracleServiceName: str("service_name"),
    oracleWalletPath: str("oracle_wallet_path"),
    oraclePdb: str("oracle_pdb"),
    oracleAuthMode:
      ct === "oracle"
        ? (str("auth_mode", "password") as ConnectionFieldsetValues["oracleAuthMode"])
        : base.oracleAuthMode,
    oracleAzureAdToken: "",
    oracleAzureAdTokenHasStored: hasStored("azure_ad_token") && ct === "oracle",
    // SQL Server
    sqlserverInstance: str("instance"),
    sqlserverAuthMode:
      ct === "sqlserver"
        ? (str("auth_mode", "password") as ConnectionFieldsetValues["sqlserverAuthMode"])
        : base.sqlserverAuthMode,
    sqlserverAzureAdToken: "",
    sqlserverAzureAdTokenHasStored: hasStored("azure_ad_token") && ct === "sqlserver",
    sqlserverPyodbcDriver: str("pyodbc_driver", base.sqlserverPyodbcDriver),
    // Redshift
    redshiftAuthMode:
      ct === "redshift"
        ? (str("auth_mode", "password") as ConnectionFieldsetValues["redshiftAuthMode"])
        : base.redshiftAuthMode,
    redshiftIamClusterId: str("iam_cluster_id"),
    redshiftIamDbUser: str("iam_db_user"),
    redshiftAwsRegion: str("aws_region", base.redshiftAwsRegion),
    // Databricks
    databricksHttpPath: str("http_path"),
    databricksAuthMode:
      ct === "databricks"
        ? (str("auth_mode", "token") as ConnectionFieldsetValues["databricksAuthMode"])
        : base.databricksAuthMode,
    databricksAccessToken: "",
    databricksAccessTokenHasStored: hasStored("access_token") && ct === "databricks",
    databricksClientId: str("databricks_client_id"),
    databricksClientSecret: "",
    databricksClientSecretHasStored: hasStored("databricks_client_secret"),
    // MongoDB
    mongoAuthMechanism: (str("auth_mechanism") as ConnectionFieldsetValues["mongoAuthMechanism"]) || "",
    mongoAuthSource: str("auth_source"),
    mongoReplicaSet: str("replica_set"),
    mongoMaxSampleSize: num("max_sample_size", 100),
    mongoMaxDocDepth: num("max_doc_depth", 2),
    mongoGssapiServiceName: str("gssapi_service_name"),
    mongoAwsSessionToken: "",
    // DB2
    db2Security:
      (str("db2_security") as ConnectionFieldsetValues["db2Security"]) || base.db2Security,
    db2Platform:
      (str("db2_platform") as ConnectionFieldsetValues["db2Platform"]) || base.db2Platform,
    db2LdapPlugin: str("db2_ldap_plugin", base.db2LdapPlugin),
    db2KrbPlugin: str("db2_krb_plugin", base.db2KrbPlugin),
    // MySQL
    mysqlAuthPlugin: str("auth_plugin"),
    // Shared SSL / Kerberos / discovery
    sslEnabled: bool("ssl"),
    sslTrustServerCert: bool("ssl_trust_server_cert"),
    sslCaCertPath: str("ssl_ca_cert_path"),
    sslClientCertPath: str("ssl_client_cert_path"),
    sslClientKeyPath: str("ssl_client_key_path"),
    kerberosEnabled: bool("kerberos"),
    kerberosPrincipal: str("kerberos_principal"),
    localSchemas: list("local_schemas"),
    blockOnSchemaChange: bool("block_on_schema_change"),
    extraParams: "{}",
  };
}
