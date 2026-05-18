"use client";

import { useCallback, useMemo, useState } from "react";
import { Check, ChevronRight } from "lucide-react";

import { AccessibleDialog } from "@/components/common/accessible-dialog";
import { toast } from "@/components/common/toast";
import { cn } from "@/lib/utils";

import { StepSource } from "./step-source";
import { StepParse } from "./step-parse";
import { StepSample } from "./step-sample";
import { StepConfirm } from "./step-confirm";
import type { FileSchemaDetail, WizardSource } from "../types";

interface FileLoaderWizardProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onSchemaCreated: (schema: FileSchemaDetail) => void;
}

const STEP_ORDER = ["source", "parse", "sample", "confirm"] as const;
type Step = (typeof STEP_ORDER)[number];

const STEP_LABEL: Record<Step, string> = {
  source: "Source",
  parse: "Parse & edit",
  sample: "Load sample (optional)",
  confirm: "Confirm",
};

/**
 * Modal-hosted 4-step wizard that drives the existing file-schema
 * endpoints (upload-copybook | upload-dictionary | manual | from-discovery)
 * and the new preview endpoint. Each step owns one focused responsibility
 * so the file stays well under the project's 500-LOC ceiling.
 */
export function FileLoaderWizard({
  projectId,
  open,
  onClose,
  onSchemaCreated,
}: FileLoaderWizardProps) {
  const [step, setStep] = useState<Step>("source");
  const [source, setSource] = useState<WizardSource | null>(null);
  const [parsedSchema, setParsedSchema] = useState<FileSchemaDetail | null>(null);

  const currentIndex = useMemo(() => STEP_ORDER.indexOf(step), [step]);

  const reset = useCallback(() => {
    setStep("source");
    setSource(null);
    setParsedSchema(null);
  }, []);

  const handleClose = useCallback(() => {
    onClose();
    // Defer the reset so the closing animation can finish without a flicker.
    setTimeout(reset, 200);
  }, [onClose, reset]);

  const handleParsed = (schema: FileSchemaDetail) => {
    setParsedSchema(schema);
    setStep("sample");
  };

  const handleSampleDone = () => {
    setStep("confirm");
  };

  const handleConfirm = () => {
    if (parsedSchema) {
      toast.success(`Saved schema "${parsedSchema.name}"`);
      onSchemaCreated(parsedSchema);
    }
    handleClose();
  };

  return (
    <AccessibleDialog
      open={open}
      onClose={handleClose}
      titleId="file-loader-wizard-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="relative w-full max-w-4xl rounded-lg border border-border bg-card shadow-xl">
        <header className="border-b border-border px-6 py-4">
          <h2
            id="file-loader-wizard-title"
            className="text-lg font-semibold text-foreground"
          >
            Add file schema
          </h2>
          <p className="text-xs text-muted-foreground">
            Import a copybook, data dictionary, build manually, or derive from a
            discovered database table.
          </p>
        </header>

        <nav className="flex items-center gap-1 border-b border-border bg-muted/20 px-4 py-2 text-xs">
          {STEP_ORDER.map((s, i) => {
            const active = s === step;
            const done = i < currentIndex;
            return (
              <div key={s} className="flex items-center gap-1">
                <span
                  className={cn(
                    "inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px]",
                    done && "bg-primary text-primary-foreground",
                    active && !done && "bg-primary/15 text-foreground ring-1 ring-primary",
                    !active && !done && "bg-muted text-muted-foreground",
                  )}
                >
                  {done ? <Check className="h-3 w-3" /> : i + 1}
                </span>
                <span
                  className={cn(
                    "text-[11px]",
                    active ? "text-foreground font-medium" : "text-muted-foreground",
                  )}
                >
                  {STEP_LABEL[s]}
                </span>
                {i < STEP_ORDER.length - 1 && (
                  <ChevronRight className="mx-1 h-3 w-3 text-muted-foreground" />
                )}
              </div>
            );
          })}
        </nav>

        <div className="px-6 py-5">
          {step === "source" && (
            <StepSource
              selected={source}
              onSelect={(src) => {
                setSource(src);
                setStep("parse");
              }}
              onCancel={handleClose}
            />
          )}
          {step === "parse" && source && (
            <StepParse
              projectId={projectId}
              source={source}
              onParsed={handleParsed}
              onBack={() => setStep("source")}
            />
          )}
          {step === "sample" && parsedSchema && (
            <StepSample
              projectId={projectId}
              schema={parsedSchema}
              onDone={handleSampleDone}
              onBack={() => setStep("parse")}
              onSkip={handleSampleDone}
            />
          )}
          {step === "confirm" && parsedSchema && (
            <StepConfirm
              schema={parsedSchema}
              onBack={() => setStep("sample")}
              onConfirm={handleConfirm}
            />
          )}
        </div>
      </div>
    </AccessibleDialog>
  );
}
