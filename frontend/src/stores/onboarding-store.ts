"use client";

import { create } from "zustand";

function getOnboardingKey(): string {
  if (typeof window === "undefined") return "dw-onboarding-done";
  try {
    const authState = JSON.parse(localStorage.getItem("auth-store") || "{}");
    const userId = authState?.state?.user?.id;
    return userId ? `dw-onboarding-${userId}` : "dw-onboarding-done";
  } catch {
    return "dw-onboarding-done";
  }
}

function isOnboardingDone(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(getOnboardingKey()) === "true";
}

interface OnboardingState {
  currentStep: number;
  completed: boolean;
  dismissed: boolean;
  visible: boolean;
  nextStep: () => void;
  skipWizard: () => void;
  completeWizard: () => void;
}

export const useOnboardingStore = create<OnboardingState>((set) => ({
  currentStep: 0,
  completed: isOnboardingDone(),
  dismissed: isOnboardingDone(),
  visible: !isOnboardingDone(),

  nextStep: () => set((s) => {
    const next = s.currentStep + 1;
    if (next >= 5) {
      localStorage.setItem(getOnboardingKey(), "true");
      return { currentStep: next, completed: true, visible: false };
    }
    return { currentStep: next };
  }),

  skipWizard: () => {
    localStorage.setItem(getOnboardingKey(), "true");
    set({ dismissed: true, visible: false });
  },

  completeWizard: () => {
    localStorage.setItem(getOnboardingKey(), "true");
    set({ completed: true, visible: false });
  },
}));
