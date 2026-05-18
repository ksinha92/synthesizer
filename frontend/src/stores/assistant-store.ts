"use client";

import { create } from "zustand";
import { api } from "@/hooks/use-api";

interface Message { role: "user" | "assistant"; content: string; actions?: { label: string; href: string }[]; }

interface AssistantState {
  messages: Message[];
  isOpen: boolean;
  loading: boolean;
  consentGiven: boolean;
  toggleOpen: () => void;
  sendMessage: (text: string, projectId: string, page?: string) => Promise<void>;
  giveConsent: () => void;
}

export const useAssistantStore = create<AssistantState>((set, get) => ({
  messages: [],
  isOpen: false,
  loading: false,
  consentGiven: typeof window !== "undefined" ? localStorage.getItem("dw-assistant-consent") === "true" : false,

  toggleOpen: () => set((s) => ({ isOpen: !s.isOpen })),

  giveConsent: () => {
    localStorage.setItem("dw-assistant-consent", "true");
    set({ consentGiven: true });
  },

  sendMessage: async (text, projectId, page) => {
    set((s) => ({ messages: [...s.messages, { role: "user", content: text }], loading: true }));
    try {
      const data = await api.post<{ response: string; actions: { label: string; href: string }[] }>(
        "/api/v1/assistant/chat",
        { message: text, project_id: projectId, context: { page: page || "dashboard" } }
      );
      set((s) => ({
        messages: [...s.messages, { role: "assistant", content: data.response, actions: data.actions }],
        loading: false,
      }));
    } catch {
      set((s) => ({
        messages: [...s.messages, { role: "assistant", content: "Sorry, I couldn't process that request." }],
        loading: false,
      }));
    }
  },
}));
