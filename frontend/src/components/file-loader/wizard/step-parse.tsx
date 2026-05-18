"use client";

import { useState } from "react";
import { AlertTriangle, Loader2, Upload } from "lucide-react";

import { Select } from "@/components/common/select";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

import { uploadFile } from "../upload-file";
import { LayoutConditionsEditor } from "./layout-conditions-editor";
import type {
  FileSchemaDetail,
  LayoutCondition,
  SplitStrategy,
  WizardSource,
} from "../types";

interface StepParseProps {
  projectId: string;
  source: WizardSource;
  onParsed: (schema: FileSchemaDetail) => void;
  onBack: () => void;
}

/**
 * Drives the chosen source endpoint. The copybook variant exposes the
 * split-strategy radio + an inline conditions editor for multi-record
 * layouts; the dictionary variant exposes target format + encoding;
 * manual and from-discovery hand off to their own minimal forms.
 */
export function StepParse(props: StepParseProps) {
  if (props.source === "upload-copybook") return <CopybookFlow {...props} />;
  if (props.source === "upload-dictionary") return <DictionaryFlow {...props} />;
  if (props.source === "manual") return <ManualFlow {...props} />;
  return <DiscoveryFlow {...props} />;
}

// ── Copybook ────────────────────────────────────────────────────────

function CopybookFlow({ projectId, onParsed, onBack }: StepParseProps) {
  const [file, setFile] = useState<File | null>(null);
  const [strategy, setStrategy] = useState<SplitStrategy>("single");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<FileSchemaDetail | null>(null);
  const [conditions, setConditions] = useState<Record<string, LayoutCondition[]>>({});

  const doUpload = async () => {
    if (!file) {
      setError("Pick a copybook file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await uploadFile<FileSchemaDetail>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas/upload-copybook`,
        { file, query: { split_strategy: strategy } },
      );
      if (!result) throw new Error("Empty response");
      setParsed(result);
      // Initialize empty conditions for each variant so the editor renders rows.
      const initial: Record<string, LayoutCondition[]> = {};
      for (const v of result.layout_variants ?? []) {
        initial[v.name] = v.conditions ?? [];
      }
      setConditions(initial);
    } catch (e) {
      setError((e as Error).message || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const continueWizard = async () => {
    if (!parsed) return;
    // If multi-variant, push conditions before moving on.
    if (parsed.layout_variants.length > 0) {
      const incomplete = parsed.layout_variants.filter(
        (v) => (conditions[v.name] ?? []).length === 0,
      );
      if (incomplete.length > 0) {
        const ok = window.confirm(
          `${incomplete.length} variant(s) have no discriminator conditions yet. Continue anyway? You can fix this later, but the preview won't be able to assign rows to them.`,
        );
        if (!ok) return;
      }
      // PATCH via raw fetch — the api{} helper only exposes get/post/put/del.
      setBusy(true);
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/projects/${projectId}/synthetic/file-schemas/${parsed.id}/layout-variants`,
          {
            method: "PATCH",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              variants: parsed.layout_variants.map((v) => ({
                variant_name: v.name,
                conditions: conditions[v.name] ?? [],
              })),
            }),
          },
        );
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(
            (detail as { detail?: { detail?: string } }).detail?.detail ||
              `HTTP ${res.status}`,
          );
        }
        const updated = (await res.json()) as FileSchemaDetail;
        onParsed(updated);
      } catch (e) {
        toast.error(`Conditions update failed: ${(e as Error).message}`);
      } finally {
        setBusy(false);
      }
    } else {
      onParsed(parsed);
    }
  };

  return (
    <div className="space-y-4">
      <FilePicker
        accept=".cpy,.cob,.txt,.cbl"
        onPick={setFile}
        label="Copybook (.cpy, .cob)"
        selected={file}
      />

      <div>
        <p className="text-xs font-medium text-foreground">Multi-record handling</p>
        <p className="text-[11px] text-muted-foreground">
          Choose how to interpret copybooks with multiple 01-levels or REDEFINES.
        </p>
        <div className="mt-1 flex gap-3">
          {(
            [
              ["single", "Single flat layout"],
              ["split_01", "One layout per 01-level"],
              ["split_redefine", "One layout per REDEFINES branch"],
            ] as [SplitStrategy, string][]
          ).map(([id, label]) => (
            <label key={id} className="flex items-center gap-1 text-xs">
              <input
                type="radio"
                name="split-strategy"
                value={id}
                checked={strategy === id}
                onChange={() => setStrategy(id)}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {parsed && (
        <ParsedSummary
          schema={parsed}
          conditionsByVariant={conditions}
          onConditionsChange={(name, conds) =>
            setConditions((p) => ({ ...p, [name]: conds }))
          }
        />
      )}

      <FooterButtons
        onBack={onBack}
        primary={parsed ? "Next" : "Parse copybook"}
        primaryBusy={busy}
        onPrimary={parsed ? continueWizard : doUpload}
      />
    </div>
  );
}

// ── Dictionary ──────────────────────────────────────────────────────

function DictionaryFlow({ projectId, onParsed, onBack }: StepParseProps) {
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState("csv");
  const [encoding, setEncoding] = useState("utf8");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const doUpload = async () => {
    if (!file) {
      setError("Pick an .xlsx file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await uploadFile<FileSchemaDetail>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas/upload-dictionary`,
        { file, query: { target_format: format, target_encoding: encoding } },
      );
      if (!result) throw new Error("Empty response");
      onParsed(result);
    } catch (e) {
      setError((e as Error).message || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <FilePicker
        accept=".xlsx,.xls"
        onPick={setFile}
        label="Data dictionary (.xlsx)"
        selected={file}
      />

      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs">
          <span className="block text-muted-foreground">Target format</span>
          <Select value={format} onChange={(e) => setFormat(e.target.value)} fullWidth>
            <option value="csv">CSV</option>
            <option value="fixed_width">Fixed-width</option>
            <option value="vsam_fixed">VSAM (fixed)</option>
            <option value="vsam_variable">VSAM (variable, RDW)</option>
            <option value="parquet">Parquet</option>
            <option value="orc">ORC</option>
          </Select>
        </label>
        <label className="text-xs">
          <span className="block text-muted-foreground">Target encoding</span>
          <Select value={encoding} onChange={(e) => setEncoding(e.target.value)} fullWidth>
            <option value="ascii">ASCII</option>
            <option value="utf8">UTF-8</option>
            <option value="ebcdic_cp037">EBCDIC cp037</option>
            <option value="ebcdic_cp1140">EBCDIC cp1140 (Euro)</option>
          </Select>
        </label>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      <FooterButtons
        onBack={onBack}
        primary="Parse dictionary"
        primaryBusy={busy}
        onPrimary={doUpload}
      />
    </div>
  );
}

// ── Manual ──────────────────────────────────────────────────────────

function ManualFlow({ projectId, onParsed, onBack }: StepParseProps) {
  const [name, setName] = useState("");
  const [format, setFormat] = useState("csv");
  const [encoding, setEncoding] = useState("utf8");
  const [rows, setRows] = useState<
    { name: string; data_type: string; length: number; nullable: boolean }[]
  >([{ name: "ID", data_type: "numeric", length: 8, nullable: false }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) {
      setError("Schema name is required.");
      return;
    }
    if (rows.length === 0) {
      setError("At least one field is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<FileSchemaDetail>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas/manual`,
        {
          name,
          file_format: format,
          encoding,
          fields: rows.map((r) => ({
            name: r.name,
            data_type: r.data_type,
            length: r.length,
            nullable: r.nullable,
          })),
        },
      );
      onParsed(result);
    } catch (e) {
      setError((e as Error).message || "Save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        <label className="col-span-3 text-xs sm:col-span-1">
          <span className="block text-muted-foreground">Schema name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
            placeholder="e.g. CUSTOMERS"
          />
        </label>
        <label className="text-xs">
          <span className="block text-muted-foreground">Format</span>
          <Select value={format} onChange={(e) => setFormat(e.target.value)} fullWidth>
            <option value="csv">CSV</option>
            <option value="fixed_width">Fixed-width</option>
            <option value="vsam_fixed">VSAM (fixed)</option>
            <option value="parquet">Parquet</option>
          </Select>
        </label>
        <label className="text-xs">
          <span className="block text-muted-foreground">Encoding</span>
          <Select value={encoding} onChange={(e) => setEncoding(e.target.value)} fullWidth>
            <option value="ascii">ASCII</option>
            <option value="utf8">UTF-8</option>
            <option value="ebcdic_cp037">EBCDIC cp037</option>
          </Select>
        </label>
      </div>

      <div className="rounded-md border border-border bg-card">
        <table className="w-full text-xs">
          <thead className="bg-muted/30 text-left">
            <tr>
              <th className="px-2 py-1.5 font-medium">Name</th>
              <th className="px-2 py-1.5 font-medium">Type</th>
              <th className="px-2 py-1.5 font-medium">Length</th>
              <th className="px-2 py-1.5 font-medium">Nullable</th>
              <th className="w-12" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-border">
                <td className="px-2 py-1">
                  <input
                    value={r.name}
                    onChange={(e) =>
                      setRows((p) => p.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
                    }
                    className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                  />
                </td>
                <td className="px-2 py-1">
                  <Select
                    value={r.data_type}
                    onChange={(e) =>
                      setRows((p) =>
                        p.map((x, j) => (j === i ? { ...x, data_type: e.target.value } : x)),
                      )
                    }
                    fullWidth={false}
                    className="min-w-[140px]"
                  >
                    <option value="alphanumeric">alphanumeric</option>
                    <option value="numeric">numeric</option>
                    <option value="decimal">decimal</option>
                    <option value="binary">binary</option>
                    <option value="packed_decimal">packed_decimal</option>
                  </Select>
                </td>
                <td className="px-2 py-1">
                  <input
                    type="number"
                    min={1}
                    value={r.length}
                    onChange={(e) =>
                      setRows((p) =>
                        p.map((x, j) =>
                          j === i ? { ...x, length: Math.max(1, parseInt(e.target.value, 10) || 1) } : x,
                        ),
                      )
                    }
                    className="w-20 rounded border border-input bg-background px-2 py-1 text-xs"
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="checkbox"
                    checked={r.nullable}
                    onChange={(e) =>
                      setRows((p) =>
                        p.map((x, j) => (j === i ? { ...x, nullable: e.target.checked } : x)),
                      )
                    }
                  />
                </td>
                <td className="px-2 py-1 text-right">
                  <button
                    type="button"
                    onClick={() => setRows((p) => p.filter((_, j) => j !== i))}
                    className="text-[10px] text-muted-foreground hover:text-destructive"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-border bg-muted/20 px-2 py-1.5 text-right">
          <button
            type="button"
            onClick={() =>
              setRows((p) => [
                ...p,
                { name: `FIELD_${p.length + 1}`, data_type: "alphanumeric", length: 10, nullable: true },
              ])
            }
            className="text-[11px] text-primary hover:underline"
          >
            + Add field
          </button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      <FooterButtons
        onBack={onBack}
        primary="Save schema"
        primaryBusy={busy}
        onPrimary={submit}
      />
    </div>
  );
}

// ── Discovery ───────────────────────────────────────────────────────

function DiscoveryFlow({ projectId, onParsed, onBack }: StepParseProps) {
  const [tableName, setTableName] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [format, setFormat] = useState("csv");
  const [encoding, setEncoding] = useState("utf8");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!connectionId || !tableName.trim()) {
      setError("Connection id and table name are required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<FileSchemaDetail>(
        `/api/v1/projects/${projectId}/synthetic/file-schemas/from-discovery`,
        {
          table_name: tableName,
          connection_id: connectionId,
          target_format: format,
          target_encoding: encoding,
        },
      );
      onParsed(result);
    } catch (e) {
      setError((e as Error).message || "Derive failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 text-xs">
      <p className="text-muted-foreground">
        Paste a connection id (find it in the Connections page URL) and the name of a
        discovered table to derive a file schema from it.
      </p>
      <input
        value={connectionId}
        onChange={(e) => setConnectionId(e.target.value)}
        placeholder="connection_id (UUID)"
        className="w-full rounded-md border border-input bg-background px-2 py-1.5"
      />
      <input
        value={tableName}
        onChange={(e) => setTableName(e.target.value)}
        placeholder="table_name"
        className="w-full rounded-md border border-input bg-background px-2 py-1.5"
      />
      <div className="grid grid-cols-2 gap-2">
        <Select value={format} onChange={(e) => setFormat(e.target.value)} fullWidth>
          <option value="csv">CSV</option>
          <option value="fixed_width">Fixed-width</option>
          <option value="vsam_fixed">VSAM (fixed)</option>
          <option value="parquet">Parquet</option>
        </Select>
        <Select value={encoding} onChange={(e) => setEncoding(e.target.value)} fullWidth>
          <option value="ascii">ASCII</option>
          <option value="utf8">UTF-8</option>
          <option value="ebcdic_cp037">EBCDIC cp037</option>
        </Select>
      </div>
      {error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-destructive">
          {error}
        </p>
      )}
      <FooterButtons
        onBack={onBack}
        primary="Derive schema"
        primaryBusy={busy}
        onPrimary={submit}
      />
    </div>
  );
}

// ── Shared helpers ─────────────────────────────────────────────────

function FilePicker({
  accept,
  onPick,
  label,
  selected,
}: {
  accept: string;
  onPick: (f: File | null) => void;
  label: string;
  selected: File | null;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-input bg-background px-3 py-3 text-xs hover:border-primary">
      <Upload className="h-4 w-4 text-muted-foreground" />
      <div className="flex-1">
        <p className="font-medium text-foreground">{label}</p>
        <p className="text-[11px] text-muted-foreground">
          {selected ? `${selected.name} (${selected.size} bytes)` : "Click to choose a file"}
        </p>
      </div>
      <input
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

function FooterButtons({
  onBack,
  onPrimary,
  primary,
  primaryBusy,
}: {
  onBack: () => void;
  onPrimary: () => void;
  primary: string;
  primaryBusy?: boolean;
}) {
  return (
    <div className="flex justify-between pt-2">
      <button
        type="button"
        onClick={onBack}
        className="rounded-md border border-input bg-background px-3 py-1.5 text-xs hover:bg-muted/40"
      >
        Back
      </button>
      <button
        type="button"
        onClick={onPrimary}
        disabled={primaryBusy}
        className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
      >
        {primaryBusy && <Loader2 className="h-3 w-3 animate-spin" />}
        {primary}
      </button>
    </div>
  );
}

function ParsedSummary({
  schema,
  conditionsByVariant,
  onConditionsChange,
}: {
  schema: FileSchemaDetail;
  conditionsByVariant: Record<string, LayoutCondition[]>;
  onConditionsChange: (name: string, conds: LayoutCondition[]) => void;
}) {
  const totalVariants = schema.layout_variants.length;
  return (
    <div className="rounded-md border border-border bg-muted/10 p-3 text-xs">
      <p className="font-medium text-foreground">
        Parsed {schema.field_count} field{schema.field_count === 1 ? "" : "s"} • record
        length {schema.record_length} bytes
        {totalVariants > 0 && (
          <>
            {" "}
            • {totalVariants} additional layout{totalVariants === 1 ? "" : "s"}
          </>
        )}
      </p>
      {totalVariants > 0 && (
        <div className="mt-2 space-y-2">
          <p className="flex items-center gap-1 text-[11px] text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-3 w-3" />
            Set discriminator conditions for each variant — a record uses a variant when
            ALL of its conditions match.
          </p>
          {schema.layout_variants.map((v) => (
            <LayoutConditionsEditor
              key={v.name}
              variantName={v.name}
              baseFields={schema.fields}
              conditions={conditionsByVariant[v.name] ?? []}
              onChange={(conds) => onConditionsChange(v.name, conds)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
