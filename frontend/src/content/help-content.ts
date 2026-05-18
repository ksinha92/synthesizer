import {
  Activity,
  Boxes,
  ClipboardCheck,
  Database,
  Eye,
  FileSearch,
  FlaskConical,
  Globe,
  HardDrive,
  Layers,
  Lock,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TestTube,
  Webhook,
  Workflow,
  Zap,
  type LucideIcon,
} from "lucide-react";

/** Visual treatment for the topic hero illustration. The component picks the
 *  matching SVG/animation — keeping this typed prevents typos. */
export type IllustrationKind =
  | "data-flow"
  | "shield-network"
  | "scanner"
  | "mask-reveal"
  | "synthetic-loop"
  | "subset-slice"
  | "workflow-graph"
  | "job-pipeline"
  | "report-doc"
  | "ephemeral-bubble"
  | "preset-stamp"
  | "rule-pattern"
  | "webhook-fan"
  | "admin-keys"
  | "project-tree";

/** Optional interactive demo widget to render on the topic page. */
export type DemoKind = "mask-preview" | "pii-classifier" | "subset-builder" | "none";

export interface HelpTopic {
  slug: string;
  title: string;
  short: string;
  icon: LucideIcon;
  illustration: IllustrationKind;
  accent: string; // chart-N color token
  category: "Core" | "Privacy" | "Generation" | "Orchestration" | "Operations" | "Admin";
  appRoute?: string; // deep link to the feature inside the app
  what: string;
  whenToUse: string[];
  howItWorks: { title: string; body: string }[];
  examples: { title: string; body: string }[];
  gotchas: string[];
  demo: DemoKind;
}

export const HELP_TOPICS: HelpTopic[] = [
  {
    slug: "projects",
    title: "Projects",
    short: "Workspaces that group connections, policies, and runs by application or environment.",
    icon: Boxes,
    illustration: "project-tree",
    accent: "--chart-1",
    category: "Core",
    appRoute: "/projects",
    what: "A project is the top-level container in Synthia. It owns connections to data sources, masking policies, synthetic-data configurations, run history, and access permissions. Everything else lives under a project.",
    whenToUse: [
      "You're starting work for a new application, team, or environment.",
      "You want to keep sensitive-data policies isolated per business unit.",
      "You need to grant a small set of users access to one workload only.",
    ],
    howItWorks: [
      { title: "Create", body: "Click 'New Project' from the project list. Give it a name and environment label (production / staging / dev)." },
      { title: "Wire", body: "Add one or more connections to data sources. Run discovery to populate the privacy hub." },
      { title: "Operate", body: "Build masking policies, generate synthetic data, schedule workflows. All runs are scoped to this project." },
    ],
    examples: [
      { title: "Production policies", body: "A 'Customer-Facing Production' project holds the strict masking policies that Compliance signs off on every quarter." },
      { title: "QA sandbox", body: "A 'QA Sandbox' project pulls subsetted, masked production data into a dev environment for engineers." },
    ],
    gotchas: [
      "Project deletion is irreversible and cascades to all child rows (connections, policies, jobs).",
      "Project names must be unique within your organization.",
    ],
    demo: "none",
  },
  {
    slug: "connections",
    title: "Connections",
    short: "Authenticated links to source databases, file systems, or warehouses.",
    icon: Database,
    illustration: "data-flow",
    accent: "--chart-2",
    category: "Core",
    appRoute: "/projects",
    what: "Connections describe how Synthia reaches your data. Each connection stores credentials encrypted at rest and is scoped to a single project. Connectors include Postgres, MySQL, SQL Server, Snowflake, Oracle, Redshift, Databricks, DB2, and MongoDB.",
    whenToUse: [
      "Before running discovery on a new data source.",
      "When you need to point a project at a new environment (e.g., promoting masking from staging to production).",
    ],
    howItWorks: [
      { title: "Provide details", body: "Host, port, database name, credentials. We test the connection before saving." },
      { title: "Encrypt and store", body: "Credentials are encrypted with Fernet and never exposed back to the UI." },
      { title: "Discover", body: "Run discovery against the connection to enumerate schemas, tables, and columns." },
    ],
    examples: [
      { title: "Read-only role", body: "Use a read-only DB role that only has SELECT on the schemas you want to discover — keeps Synthia from accidentally writing." },
      { title: "Multiple envs", body: "Two connections per project: 'prod-readonly' for discovery, 'dev-readwrite' for synthetic-data destinations." },
    ],
    gotchas: [
      "Connections only test reachability — they don't validate permissions on every table.",
      "Rotating credentials elsewhere will fail discovery silently until you update the connection.",
    ],
    demo: "none",
  },
  {
    slug: "discovery",
    title: "Discovery",
    short: "Automated PII classification that scans tables and labels sensitive columns.",
    icon: FileSearch,
    illustration: "scanner",
    accent: "--chart-3",
    category: "Privacy",
    appRoute: "/projects",
    what: "Discovery walks each connection's schema, samples values, and applies a layered classifier (regex + column-name heuristics + ML) to label each column with a PII type (email, ssn, phone, address, dob, name, credit_card, ip_address, or none). Results feed every downstream policy.",
    whenToUse: [
      "First run on a new connection.",
      "After a schema change (new columns, renamed tables).",
      "Periodically to catch drift in unstructured columns.",
    ],
    howItWorks: [
      { title: "Sample", body: "We pull a small, random sample from each table (default 1,000 rows) — no full-table scan." },
      { title: "Classify", body: "Each column gets a PII type plus a confidence score (0-1)." },
      { title: "Persist", body: "Results are written to the privacy hub. Low-confidence calls are flagged 'needs_review'." },
    ],
    examples: [
      { title: "First scan", body: "On a 200-table Postgres source, expect 30-60 seconds to classify ~3,000 columns." },
      { title: "Override", body: "If discovery mis-flags 'product_code' as an SSN, override it to 'none' from the privacy hub." },
    ],
    gotchas: [
      "Discovery is read-only but still issues SELECTs. On busy production, run during off-hours.",
      "Sample-based classification can miss PII that only appears in tail data. Re-run with a larger sample for high-volume tables.",
    ],
    demo: "pii-classifier",
  },
  {
    slug: "privacy-hub",
    title: "Privacy Hub",
    short: "Single pane showing PII coverage, risk, and remediation across a project.",
    icon: Shield,
    illustration: "shield-network",
    accent: "--chart-4",
    category: "Privacy",
    appRoute: "/projects",
    what: "The Privacy Hub aggregates discovery results into a project-wide view: how many sensitive columns exist, how many are covered by a masking policy, and which are still exposed. It's the canonical answer to 'where is our PII risk concentrated?'",
    whenToUse: [
      "Reviewing risk before signing off on a release.",
      "Building a remediation backlog for unmasked sensitive columns.",
      "Auditing coverage during a compliance review.",
    ],
    howItWorks: [
      { title: "Aggregate", body: "We join discovery classifications with active masking rules to compute coverage per table." },
      { title: "Rate", body: "Each table gets a privacy rating (0-100) based on coverage and sensitivity density." },
      { title: "Recommend", body: "For each unprotected PII type we suggest the best-fit generator (faker_replace, hash, format-preserving encryption, etc.)." },
    ],
    examples: [
      { title: "Coverage gap", body: "Privacy Hub flags 12 unprotected email columns in 'customers' → one click adds a faker_replace rule to all of them." },
      { title: "Pre-release audit", body: "Run a compliance report directly from the hub for the latest snapshot of coverage." },
    ],
    gotchas: [
      "Coverage only counts active rules — disabled rules don't protect data.",
      "A column's PII type can change between discovery runs if you broaden the sample size.",
    ],
    demo: "none",
  },
  {
    slug: "masking",
    title: "Masking",
    short: "Policies that transform sensitive columns into safe, realistic values.",
    icon: Lock,
    illustration: "mask-reveal",
    accent: "--chart-5",
    category: "Privacy",
    appRoute: "/projects",
    what: "A masking policy is a named bundle of rules. Each rule targets a column (or a pattern across columns) and applies one of Synthia's strategies: redact, hash (HMAC-SHA256), faker replace, partial mask, format-preserving encryption (FPE), shuffle, nullify, or Presidio redact for narrative columns. Rules can be linked so a row's first_name + last_name + email are generated together.",
    whenToUse: [
      "Producing test data from production for engineering or QA.",
      "Sharing data with a third-party vendor under a DPA.",
      "Anonymizing exports for analytics teams.",
    ],
    howItWorks: [
      { title: "Define", body: "Pick a column or pattern, choose a generator, and configure format/length constraints." },
      { title: "Link", body: "Group related columns into a consistency set so they stay coherent (the same 'Jane Doe' always gets the same email)." },
      { title: "Apply", body: "Run the policy as a job. Output lands in your chosen destination — same DB (in-place), a new schema, or a file export." },
    ],
    examples: [
      { title: "Reversible card numbers", body: "Use FPE on credit_card_number — output keeps the 16-digit format and is reversible only with the deployment SECRET_KEY (the FPE AES-128 key is derived from it via HKDF). Analytics can still join on the masked value." },
      { title: "Consistency", body: "Link customer_email + first_name + last_name in a policy so the same fake identity is reused per row. Hash strategy can optionally mix a consistency-group label into its salt so the same value hashes identically across all linked columns." },
    ],
    gotchas: [
      "FPE derives its AES-128 key from the deployment SECRET_KEY via HKDF. Rotate SECRET_KEY and old FPE ciphertexts can no longer be reversed.",
      "Hash and FPE depend on a stable deployment salt/SECRET_KEY. Reseeding either changes every previously-masked value.",
      "In-place masking is irreversible — always test against a copy first.",
      "FF3-1 needs at least two characters of input; shorter values fall back to a hash for that single column.",
    ],
    demo: "mask-preview",
  },
  {
    slug: "synthetic",
    title: "Synthetic Data Generation",
    short: "Manufactured data that mimics production statistics without containing real PII.",
    icon: Sparkles,
    illustration: "synthetic-loop",
    accent: "--chart-3",
    category: "Generation",
    appRoute: "/projects",
    what: "Where masking transforms existing rows, synthetic generation produces brand-new rows from learned distributions. Use this when you need volume (10x your prod data for load testing) or when you can't pull from prod at all.",
    whenToUse: [
      "Performance/load testing — scale a table without scaling exposure.",
      "Demo environments where prod data can't leave the boundary.",
      "Filling out a referentially-correct toy database for engineers.",
    ],
    howItWorks: [
      { title: "Learn", body: "We profile the source: distributions, FK graphs, cardinalities." },
      { title: "Configure", body: "Pick row counts, density, and per-column generators. Optional: train a model for cross-column joint distributions." },
      { title: "Generate", body: "Run as a job. Output lands in the chosen destination with referential integrity preserved." },
    ],
    examples: [
      { title: "10x load test", body: "Generate 5M synthetic orders from a 500K-row source, with realistic value distributions for unit_price." },
      { title: "Demo seed", body: "Stand up a fresh demo environment with 100 synthetic customers + 500 orders + 1000 transactions, all referentially consistent." },
    ],
    gotchas: [
      "Synthetic data is statistically realistic but not behaviorally realistic — don't use it to test edge-case business logic.",
      "Generation cost scales with row count and column count. Budget 1-2 minutes per million rows for simple schemas.",
    ],
    demo: "none",
  },
  {
    slug: "subsetting",
    title: "Subsetting",
    short: "Pull a referentially-correct slice of a large production database.",
    icon: Layers,
    illustration: "subset-slice",
    accent: "--chart-7",
    category: "Generation",
    appRoute: "/projects",
    what: "Subsetting builds a smaller, internally consistent copy of a database. Specify a seed (e.g., 10,000 specific customers); subsetting walks foreign keys to pull every related row — orders, payments, addresses — so the slice is still queryable end-to-end.",
    whenToUse: [
      "Engineers want dev data that looks like prod but fits on a laptop.",
      "Reproducing a bug — pull just the rows around an affected account.",
      "Sharing a representative slice with a vendor for diagnostics.",
    ],
    howItWorks: [
      { title: "Pick seed", body: "Define the WHERE clause that selects your root rows (e.g., customer_id IN (...) or signup_date > '2025-01-01')." },
      { title: "Walk graph", body: "We follow discovered + manually-asserted foreign keys outward until all referenced rows are pulled." },
      { title: "Mask + export", body: "Apply a masking policy and write the slice to a target DB or files (Parquet/CSV/SQL)." },
    ],
    examples: [
      { title: "Bug repro", body: "Pull the 1,200 rows touching account_id=987 so a developer can reproduce without prod access." },
      { title: "Tenant slice", body: "Multi-tenant DB — pull just tenant_id=abc with all its data for an on-prem customer copy." },
    ],
    gotchas: [
      "Subsetting depends on FK discovery — circular references or unresolved virtual FKs can stall the walk.",
      "Self-referential tables (like org_chart parent_id) can pull in unexpectedly large subsets.",
    ],
    demo: "subset-builder",
  },
  {
    slug: "workflows",
    title: "Workflows",
    short: "Multi-step pipelines that chain discovery, masking, and generation.",
    icon: Workflow,
    illustration: "workflow-graph",
    accent: "--chart-8",
    category: "Orchestration",
    appRoute: "/projects",
    what: "A workflow stitches together steps — discover, then mask, then subset, then export — and runs them as a single unit. Use workflows for repeatable, scheduled operations like nightly test-data refreshes.",
    whenToUse: [
      "Nightly QA refresh: rediscover → mask → push to QA database.",
      "Pre-release: subset production → mask → land in staging.",
      "Post-incident: re-run discovery → flag new PII → notify webhook.",
    ],
    howItWorks: [
      { title: "Compose", body: "Drag steps onto the workflow canvas; configure each one." },
      { title: "Trigger", body: "Run manually, on a schedule, or from a webhook." },
      { title: "Observe", body: "Per-step progress, retries, and logs in the Jobs view." },
    ],
    examples: [
      { title: "Weekly refresh", body: "Cron every Sunday 2am: discover → mask → load into QA. Slack notification on failure." },
      { title: "Bug-triggered", body: "Webhook from PagerDuty triggers a workflow that subsets the affected rows for the on-call." },
    ],
    gotchas: [
      "Only one active execution per workflow at a time — concurrent triggers are queued.",
      "Workflows fail loudly: if step 2 fails, downstream steps don't run. Use retries on transient steps.",
    ],
    demo: "none",
  },
  {
    slug: "jobs",
    title: "Jobs",
    short: "Async execution units — every long-running operation is a job.",
    icon: Zap,
    illustration: "job-pipeline",
    accent: "--chart-1",
    category: "Operations",
    appRoute: "/projects",
    what: "Discovery, masking, synthetic generation, subsetting, workflow runs, and compliance reports all execute as background jobs. Jobs have a status (pending / running / completed / failed / cancelled), progress, checkpoints for resume, and structured logs.",
    whenToUse: [
      "Monitoring an in-flight operation.",
      "Investigating a recent failure or timing regression.",
      "Cancelling a runaway job.",
    ],
    howItWorks: [
      { title: "Enqueue", body: "API call or scheduler hands a task to Celery." },
      { title: "Execute", body: "Workers pick it up; progress is written to the DB every 5 seconds." },
      { title: "Resolve", body: "On success, status flips to completed. On failure, the job moves to the DLQ for inspection and optional replay." },
    ],
    examples: [
      { title: "Cancel a runaway", body: "Click Cancel on a stuck masking job; the worker checks the flag at the next checkpoint and exits cleanly." },
      { title: "DLQ replay", body: "After fixing a bad credential, replay the failed jobs from the dead-letter queue with one click." },
    ],
    gotchas: [
      "Cancel is cooperative — workers exit at the next checkpoint, not instantly.",
      "Jobs in 'pending' for more than 5 minutes usually mean no worker is consuming the queue.",
    ],
    demo: "none",
  },
  {
    slug: "compliance",
    title: "Compliance Reports",
    short: "Audit-ready snapshots of privacy posture, coverage, and policy history.",
    icon: ClipboardCheck,
    illustration: "report-doc",
    accent: "--chart-4",
    category: "Operations",
    appRoute: "/projects",
    what: "Compliance reports produce signed, dated PDFs (and JSON) summarizing a project's privacy posture: sensitive columns, masking coverage, policy diffs, and recent job activity. Maps directly to GDPR, HIPAA, and SOC 2 evidence requests.",
    whenToUse: [
      "Quarterly compliance review.",
      "Auditor evidence requests.",
      "Pre/post comparison after a policy change.",
    ],
    howItWorks: [
      { title: "Generate", body: "Click 'New Report', pick a regulation framework, and submit. Generation runs as a job." },
      { title: "Sign", body: "The PDF includes a hash and timestamp signed by Synthia for tamper detection." },
      { title: "Archive", body: "Reports are versioned and immutable. Old reports remain even if the underlying data changes." },
    ],
    examples: [
      { title: "GDPR audit", body: "Generate a GDPR report covering Q3 — includes the count of right-to-erasure requests fulfilled (via masking)." },
      { title: "Before/after", body: "Compare two reports to show an auditor exactly which columns got newly covered between releases." },
    ],
    gotchas: [
      "Reports are point-in-time. Coverage can drop after the report is signed if rules are disabled.",
      "PDF generation can take 30-60s for large projects — the report shows up in the list once the job completes.",
    ],
    demo: "none",
  },
  {
    slug: "ephemeral",
    title: "Ephemeral Environments",
    short: "Short-lived, masked database copies provisioned on demand.",
    icon: FlaskConical,
    illustration: "ephemeral-bubble",
    accent: "--chart-7",
    category: "Generation",
    appRoute: "/projects",
    what: "Ephemeral environments spin up an isolated, pre-masked database for a fixed window (default 4 hours), then automatically tear down. Used for ad-hoc experiments, training, or one-off vendor access.",
    whenToUse: [
      "A new hire needs a sandbox for their first week.",
      "A vendor needs short-term access to investigate a bug.",
      "An ML team wants a temporary working copy for an experiment.",
    ],
    howItWorks: [
      { title: "Request", body: "Pick a source connection, a masking policy, and a TTL." },
      { title: "Provision", body: "We stand up a fresh DB, copy the schema, apply the policy, and load the data." },
      { title: "Expire", body: "At TTL, the database is destroyed and credentials revoked." },
    ],
    examples: [
      { title: "Onboarding sandbox", body: "Provision a 7-day environment for a new engineer with masked production data." },
      { title: "Vendor diagnosis", body: "Spin up a 24-hour copy with the buggy account's data for a vendor support call." },
    ],
    gotchas: [
      "Ephemeral environments charge against the same DB host budget as your other connections — large copies count.",
      "Don't put critical work in an ephemeral environment. It will be destroyed.",
    ],
    demo: "none",
  },
  {
    slug: "generator-presets",
    title: "Generator Presets",
    short: "Reusable, pre-configured generators shared across policies.",
    icon: TestTube,
    illustration: "preset-stamp",
    accent: "--chart-2",
    category: "Generation",
    appRoute: "/generator-presets",
    what: "A generator preset bundles a generator with its config — e.g., 'US Adult Birthdate' = the faker_date generator configured for ages 21–80. Apply a preset to many rules across many policies in one click; updates propagate automatically.",
    whenToUse: [
      "Standardizing how 'US phone numbers' look across every project.",
      "Reusing a complex format-preserving config (e.g., specific token alphabet) without re-typing it everywhere.",
    ],
    howItWorks: [
      { title: "Author", body: "Create a preset once with a name, generator, and config payload." },
      { title: "Reference", body: "In any masking rule, pick a preset instead of configuring inline." },
      { title: "Update once", body: "Change the preset → every linked rule picks up the new behavior on the next job." },
    ],
    examples: [
      { title: "Adult age", body: "Preset 'us_adult_birthdate' (faker_date, range 1944-01-01 to 2004-12-31) used by 14 masking rules across 8 projects." },
      { title: "Synthetic SSN", body: "Preset 'fake_ssn_xxx_xx_nnnn' that formats SSNs but uses an invalid prefix so no real values can match." },
    ],
    gotchas: [
      "Deleting a preset doesn't delete the rules referencing it — they keep their last-known config (preset_id becomes NULL).",
    ],
    demo: "none",
  },
  {
    slug: "sensitivity-rules",
    title: "Sensitivity Rules",
    short: "Custom patterns that extend the built-in PII classifier.",
    icon: ShieldAlert,
    illustration: "rule-pattern",
    accent: "--chart-6",
    category: "Privacy",
    appRoute: "/sensitivity-rules",
    what: "Sensitivity rules let you teach discovery about your organization's specific patterns: internal employee IDs, partner account numbers, custom medical codes. Each rule is a regex + a target PII type + a confidence score.",
    whenToUse: [
      "Discovery isn't catching your internal account format.",
      "You have a domain-specific identifier (e.g., HL7 ID) that needs to be flagged.",
    ],
    howItWorks: [
      { title: "Define", body: "Name, regex, PII type to assign, base confidence." },
      { title: "Activate", body: "Rules are applied on the next discovery run." },
      { title: "Iterate", body: "Tune confidence based on false positives — too aggressive matches noise, too conservative misses data." },
    ],
    examples: [
      { title: "Employee ID", body: "Regex /^EMP-\\d{6}$/ → PII type 'employee_id', confidence 0.95." },
      { title: "Medical record", body: "Regex /^MRN\\d{8}$/ → PII type 'medical_record_number'." },
    ],
    gotchas: [
      "Overly broad regexes can flood discovery with false positives. Test the regex on sample data first.",
      "Rules apply globally — they affect every project's next discovery run.",
    ],
    demo: "none",
  },
  {
    slug: "webhooks",
    title: "Webhooks",
    short: "Outbound HTTP notifications when jobs, workflows, or scans complete.",
    icon: Webhook,
    illustration: "webhook-fan",
    accent: "--chart-3",
    category: "Operations",
    appRoute: "/projects",
    what: "Webhooks push events to your systems. Configure a URL, pick which events to subscribe to (job.completed, job.failed, workflow.failed, discovery.drift), and Synthia POSTs a signed JSON payload whenever they fire.",
    whenToUse: [
      "Slack/PagerDuty notifications on failure.",
      "Triggering downstream pipelines (e.g., Airflow) on success.",
      "Updating a status board.",
    ],
    howItWorks: [
      { title: "Register", body: "URL + secret + event subscriptions. We display the secret once; you store it in your receiver for HMAC verification." },
      { title: "Deliver", body: "On event, we POST a signed JSON envelope. Receiver verifies the signature." },
      { title: "Retry", body: "Failed deliveries are retried with exponential backoff up to 1 hour, then dead-lettered." },
    ],
    examples: [
      { title: "Slack alert", body: "On job.failed, POST to a Slack-incoming-webhook URL with the project + job_type + error." },
      { title: "Airflow trigger", body: "On workflow.completed, POST to Airflow REST API to kick off the next DAG." },
    ],
    gotchas: [
      "Your receiver MUST verify the HMAC signature — anyone can hit a webhook URL otherwise.",
      "Retries can deliver out-of-order. Treat delivery as at-least-once and idempotent on your side.",
    ],
    demo: "none",
  },
  {
    slug: "admin",
    title: "Admin",
    short: "Users, roles, audit log, and platform-wide settings.",
    icon: Settings,
    illustration: "admin-keys",
    accent: "--chart-8",
    category: "Admin",
    appRoute: "/admin",
    what: "The admin area covers identity, RBAC, audit trail, and global platform configuration. Only users with the admin role can access it.",
    whenToUse: [
      "Adding or removing users.",
      "Reviewing the audit log after a security incident.",
      "Configuring SSO, retention policies, or platform-wide guardrails.",
    ],
    howItWorks: [
      { title: "Identity", body: "Users sign in via SSO. Local accounts exist for break-glass." },
      { title: "Roles", body: "Project-scoped roles: viewer / editor / admin. Plus a platform admin role." },
      { title: "Audit", body: "Every privileged action writes to the immutable audit log with actor, target, and timestamp." },
    ],
    examples: [
      { title: "Quarterly review", body: "Export the audit log for Q3, filter to 'role.granted' events for the compliance team." },
      { title: "Offboarding", body: "Remove a leaving employee's user — all their project access is revoked atomically." },
    ],
    gotchas: [
      "Removing the last platform admin will lock you out. Always keep ≥2.",
      "Audit log is append-only — you can't redact entries, only export them.",
    ],
    demo: "none",
  },
];

// ── FAQ ────────────────────────────────────────────────────────────────────────

export type FaqCategory = "Getting Started" | "Security & Privacy" | "Operations" | "Billing & Limits" | "Troubleshooting";

export interface FaqEntry {
  category: FaqCategory;
  question: string;
  answer: string;
}

export const FAQ_ENTRIES: FaqEntry[] = [
  // Getting Started
  {
    category: "Getting Started",
    question: "What's the fastest way to evaluate Synthia?",
    answer:
      "Walk the onboarding flow — it has you create a project, add a Postgres or MySQL connection, run discovery, and build your first masking policy in under 10 minutes. Use a non-production database for the trial.",
  },
  {
    category: "Getting Started",
    question: "Do I need to install anything on my database?",
    answer:
      "No. Synthia connects with a standard read-only role plus (optionally) a write target for synthetic-data destinations. No agent, no extension, no logical replication needed.",
  },
  {
    category: "Getting Started",
    question: "Which data sources are supported?",
    answer:
      "Postgres, MySQL, SQL Server, Oracle, Snowflake, Redshift, Databricks, DB2, and MongoDB. File sources (CSV / Parquet / JSON) work via the file-source flow.",
  },
  // Security & Privacy
  {
    category: "Security & Privacy",
    question: "Where are credentials stored?",
    answer:
      "Connection credentials are encrypted with Fernet (AES-128 CBC + HMAC-SHA256) using a per-deployment key that lives outside the database. The plaintext never leaves memory once written.",
  },
  {
    category: "Security & Privacy",
    question: "Does production data ever leave my network?",
    answer:
      "Only if you configure an external destination. By default Synthia reads sample rows for discovery and writes masked output back to a destination you control. No data is sent to Anthropic, Ameritas, or any third party.",
  },
  {
    category: "Security & Privacy",
    question: "Can I reverse a masking operation?",
    answer:
      "Only if you used a reversible generator (format-preserving encryption or tokenization with a stored key). Redact, hash, and faker_replace are one-way.",
  },
  {
    category: "Security & Privacy",
    question: "How is the audit log protected against tampering?",
    answer:
      "Audit entries are append-only at the application layer and the DB role used by the API cannot DELETE from audit_log. Compliance reports are signed with a hash so post-export tampering is detectable.",
  },
  // Operations
  {
    category: "Operations",
    question: "How do I monitor a long-running job?",
    answer:
      "Open Jobs from the project sidebar — every job has live progress, started_at / completed_at, and a structured log tail. You'll also get a notification when it finishes.",
  },
  {
    category: "Operations",
    question: "Can I cancel a running job?",
    answer:
      "Yes. Cancel is cooperative: the worker checks the cancel flag at the next checkpoint (every ~5s) and exits cleanly. Any data already written is left in place.",
  },
  {
    category: "Operations",
    question: "Why is my job stuck in 'pending'?",
    answer:
      "Usually no Celery worker is consuming the queue. Check that the worker container is running and connected to Redis. The Pipeline Health tile on the dashboard surfaces stuck queues automatically.",
  },
  {
    category: "Operations",
    question: "How often should I re-run discovery?",
    answer:
      "Run it after any schema change, and at minimum monthly to catch drift. The dashboard's 'stale connections' insight will tell you which connections haven't been re-scanned in 14+ days.",
  },
  // Billing & Limits
  {
    category: "Billing & Limits",
    question: "How many projects can I create?",
    answer:
      "Internal Ameritas deployments are unlimited. External tenants follow their contract tier. Contact your platform admin if you hit a soft limit.",
  },
  {
    category: "Billing & Limits",
    question: "Are there row-count limits on masking jobs?",
    answer:
      "There's no hard cap, but jobs over 100M rows are best run during off-hours and broken into chunked workflows. The performance tile on the project dashboard shows row throughput.",
  },
  // Troubleshooting
  {
    category: "Troubleshooting",
    question: "Discovery is mis-classifying a column. How do I fix it?",
    answer:
      "Open the column in the Privacy Hub and override the PII type. Overrides persist across re-scans. If the same false positive happens across many tables, add a sensitivity rule to teach the classifier.",
  },
  {
    category: "Troubleshooting",
    question: "My webhook isn't firing.",
    answer:
      "Three things to check: (1) the event type is in your subscription list, (2) the receiver returns 2xx within 10 seconds, (3) the HMAC signature verifies on your side. The webhooks page shows recent delivery attempts and the dead-letter queue.",
  },
  {
    category: "Troubleshooting",
    question: "My synthetic data violates a foreign-key constraint.",
    answer:
      "This means the FK wasn't discovered or asserted. Open the Discovery → Relationships view and add the missing FK as a virtual relationship. Re-run synthetic generation and the new constraint will be honored.",
  },
];

// ── Onboarding ─────────────────────────────────────────────────────────────────

export interface OnboardingStep {
  n: number;
  title: string;
  body: string;
  icon: LucideIcon;
  illustration: IllustrationKind;
  cta?: { label: string; href: string };
  details: string[];
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    n: 1,
    title: "Welcome to Synthia",
    body: "Synthia is an AI-powered Test Data Management platform. It classifies sensitive data, masks it safely, and generates realistic test data — all without copying real production data to anyone who shouldn't have it.",
    icon: Globe,
    illustration: "shield-network",
    details: [
      "Read-only by default. We never write to your source unless you explicitly configure a destination.",
      "Every operation is auditable. Every action writes to an immutable audit log.",
      "Built for enterprise. RBAC, SSO, signed compliance reports.",
    ],
  },
  {
    n: 2,
    title: "Create your first project",
    body: "A project is a workspace that holds your connections, masking policies, and run history. Group projects by application or environment.",
    icon: Boxes,
    illustration: "project-tree",
    cta: { label: "Create a project", href: "/projects" },
    details: [
      "Give it a clear name like 'Customer Service — Production'.",
      "Add an environment tag (production, staging, dev) so dashboards can filter on it.",
      "You can invite collaborators later with viewer / editor / admin roles.",
    ],
  },
  {
    n: 3,
    title: "Connect a data source",
    body: "Add a connection to the database you want to work with. Use a read-only role for safety. Synthia tests the connection before saving the credentials, then encrypts them at rest.",
    icon: Database,
    illustration: "data-flow",
    details: [
      "Supports Postgres, MySQL, SQL Server, Oracle, Snowflake, Redshift, Databricks, DB2, MongoDB.",
      "Credentials are encrypted with Fernet — Synthia never displays them back after entry.",
      "A 'connection test' is a TCP+auth handshake. Permission errors surface on the first discovery run.",
    ],
  },
  {
    n: 4,
    title: "Run discovery",
    body: "Discovery samples your tables and classifies every column. Sensitive columns get a PII type and confidence score — the input for every downstream privacy decision.",
    icon: FileSearch,
    illustration: "scanner",
    details: [
      "Sample size defaults to 1,000 rows per table — typically classifies in under a minute for 200-table sources.",
      "Low-confidence calls are flagged 'needs_review'. Confirm or override them in the Privacy Hub.",
      "Re-run after any schema change. Discovery drift is surfaced on the dashboard automatically.",
    ],
  },
  {
    n: 5,
    title: "Build a masking policy",
    body: "Open the Privacy Hub to see your unprotected sensitive columns. Pick a recommended generator for each and bundle them into a policy.",
    icon: Lock,
    illustration: "mask-reveal",
    details: [
      "Synthia recommends the right generator per PII type — faker_replace for emails, format-preserving for credit cards, etc.",
      "Link related columns (first_name + last_name + email) so the same fake identity is reused per row.",
      "Save the policy as the project default to use it for every future job.",
    ],
  },
  {
    n: 6,
    title: "Run your first masking job",
    body: "Pick the policy you built, pick a destination (same DB / new schema / file export), and run it. Watch progress in the Jobs view; you'll get a notification when it's done.",
    icon: Zap,
    illustration: "job-pipeline",
    details: [
      "Always run against a copy before in-place masking. In-place is irreversible.",
      "Jobs can be cancelled at any checkpoint — you won't corrupt half-masked tables.",
      "On failure, the job moves to the dead-letter queue. Fix the cause and replay with one click.",
    ],
  },
  {
    n: 7,
    title: "Explore from here",
    body: "You've masked your first dataset. From here, explore synthetic generation, subsetting, workflows for repeatable runs, and webhooks for downstream integration.",
    icon: Sparkles,
    illustration: "synthetic-loop",
    cta: { label: "Open the dashboard", href: "/" },
    details: [
      "Set up a nightly workflow to refresh your QA database automatically.",
      "Subset prod down to a laptop-sized dev environment for engineers.",
      "Generate a compliance report once per quarter as auditor-ready evidence.",
    ],
  },
];

// ── Lookup helpers ─────────────────────────────────────────────────────────────

export function getTopic(slug: string): HelpTopic | undefined {
  return HELP_TOPICS.find((t) => t.slug === slug);
}

export function topicCategories(): Array<{ name: HelpTopic["category"]; topics: HelpTopic[] }> {
  const order: HelpTopic["category"][] = [
    "Core",
    "Privacy",
    "Generation",
    "Orchestration",
    "Operations",
    "Admin",
  ];
  return order.map((name) => ({ name, topics: HELP_TOPICS.filter((t) => t.category === name) }));
}

export function faqCategories(): FaqCategory[] {
  const seen = new Set<FaqCategory>();
  const order: FaqCategory[] = [];
  for (const e of FAQ_ENTRIES) {
    if (!seen.has(e.category)) {
      seen.add(e.category);
      order.push(e.category);
    }
  }
  return order;
}

// HelpIcon mapping for navigation (not from lucide list above — kept separate
// so the consumer can avoid importing the full TOPIC array just for an icon).
export { Activity, ClipboardCheck, Eye, HardDrive, ShieldCheck };
