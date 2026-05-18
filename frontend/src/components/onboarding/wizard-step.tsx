"use client";

import { cn } from "@/lib/utils";

interface WizardStepProps {
  stepNumber: number;
  totalSteps: number;
  title: string;
  description: string;
  hint: string;
  onNext: () => void;
  onSkip: () => void;
  isLast: boolean;
}

export function WizardStep({ stepNumber, totalSteps, title, description, hint, onNext, onSkip, isLast }: WizardStepProps) {
  return (
    <div className="space-y-3">
      {/* Progress dots */}
      <div className="flex items-center gap-1.5">
        {Array.from({ length: totalSteps }, (_, i) => (
          <div key={i} className={cn("h-1.5 rounded-full transition-all", i === stepNumber ? "w-6 bg-primary" : i < stepNumber ? "w-1.5 bg-primary/50" : "w-1.5 bg-muted")} />
        ))}
      </div>

      {/* Content */}
      <div>
        <p className="text-xs text-muted-foreground">Step {stepNumber + 1} of {totalSteps}</p>
        <h3 className="text-sm font-semibold text-foreground mt-0.5">{title}</h3>
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
        <p className="text-xs text-primary mt-2 font-medium">{hint}</p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button onClick={onNext} className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90">
          {isLast ? "Finish" : "Next"}
        </button>
        <button onClick={onSkip} className="text-xs text-muted-foreground hover:text-foreground">Skip tour</button>
      </div>
    </div>
  );
}
