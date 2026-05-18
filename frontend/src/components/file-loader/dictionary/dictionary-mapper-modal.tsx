"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Plus, X } from "lucide-react";

import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { Select } from "@/components/common/select";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

import { TransformPill, type TransformSpec } from "./transform-pill";
import type { FileSchemaDetail, FileSchemaSummary } from "../types";

interface DictionaryMapperModalProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
  /** When set, opens preselecting this schema as the source for a NEW derive. */
  sourceSchemaId?: string;
  /**
   * When set, opens re-editing this existing derived schema in place.
   * Takes precedence over ``sourceSchemaId`` — the source comes from
   * ``metadata.derived_from`` on the persisted row, not the prop. Save
   * calls PATCH instead of POST so the existing schema id is preserved
   * (any file-set / rule that references the old id stays valid).
   */
  derivedSchemaId?: string;
}

interface MappingRow {
  target_field: string;
  source_field: string | null;
  constant: string | null;
  transforms: TransformSpec[];
}

interface ExistingMappingResponse {
  derived_from: string | null;
  derived_from_name: string | null;
  mappings: MappingRow[];
  target_name?: string | null;
  target_format?: string | null;
  target_encoding?: string | null;
  target_output_filename?: string | null;
}

/**
 * Two-tree dictionary mapper modeled on Altova MapForce / Talend Data
 * Mapper. Source fields (left) are mapped to target fields (right);
 * each row stores a transform chain that's evaluated by the backend
 * derive endpoint when the new schema is saved.
 */
export function DictionaryMapperModal({
  projectId,
  open,
  onClose,
  sourceSchemaId,
  derivedSchemaId,
}: DictionaryMapperModalProps) {
  const isEditMode = !!derivedSchemaId;

  const [schemas, setSchemas] = useState<FileSchemaSummary[]>([]);
  const [sourceId, setSourceId] = useState<string | null>(sourceSchemaId ?? null);
  const [sourceDetail, setSourceDetail] = useState<FileSchemaDetail | null>(null);
  const [targetName, setTargetName] = useState("");
  const [targetFormat, setTargetFormat] = useState("csv");
  const [targetEncoding, setTargetEncoding] = useState("utf8");
  // Empty string means "no override"; round-tripped to null on save so the
  // backend stores ``NULL`` rather than the literal empty string.
  const [targetOutputFilename, setTargetOutputFilename] = useState("");
  const [rows, setRows] = useState<MappingRow[]>([]);
  // ``hydrating`` covers both schema-list load + (in edit mode) the
  // existing-mapping fetch. While true the source dropdown is disabled
  // because changing source mid-load would race with the field hydration.
  const [hydrating, setHydrating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Tracks whether the user has manually edited rows after hydration so
  // we don't blow away their edits when the source-detail effect re-runs.
  const [hydratedForDerived, setHydratedForDerived] = useState<string | null>(null);

  // Reset transient state every time the modal closes — otherwise the
  // next open inherits stale rows + targetName from the previous edit.
  useEffect(() => {
    if (open) return;
    setSourceId(sourceSchemaId ?? null);
    setSourceDetail(null);
    setTargetName("");
    setTargetFormat("csv");
    setTargetEncoding("utf8");
    setTargetOutputFilename("");
    setRows([]);
    setError(null);
    setHydratedForDerived(null);
  }, [open, sourceSchemaId]);

  // Load schema list on open.
  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const list = await api.get<FileSchemaSummary[]>(
          `/api/v1/projects/${projectId}/synthetic/file-schemas`,
        );
        setSchemas(list);
        // Don't auto-pick a source when we're about to hydrate an
        // existing derived schema — that path sets sourceId from the
        // persisted ``derived_from`` instead.
        if (!isEditMode && !sourceId && list.length > 0) {
          setSourceId(list[0].id);
        }
      } catch (e) {
        setError((e as Error).message || "Failed to load schemas");
      }
    })();
  }, [open, projectId, sourceId, isEditMode]);

  // Edit mode: hydrate from the existing derived schema before the
  // source-detail effect runs, so seeding doesn't clobber the saved rows.
  useEffect(() => {
    if (!open || !derivedSchemaId) return;
    if (hydratedForDerived === derivedSchemaId) return;
    setHydrating(true);
    setError(null);
    (async () => {
      try {
        const existing = await api.get<ExistingMappingResponse>(
          `/api/v1/projects/${projectId}/file-schemas/${derivedSchemaId}/mappings`,
        );
        if (!existing.derived_from) {
          throw new Error(
            "This schema was not produced by the dictionary mapper, so it can't be re-edited here.",
          );
        }
        setSourceId(existing.derived_from);
        setTargetName(existing.target_name ?? "");
        setTargetFormat(existing.target_format ?? "csv");
        setTargetEncoding(existing.target_encoding ?? "utf8");
        setTargetOutputFilename(existing.target_output_filename ?? "");
        setRows(
          existing.mappings.map((m) => ({
            target_field: m.target_field,
            source_field: m.source_field ?? null,
            constant: m.constant ?? null,
            transforms: m.transforms ?? [],
          })),
        );
        setHydratedForDerived(derivedSchemaId);
      } catch (e) {
        setError((e as Error).message || "Failed to load existing mapping");
      } finally {
        setHydrating(false);
      }
    })();
  }, [open, derivedSchemaId, projectId, hydratedForDerived]);

  // Load full detail of the chosen source — also needed in edit mode so
  // the source-field dropdown has options. In edit mode we DO NOT reseed
  // rows from the source fields; the rows came from the existing mapping.
  useEffect(() => {
    if (!sourceId) {
      setSourceDetail(null);
      return;
    }
    setLoading(true);
    setError((prev) => prev); // keep any hydration error visible
    (async () => {
      try {
        const detail = await api.get<FileSchemaDetail>(
          `/api/v1/projects/${projectId}/synthetic/file-schemas/${sourceId}`,
        );
        setSourceDetail(detail);
        if (!isEditMode) {
          // Create mode: seed rows with one mapping per source field —
          // analysts almost always want a 1:1 starting point and edit
          // from there. Edit mode keeps the persisted rows untouched.
          setRows(
            detail.fields.map((f) => ({
              target_field: f.name,
              source_field: f.name,
              constant: null,
              transforms: [],
            })),
          );
        }
      } catch (e) {
        setError((e as Error).message || "Failed to load source schema");
      } finally {
        setLoading(false);
      }
    })();
  }, [sourceId, projectId, isEditMode]);

  const sourceFieldNames = useMemo(
    () => sourceDetail?.fields.map((f) => f.name) ?? [],
    [sourceDetail],
  );

  const updateRow = (i: number, patch: Partial<MappingRow>) =>
    setRows((p) => p.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const addRow = () =>
    setRows((p) => [
      ...p,
      {
        target_field: `TARGET_${p.length + 1}`,
        source_field: sourceFieldNames[0] ?? null,
        constant: null,
        transforms: [],
      },
    ]);

  const removeRow = (i: number) => setRows((p) => p.filter((_, j) => j !== i));

  const addTransform = (i: number, type: TransformSpec["type"]) => {
    const t: TransformSpec = { type, args: defaultArgsFor(type) };
    setRows((p) =>
      p.map((r, j) => (j === i ? { ...r, transforms: [...r.transforms, t] } : r)),
    );
  };

  const save = async () => {
    if (!sourceId || !targetName.trim() || rows.length === 0) {
      setError("Pick a source, name the target, and define at least one mapping.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const body = {
        target_name: targetName,
        target_format: targetFormat,
        target_encoding: targetEncoding,
        // Empty string → null on the wire so the backend stores NULL
        // (the "no custom output filename" intent) rather than the
        // literal "". Trimming avoids whitespace-only filenames.
        target_output_filename: targetOutputFilename.trim() || null,
        mappings: rows.map((r) => ({
          target_field: r.target_field,
          source_field: r.source_field,
          constant: r.constant,
          transforms: r.transforms,
        })),
      };

      if (isEditMode && derivedSchemaId) {
        // PATCH path — update the existing derived schema in place via
        // raw fetch (the api{} helper doesn't expose PATCH). Auth still
        // flows through the same cookie + credentials path.
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(
          `${apiBase}/api/v1/projects/${projectId}/file-schemas/${derivedSchemaId}/mapping`,
          {
            method: "PATCH",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        );
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error(
            (detail as { detail?: { detail?: string } | string }).detail
              ? typeof (detail as { detail?: unknown }).detail === "string"
                ? ((detail as { detail: string }).detail)
                : ((detail as { detail: { detail?: string } }).detail.detail || `HTTP ${res.status}`)
              : `HTTP ${res.status}`,
          );
        }
        const updated = (await res.json()) as {
          id: string;
          name: string;
          field_count: number;
        };
        toast.success(
          `Updated "${updated.name}" — ${updated.field_count} field${
            updated.field_count === 1 ? "" : "s"
          }`,
        );
        onClose();
      } else {
        const created = await api.post<{ id: string; name: string; field_count: number }>(
          `/api/v1/projects/${projectId}/file-schemas/${sourceId}/derive`,
          body,
        );
        toast.success(
          `Derived "${created.name}" with ${created.field_count} field${
            created.field_count === 1 ? "" : "s"
          }`,
        );
        onClose();
      }
    } catch (e) {
      setError((e as Error).message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AccessibleDialog
      open={open}
      onClose={onClose}
      titleId="dictionary-mapper-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="relative flex h-[80vh] w-full max-w-5xl flex-col rounded-lg border border-border bg-card shadow-xl">
        <header className="flex items-baseline justify-between border-b border-border px-6 py-4">
          <div>
            <h2 id="dictionary-mapper-title" className="text-lg font-semibold text-foreground">
              {isEditMode ? "Edit mapping" : "Data dictionary mapper"}
            </h2>
            <p className="text-xs text-muted-foreground">
              {isEditMode
                ? "Update an existing derived schema in place — the source is fixed and the schema id is preserved."
                : "Map source fields to a new target schema with optional transforms."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted/40 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="grid grid-cols-1 gap-2 px-6 py-3 text-xs sm:grid-cols-4">
          <label>
            <span className="block text-muted-foreground">Source schema</span>
            <Select
              fullWidth
              value={sourceId ?? ""}
              onChange={(e) => setSourceId(e.target.value || null)}
              disabled={isEditMode || hydrating}
              title={
                isEditMode
                  ? "Source can't change on re-edit — use 'New mapping' for a different source."
                  : undefined
              }
            >
              <option value="">— pick one —</option>
              {schemas.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.file_format})
                </option>
              ))}
            </Select>
          </label>
          <label>
            <span className="block text-muted-foreground">Target name</span>
            <input
              value={targetName}
              onChange={(e) => setTargetName(e.target.value)}
              placeholder="e.g. ORDERS_LEGACY"
              className="w-full rounded-md border border-input bg-background px-2 py-1.5"
            />
          </label>
          <label>
            <span className="block text-muted-foreground">Target format</span>
            <Select fullWidth value={targetFormat} onChange={(e) => setTargetFormat(e.target.value)}>
              <option value="csv">CSV</option>
              <option value="fixed_width">Fixed-width</option>
              <option value="vsam_fixed">VSAM (fixed)</option>
              <option value="parquet">Parquet</option>
            </Select>
          </label>
          <label>
            <span className="block text-muted-foreground">Target encoding</span>
            <Select fullWidth value={targetEncoding} onChange={(e) => setTargetEncoding(e.target.value)}>
              <option value="ascii">ASCII</option>
              <option value="utf8">UTF-8</option>
              <option value="ebcdic_cp037">EBCDIC cp037</option>
            </Select>
          </label>
        </div>

        <div className="px-6 pb-2 text-xs">
          <label className="block">
            <span className="block text-muted-foreground">
              Output filename <span className="text-[10px]">(optional)</span>
            </span>
            <input
              value={targetOutputFilename}
              onChange={(e) => setTargetOutputFilename(e.target.value)}
              placeholder={
                isEditMode
                  ? "Leave blank to clear; current value is preserved if you don't touch it"
                  : "e.g. orders_legacy.dat"
              }
              className="w-full max-w-md rounded-md border border-input bg-background px-2 py-1.5"
            />
          </label>
        </div>

        <div className="flex-1 overflow-auto px-6 pb-4">
          {hydrating || (isEditMode && !hydratedForDerived) ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading existing mapping…
            </div>
          ) : loading && !isEditMode ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading source schema…
            </div>
          ) : rows.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Pick a source schema to start mapping.
            </p>
          ) : (
            <div className="rounded-md border border-border bg-card">
              <table className="w-full text-xs">
                <thead className="bg-muted/30 text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1.5 font-medium">Target field</th>
                    <th className="px-2 py-1.5 font-medium">Source field</th>
                    <th className="px-2 py-1.5 font-medium">Constant</th>
                    <th className="px-2 py-1.5 font-medium">Transforms</th>
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="px-2 py-1">
                        <input
                          value={r.target_field}
                          onChange={(e) => updateRow(i, { target_field: e.target.value })}
                          className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Select
                          fullWidth
                          value={r.source_field ?? ""}
                          onChange={(e) =>
                            updateRow(i, {
                              source_field: e.target.value || null,
                              constant: e.target.value ? null : r.constant,
                            })
                          }
                        >
                          <option value="">— constant —</option>
                          {sourceFieldNames.map((n) => (
                            <option key={n} value={n}>
                              {n}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="px-2 py-1">
                        <input
                          value={r.constant ?? ""}
                          onChange={(e) =>
                            updateRow(i, {
                              constant: e.target.value || null,
                              source_field: e.target.value ? null : r.source_field,
                            })
                          }
                          placeholder="(none)"
                          className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <div className="flex flex-wrap items-center gap-1">
                          {r.transforms.map((t, ti) => (
                            <TransformPill
                              key={ti}
                              transform={t}
                              onRemove={() =>
                                updateRow(i, {
                                  transforms: r.transforms.filter((_, j) => j !== ti),
                                })
                              }
                            />
                          ))}
                          <Select
                            fullWidth={false}
                            value=""
                            onChange={(e) => {
                              if (e.target.value) {
                                addTransform(i, e.target.value as TransformSpec["type"]);
                              }
                              e.currentTarget.value = "";
                            }}
                            className="min-w-[120px]"
                          >
                            <option value="">+ transform</option>
                            <option value="trim">trim</option>
                            <option value="pad">pad</option>
                            <option value="upper">upper</option>
                            <option value="lower">lower</option>
                            <option value="substring">substring</option>
                            <option value="date_format">date_format</option>
                          </Select>
                        </div>
                      </td>
                      <td className="px-2 py-1 text-right">
                        <button
                          type="button"
                          onClick={() => removeRow(i)}
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
                  onClick={addRow}
                  className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                >
                  <Plus className="h-3 w-3" /> Add mapping
                </button>
              </div>
            </div>
          )}
        </div>

        {error && (
          <p className="mx-6 mb-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </p>
        )}

        <footer className="flex justify-end gap-2 border-t border-border px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-xs hover:bg-muted/40"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving || hydrating}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            {saving && <Loader2 className="h-3 w-3 animate-spin" />}
            {isEditMode ? "Update mapping" : "Save target schema"}
          </button>
        </footer>
      </div>
    </AccessibleDialog>
  );
}

function defaultArgsFor(type: TransformSpec["type"]): Record<string, string | number> {
  switch (type) {
    case "pad":
      return { length: 10, side: "right", char: " " };
    case "substring":
      return { start: 0, end: 10 };
    case "date_format":
      return { from: "YYYYMMDD", to: "YYYY-MM-DD" };
    default:
      return {};
  }
}
