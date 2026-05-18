"use client";

import { useEffect } from "react";
import { Sparkles, X } from "lucide-react";
import { useOnboardingStore } from "@/stores/onboarding-store";
import { useAssistantStore } from "@/stores/assistant-store";
import { WizardStep } from "./wizard-step";

const STEPS = [
  { title: "Create a Project", description: "Projects organize your TDM work. Each project connects to data sources and manages discovery, masking, and generation.", hint: "Go to Projects → Click 'New Project'" },
  { title: "Add a Connection", description: "Connect to your database (PostgreSQL, MySQL, MongoDB, or Snowflake) so Synthia can introspect your schema.", hint: "Inside your project → Connections → 'Add Connection'" },
  { title: "Run Discovery", description: "Discover your schema and detect PII automatically with our 4-layer AI pipeline (regex, NER, heuristics, LLM).", hint: "Discovery tab → Select connection → 'Run Discovery'" },
  { title: "Review PII Results", description: "Review detected PII columns, override classifications if needed, and see confidence scores for each detection.", hint: "Discovery → PII Results tab → Review badges" },
  { title: "Apply Masking", description: "Create masking policies to protect sensitive data with 7 strategies including format-preserving encryption.", hint: "Masking tab → 'Auto-suggest from PII' → Execute" },
];

export function OnboardingWizard() {
  const { currentStep, visible, nextStep, skipWizard, completeWizard } = useOnboardingStore();
  const assistantOpen = useAssistantStore((s) => s.isOpen);

  // Hide wizard when assistant opens (z-index conflict prevention)
  if (!visible || assistantOpen) return null;

  const isLast = currentStep >= STEPS.length - 1;
  const isDone = currentStep >= STEPS.length;

  if (isDone) {
    return (
      <div className="fixed bottom-20 right-6 z-40 w-80 rounded-xl border border-border bg-card p-5 shadow-xl">
        <div className="text-center space-y-3">
          <Sparkles className="h-8 w-8 text-primary mx-auto" />
          <h3 className="text-sm font-semibold text-foreground">You're all set!</h3>
          <p className="text-xs text-muted-foreground">You're ready to manage test data like a pro. The AI assistant (Bot icon) can help anytime.</p>
          <button onClick={completeWizard} className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground">
            Get started
          </button>
        </div>
      </div>
    );
  }

  const step = STEPS[currentStep];

  return (
    <div className="fixed bottom-20 right-6 z-40 w-80 rounded-xl border border-primary/30 bg-card p-5 shadow-xl">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-xs font-medium text-primary">Getting Started</span>
        </div>
        <button onClick={skipWizard} className="text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <WizardStep
        stepNumber={currentStep}
        totalSteps={STEPS.length}
        title={step.title}
        description={step.description}
        hint={step.hint}
        onNext={nextStep}
        onSkip={skipWizard}
        isLast={isLast}
      />
    </div>
  );
}
