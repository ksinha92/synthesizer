/** Per-connector setup guides shown by the info-button popup in the
 *  Add Connection picker. Each guide is structured so the dialog can render
 *  tabs uniformly (prereqs / setup / test / troubleshoot) and surface
 *  copy-to-clipboard commands.
 */

export interface GuideStep {
  title: string;
  body: string;
  /** Optional code/SQL the user should run on their side. Renders with a Copy button. */
  code?: { lang: "sql" | "bash" | "json" | "ini"; value: string };
}

export interface GuideTroubleshoot {
  error: string;
  fix: string;
}

export interface ConnectorGuide {
  /** Matches `Connector.value` in connector-tile-grid.tsx */
  value: string;
  label: string;
  summary: string;
  defaults: { host: string; port: number; placeholderDb: string };
  prerequisites: string[];
  setup: GuideStep[];
  test: { command: string; lang: "bash" | "sql"; note: string };
  troubleshoot: GuideTroubleshoot[];
}

const GRANT_PG = `-- Run as a Postgres superuser
CREATE ROLE synthia_reader WITH LOGIN PASSWORD 'change-me';
GRANT CONNECT ON DATABASE your_db TO synthia_reader;
\\c your_db
GRANT USAGE ON SCHEMA public TO synthia_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO synthia_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO synthia_reader;`;

const GRANT_MYSQL = `-- Run as a MySQL admin (e.g., root)
CREATE USER 'synthia_reader'@'%' IDENTIFIED BY 'change-me';
GRANT SELECT ON your_db.* TO 'synthia_reader'@'%';
FLUSH PRIVILEGES;`;

const GRANT_SQLSERVER = `-- Run as a SQL Server sysadmin
CREATE LOGIN synthia_reader WITH PASSWORD = 'Change-Me-123!';
USE [your_db];
CREATE USER synthia_reader FOR LOGIN synthia_reader;
ALTER ROLE db_datareader ADD MEMBER synthia_reader;`;

const GRANT_ORACLE = `-- Run as SYS or a DBA in the target PDB
CREATE USER synthia_reader IDENTIFIED BY "Change-Me-1";
GRANT CREATE SESSION TO synthia_reader;
GRANT SELECT ANY TABLE TO synthia_reader;
-- Or more conservatively, GRANT SELECT ON each schema you want to expose.`;

const GRANT_DB2 = `-- Run as an authorised DB2 administrator
db2 "CREATE USER synthia_reader USING 'change-me'"
-- Then in the target database:
db2 "GRANT CONNECT ON DATABASE TO USER synthia_reader"
db2 "GRANT SELECT ON SCHEMA YOUR_SCHEMA TO USER synthia_reader"`;

const GRANT_SNOWFLAKE = `-- Run as ACCOUNTADMIN
CREATE ROLE synthia_reader;
GRANT USAGE ON WAREHOUSE compute_wh TO ROLE synthia_reader;
GRANT USAGE ON DATABASE your_db TO ROLE synthia_reader;
GRANT USAGE ON ALL SCHEMAS IN DATABASE your_db TO ROLE synthia_reader;
GRANT SELECT ON ALL TABLES IN DATABASE your_db TO ROLE synthia_reader;
GRANT SELECT ON FUTURE TABLES IN DATABASE your_db TO ROLE synthia_reader;
CREATE USER synthia_user PASSWORD = 'change-me' DEFAULT_ROLE = synthia_reader;
GRANT ROLE synthia_reader TO USER synthia_user;`;

const GRANT_REDSHIFT = `-- Run as a Redshift admin (superuser)
CREATE USER synthia_reader WITH PASSWORD 'Change-Me-1';
GRANT USAGE ON SCHEMA public TO synthia_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO synthia_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO synthia_reader;`;

const GRANT_DATABRICKS = `-- Run in a Databricks SQL warehouse as a workspace admin
CREATE USER \`synthia-reader@example.com\`;
GRANT USE_CATALOG ON CATALOG main TO \`synthia-reader@example.com\`;
GRANT USE_SCHEMA ON SCHEMA main.your_schema TO \`synthia-reader@example.com\`;
GRANT SELECT ON SCHEMA main.your_schema TO \`synthia-reader@example.com\`;`;

const MONGO_USER = `// Run in mongosh, as an admin
use your_db
db.createUser({
  user: "synthia_reader",
  pwd: "change-me",
  roles: [ { role: "read", db: "your_db" } ]
})`;

export const CONNECTOR_GUIDES: ConnectorGuide[] = [
  // ── PostgreSQL ──────────────────────────────────────────────────────
  {
    value: "postgresql",
    label: "PostgreSQL",
    summary:
      "Synthia's Postgres connector supports password and Kerberos auth. Discovery samples small batches; you control which schemas/tables it can see via standard GRANTs. TLS is supported via ssl_ca_cert_path / ssl_client_cert_path in the advanced extras.",
    defaults: { host: "your-postgres-host.internal", port: 5432, placeholderDb: "your_db" },
    prerequisites: [
      "Postgres reachable from Synthia (TCP 5432 by default).",
      "Ability to create a role with SELECT on the schemas you want to expose. Password or Kerberos auth.",
      "Postgres is configured to accept TCP/IP connections (listen_addresses in postgresql.conf).",
    ],
    setup: [
      {
        title: "Create a read-only role",
        body: "We strongly recommend a dedicated read-only role. Grant SELECT only on the schemas you want Synthia to discover.",
        code: { lang: "sql", value: GRANT_PG },
      },
      {
        title: "Allow the role from the network",
        body: "If your pg_hba.conf restricts connections by host, add a line for Synthia's egress IP allowing the new role. md5 or scram-sha-256 auth methods are both supported.",
      },
      {
        title: "Fill the connection form",
        body: "Host = your DB host (no protocol prefix), Port = 5432, Database = the target DB name, Username = synthia_reader, Password = the role's password.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "psql -h your-postgres-host.internal -p 5432 -U synthia_reader -d your_db -c 'SELECT 1;'",
      note: "If this returns 1 from your laptop with the same credentials Synthia will use, the connection will work.",
    },
    troubleshoot: [
      {
        error: "FATAL: no pg_hba.conf entry",
        fix: "Add a host line in pg_hba.conf permitting the role from Synthia's source CIDR; reload Postgres (pg_ctl reload).",
      },
      {
        error: "permission denied for schema",
        fix: "Re-run the GRANTs — newly-created tables also need ALTER DEFAULT PRIVILEGES so Synthia can read them later.",
      },
      {
        error: "connection refused on 5432",
        fix: "Check listen_addresses = '*' (or your specific interface) and that a firewall isn't dropping inbound TCP/5432.",
      },
    ],
  },

  // ── MySQL ───────────────────────────────────────────────────────────
  {
    value: "mysql",
    label: "MySQL",
    summary:
      "MySQL or MariaDB. Password auth only. A read-only user with SELECT on the target database is sufficient for discovery and masking jobs. Use auth_plugin in the advanced extras if your server requires mysql_native_password vs caching_sha2_password.",
    defaults: { host: "your-mysql-host.internal", port: 3306, placeholderDb: "your_db" },
    prerequisites: [
      "MySQL 5.7 / 8.0 or MariaDB 10.3+ reachable on TCP/3306 (or your custom port).",
      "Ability to create a user with SELECT on the target schema.",
      "Server's bind-address allows non-localhost connections.",
    ],
    setup: [
      {
        title: "Create a read-only user",
        body: "MySQL 8 stores password hashes per host. The '%' wildcard lets the user connect from any source IP — tighten it to Synthia's egress range in production.",
        code: { lang: "sql", value: GRANT_MYSQL },
      },
      {
        title: "Verify bind-address",
        body: "In /etc/mysql/my.cnf set bind-address = 0.0.0.0 (or the interface that Synthia can reach), then restart mysqld. Default bind to 127.0.0.1 only accepts local sockets.",
      },
      {
        title: "Fill the form",
        body: "Host = MySQL host, Port = 3306, Database = your_db, Username = synthia_reader, Password = the user's password.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "mysql -h your-mysql-host.internal -P 3306 -u synthia_reader -p your_db -e 'SELECT 1;'",
      note: "You should see a single row with '1'. If you get 'Access denied' the GRANT didn't take effect — check `SHOW GRANTS FOR 'synthia_reader'@'%';`.",
    },
    troubleshoot: [
      {
        error: "Access denied for user 'synthia_reader'@'…'",
        fix: "The host part of the user account must match the source. Either GRANT … TO 'synthia_reader'@'%' or create a separate account for Synthia's source IP.",
      },
      {
        error: "Authentication plugin 'caching_sha2_password' cannot be loaded",
        fix: "Older clients/proxies don't speak SHA2. ALTER USER 'synthia_reader'@'%' IDENTIFIED WITH mysql_native_password BY 'change-me';",
      },
    ],
  },

  // ── MongoDB ─────────────────────────────────────────────────────────
  {
    value: "mongodb",
    label: "MongoDB",
    summary:
      "Self-hosted MongoDB or Atlas. Supports password, SCRAM-SHA-256/1, X.509, GSSAPI/Kerberos, and AWS auth — pick one via the auth_mechanism extra. Discovery samples documents to infer the schema; PII classification happens per top-level field path.",
    defaults: { host: "your-mongo-host.internal", port: 27017, placeholderDb: "your_db" },
    prerequisites: [
      "MongoDB reachable from Synthia (TCP 27017 by default), or an Atlas cluster.",
      "A user with the `read` role on the target database (or the equivalent under your chosen auth mechanism).",
      "If using Atlas, add Synthia's egress IPs to the Project IP Access List.",
    ],
    setup: [
      {
        title: "Create a read-only user",
        body: "MongoDB authenticates against an auth database. Use the target database itself (or `admin` if your standards require it) — set the `auth_source` extra accordingly. Optional `replica_set` extra if connecting to a replica set.",
        code: { lang: "json", value: MONGO_USER },
      },
      {
        title: "Pick an auth mechanism",
        body: "Default is password (SCRAM under the hood). For X.509, GSSAPI/Kerberos, or AWS IAM, set the `auth_mechanism` extra to scram_sha_256 / x509 / gssapi / aws and add the matching credential extras (e.g. gssapi_service_name).",
      },
      {
        title: "Fill the form",
        body: "Host = Mongo primary or mongos hostname, Port = 27017, Database = your_db. Synthia builds a plain mongodb:// URI from Host + Port — mongodb+srv:// (SRV) hostnames are NOT supported here; resolve SRV out of band and put the resulting host/port pair in the form. For replica sets, also set the `replica_set` extra. TLS via ssl_ca_cert_path / ssl_client_cert_path extras.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "mongosh 'mongodb://synthia_reader:change-me@your-mongo-host.internal:27017/your_db?authSource=your_db'",
      note: "Then `show collections;` — if you see the target collections, Synthia can too.",
    },
    troubleshoot: [
      {
        error: "Authentication failed",
        fix: "Almost always an `auth_source` mismatch. Set the `auth_source` extra to the DB the user was created in (often `admin`).",
      },
      {
        error: "No suitable servers found (server selection timeout)",
        fix: "Network blocked. Confirm Synthia's egress IPs are in your firewall + (for Atlas) the project IP access list.",
      },
    ],
  },

  // ── Oracle ──────────────────────────────────────────────────────────
  {
    value: "oracle",
    label: "Oracle",
    summary:
      "Oracle Database. Supports password, Kerberos, and Azure AD auth. Service name and PDB name live in the advanced extras (service_name, oracle_pdb); the top-level Database field is the SID or fallback service name.",
    defaults: { host: "your-oracle-host.internal", port: 1521, placeholderDb: "ORCLPDB1" },
    prerequisites: [
      "An Oracle DB reachable on TCP/1521 (or the configured port).",
      "DBA access to create a user and grant CREATE SESSION + SELECT.",
      "Connect string ingredients ready: hostname, listener port, and either a SID or a service name (for PDBs).",
    ],
    setup: [
      {
        title: "Create the user in the right container",
        body: "If you're on a multi-tenant CDB, ALTER SESSION SET CONTAINER = your_pdb before creating the user — common users (C##…) are usually not what you want.",
        code: { lang: "sql", value: GRANT_ORACLE },
      },
      {
        title: "Configure the advanced extras for PDBs",
        body: "Synthia's top-level Database field is the SID or default service name. For a PDB, set the service_name extra (e.g. ORCLPDB1) and optionally the oracle_pdb extra. For mTLS, also set oracle_wallet_path.",
      },
      {
        title: "Fill the form",
        body: "Host = listener host, Port = 1521, Database = SID or service name, Username + Password. Auth mode (password / kerberos / azure_ad) is set via advanced extras; for Azure AD pass azure_ad_token.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "sqlplus synthia_reader/change-me@your-oracle-host.internal:1521/ORCLPDB1",
      note: "Connect, then `SELECT 1 FROM dual;`. If sqlplus prompts for a re-login or hangs, the listener isn't routing to your PDB.",
    },
    troubleshoot: [
      {
        error: "ORA-12514: TNS:listener does not currently know of service requested",
        fix: "Service name typo, or the PDB is closed. Run `SHOW PDBS;` as SYS and `ALTER PLUGGABLE DATABASE … OPEN;` if needed.",
      },
      {
        error: "ORA-01017: invalid username/password",
        fix: "Make sure you created the user in the PDB, not the CDB root. Oracle is case-sensitive when quoted identifiers were used.",
      },
    ],
  },

  // ── SQL Server ──────────────────────────────────────────────────────
  {
    value: "sqlserver",
    label: "SQL Server",
    summary:
      "Microsoft SQL Server or Azure SQL Database. Three auth modes: SQL password (db_datareader on the target DB), Windows / Kerberos integrated auth, or Azure AD token. The msodbcsql18 driver must be present in the worker image.",
    defaults: { host: "your-mssql-host.internal", port: 1433, placeholderDb: "your_db" },
    prerequisites: [
      "SQL Server reachable, or an Azure SQL DB / Managed Instance.",
      "For SQL-auth: Mixed-mode authentication enabled and a SQL login. For Windows auth: configured Kerberos. For Azure AD: an azure_ad_token in the advanced extras.",
      "TCP/IP protocol enabled in SQL Server Configuration Manager.",
    ],
    setup: [
      {
        title: "Create a SQL login + database user",
        body: "SQL Server splits server-level logins from database-level users. You need both — the login lets you connect; the user lets you read.",
        code: { lang: "sql", value: GRANT_SQLSERVER },
      },
      {
        title: "Enable TCP/IP and confirm the port",
        body: "In SQL Server Configuration Manager → SQL Server Network Configuration → Protocols for MSSQLSERVER, enable TCP/IP. Default port is 1433; named instances often use dynamic ports — fix it to 1433 for Synthia.",
      },
      {
        title: "Fill the form",
        body: "Host = SQL Server hostname, Port = 1433, Database = your_db, Username = synthia_reader, Password = the SQL-login password.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "sqlcmd -S your-mssql-host.internal,1433 -U synthia_reader -P 'Change-Me-123!' -d your_db -Q 'SELECT 1;'",
      note: "Note the comma (not colon) between host and port — that's the sqlcmd convention.",
    },
    troubleshoot: [
      {
        error: "Login failed for user 'synthia_reader'",
        fix: "Most often: the LOGIN exists but the database USER doesn't. Re-run CREATE USER + ALTER ROLE. Also check Mixed-mode auth is enabled.",
      },
      {
        error: "Cannot open server '…' requested by the login. Client with IP … is not allowed",
        fix: "Azure SQL firewall. Add Synthia's egress IPs to the server-level firewall rules.",
      },
    ],
  },

  // ── DB2 ─────────────────────────────────────────────────────────────
  {
    value: "db2",
    label: "IBM DB2",
    summary:
      "IBM DB2 LUW. Three auth modes are supported: password, Kerberos, and LDAP. Pick one via the db2_security extra (LDAP requires ldap_enabled=true; Kerberos via the kerberos flag and a principal).",
    defaults: { host: "your-db2-host.internal", port: 50000, placeholderDb: "SAMPLE" },
    prerequisites: [
      "DB2 LUW reachable.",
      "DB2COMM=TCPIP and SVCENAME set to a port (default 50000).",
      "Ability to create a user via the OS (for password auth) or via your IAM/LDAP/Kerberos infrastructure, then grant SELECT inside DB2.",
    ],
    setup: [
      {
        title: "Provision the user + grants",
        body: "DB2 authenticates against the OS by default. Create the OS user first, then grant DB2 privileges to that identity.",
        code: { lang: "bash", value: GRANT_DB2 },
      },
      {
        title: "Confirm the listener",
        body: "Run `db2 get dbm cfg | grep -i svcename` — confirm it matches the port you're entering into Synthia. Then `db2set DB2COMM=TCPIP` and restart the instance if needed.",
      },
      {
        title: "Fill the form",
        body: "Host = DB2 host, Port = 50000, Database = database alias (SAMPLE in many tutorials), Username + Password.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "db2 connect to SAMPLE user synthia_reader using change-me && db2 \"SELECT 1 FROM SYSIBM.SYSDUMMY1\"",
      note: "If `connect to` succeeds and the SELECT returns 1, Synthia will connect with the same credentials.",
    },
    troubleshoot: [
      {
        error: "SQL30081N A communication error has been detected",
        fix: "The DB2 listener isn't up or the port differs. Check `db2 get dbm cfg | grep SVCENAME` and the OS-level service.",
      },
      {
        error: "SQL1060N User does not have CONNECT privilege",
        fix: "Run `db2 GRANT CONNECT ON DATABASE TO USER synthia_reader` while connected as a DBA.",
      },
    ],
  },

  // ── Snowflake ───────────────────────────────────────────────────────
  {
    value: "snowflake",
    label: "Snowflake",
    summary:
      "Snowflake. The connector reads the account locator and warehouse from the advanced extras (account, warehouse) — Host is informational only. Supports password, key-pair, OAuth, Okta, and externalbrowser auth.",
    defaults: { host: "myaccount.snowflakecomputing.com", port: 443, placeholderDb: "YOUR_DB" },
    prerequisites: [
      "An active Snowflake account locator (e.g., xy12345 or xy12345.us-east-1).",
      "A virtual warehouse the Synthia role can USE.",
      "ACCOUNTADMIN (or equivalent) access to provision the role and user.",
    ],
    setup: [
      {
        title: "Create a role, user, and grants",
        body: "Snowflake is grant-heavy: USAGE on warehouse + database + schema + SELECT on tables, plus FUTURE grants so newly-created tables remain readable.",
        code: { lang: "sql", value: GRANT_SNOWFLAKE },
      },
      {
        title: "Set the required extras",
        body: "In the connection form's advanced panel, set account (the locator — e.g. xy12345.us-east-1, NOT the full snowflakecomputing.com URL) and warehouse (e.g. COMPUTE_WH). Optionally set role.",
      },
      {
        title: "Pick an auth mode (optional)",
        body: "Default is password. For key-pair, set the private_key_pem extra and (if encrypted) private_key_passphrase. For OAuth, set oauth_token (or the refresh-token + client_id + client_secret triple). For Okta, set okta_url.",
      },
      {
        title: "Fill the form",
        body: "Host = your snowflakecomputing.com URL (informational), Port = 443, Database = the database, Username + Password (or leave password blank when using key-pair / OAuth). All real connection routing comes from the extras above.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "snowsql -a xy12345.us-east-1 -u synthia_user -d your_db -w compute_wh -q 'SELECT 1;'",
      note: "Pass -a (account locator), -w (warehouse), and -d (database). If snowsql succeeds with these values, copy them verbatim into Synthia's account/warehouse extras.",
    },
    troubleshoot: [
      {
        error: "Required extra 'account' is missing",
        fix: "Synthia reads the account locator from extras.account, not from Host. Open the advanced panel and set account to your locator (xy12345.us-east-1 or similar).",
      },
      {
        error: "Insufficient privileges to operate on warehouse 'COMPUTE_WH'",
        fix: "Add `GRANT USAGE ON WAREHOUSE compute_wh TO ROLE synthia_reader;`. Snowflake won't auto-resume a suspended warehouse without OPERATE either — grant OPERATE if you want auto-resume.",
      },
      {
        error: "Object does not exist or not authorized",
        fix: "Snowflake is case-sensitive when objects were created with quoted identifiers. Confirm spelling in the role's grant list (`SHOW GRANTS TO ROLE …`).",
      },
    ],
  },

  // ── Redshift ────────────────────────────────────────────────────────
  {
    value: "redshift",
    label: "Amazon Redshift",
    summary:
      "Redshift provisioned clusters or Serverless. Two auth modes: password (default) and IAM (set auth_mode=iam plus iam_cluster_id, iam_db_user, aws_region in extras). SSL is on by default; sslmode is verify-ca unless ssl_trust_server_cert is set.",
    defaults: { host: "your-cluster.abc.us-east-1.redshift.amazonaws.com", port: 5439, placeholderDb: "your_db" },
    prerequisites: [
      "A Redshift cluster or Serverless workgroup reachable from Synthia.",
      "A VPC security group rule permitting inbound TCP/5439 from Synthia's egress IPs.",
      "Either: a SQL user with SELECT (for password auth), OR an IAM role/user with redshift:GetClusterCredentials (for IAM auth).",
    ],
    setup: [
      {
        title: "Create a read-only user (password auth)",
        body: "Redshift uses Postgres-style grants but doesn't support some PG features (e.g., no role inheritance in some versions). The grant below works on RA3 and Serverless.",
        code: { lang: "sql", value: GRANT_REDSHIFT },
      },
      {
        title: "Or configure IAM auth",
        body: "Skip the password and set the advanced extras: auth_mode=iam, iam_cluster_id=your-cluster-id, iam_db_user=synthia_reader, aws_region=us-east-1. The worker uses the host environment's AWS credentials to call GetClusterCredentials.",
      },
      {
        title: "Open the VPC security group",
        body: "Add an inbound rule on the cluster's security group: TCP 5439 from Synthia's CIDR. If the cluster is in a private subnet, you also need NAT/Transit Gateway routing.",
      },
      {
        title: "Fill the form",
        body: "Host = full Redshift endpoint, Port = 5439, Database = the DB (often the default 'dev' if you haven't created one). For password auth provide Username + Password; for IAM auth leave them blank and use the extras above.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "psql -h your-cluster.abc.us-east-1.redshift.amazonaws.com -p 5439 -U synthia_reader -d your_db -c 'SELECT 1;'",
      note: "psql works against Redshift because the wire protocol is PG-compatible. If this works, Synthia will work.",
    },
    troubleshoot: [
      {
        error: "could not connect to server: Connection timed out",
        fix: "Almost always VPC routing. The cluster's security group must allow Synthia's source IPs on TCP/5439, and the route must exist (NAT GW for private subnets).",
      },
      {
        error: "permission denied for relation pg_class",
        fix: "Redshift restricts some catalog tables. Use `pg_catalog.svv_columns` and `svv_tables` rather than `information_schema` for full coverage.",
      },
    ],
  },

  // ── Databricks ──────────────────────────────────────────────────────
  {
    value: "databricks",
    label: "Databricks",
    summary:
      "Databricks SQL warehouse. http_path is REQUIRED in the advanced extras. Two auth modes: token (default — access_token extra or the Password field) and oauth_m2m (set databricks_client_id + databricks_client_secret). Unity Catalog grants control visibility.",
    defaults: { host: "your-workspace.cloud.databricks.com", port: 443, placeholderDb: "main" },
    prerequisites: [
      "A SQL warehouse (Pro or Serverless) in the workspace.",
      "Either a personal access token (token auth), or an OAuth service-principal client_id + client_secret (oauth_m2m auth).",
      "The warehouse's HTTP Path — visible on the SQL warehouse details page (e.g. /sql/1.0/warehouses/abcd1234).",
      "Unity Catalog enabled (recommended).",
    ],
    setup: [
      {
        title: "Provision Unity Catalog grants",
        body: "Grant USE on the catalog and schema, then SELECT on the schema. Databricks supports group-level grants — recommended over individual users for service workloads.",
        code: { lang: "sql", value: GRANT_DATABRICKS },
      },
      {
        title: "Set the required http_path extra",
        body: "Open the advanced panel and paste the warehouse's HTTP Path (e.g. /sql/1.0/warehouses/abcd1234). Without this, the connection will fail with a missing-extra error.",
      },
      {
        title: "Choose your auth mode",
        body: "Token (default): mint a PAT under Workspace → Settings → Developer → Access Tokens, then paste it into either the access_token extra or the Password field. OAuth M2M: set auth_mode=oauth_m2m and provide databricks_client_id + databricks_client_secret in extras.",
      },
      {
        title: "Fill the form",
        body: "Host = workspace URL (without https://), Port = 443, Database = catalog (e.g., main). Username is unused for token / M2M auth. Confirm http_path is set in extras before saving.",
      },
    ],
    test: {
      lang: "bash",
      command:
        "python -c \"from databricks import sql; c=sql.connect(server_hostname='your-workspace.cloud.databricks.com', http_path='/sql/1.0/warehouses/abcd1234', access_token='dapi…'); cur=c.cursor(); cur.execute('SELECT 1'); print(cur.fetchall()); cur.close(); c.close()\"",
      note: "This uses the exact same library and parameters (server_hostname / http_path / access_token / catalog) that Synthia's connector uses internally. If it succeeds with your values, the connection form will succeed too. Replace the host, http_path, and access_token with yours. Install with `pip install databricks-sql-connector` first.",
    },
    troubleshoot: [
      {
        error: "Required extra 'http_path' is missing",
        fix: "http_path is mandatory for Databricks. Open the warehouse details page in the workspace UI, copy the HTTP Path, and paste it into the http_path extra in Synthia's advanced panel.",
      },
      {
        error: "Permission denied: user does not have USE_SCHEMA on …",
        fix: "Unity Catalog requires explicit USE on every level (catalog → schema). Grant USE_CATALOG and USE_SCHEMA, then SELECT.",
      },
      {
        error: "warehouse is not running",
        fix: "Synthia doesn't auto-start Pro warehouses. Either enable auto-start on the warehouse settings, or use a Serverless warehouse which is always on.",
      },
    ],
  },
];

export function getGuide(value: string): ConnectorGuide | undefined {
  return CONNECTOR_GUIDES.find((g) => g.value === value);
}
