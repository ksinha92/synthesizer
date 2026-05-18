"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Info, Send, X } from "lucide-react";
import { useAssistantStore } from "@/stores/assistant-store";
import { ChatMessage } from "./chat-message";
import { api } from "@/hooks/use-api";

interface AssistantSidebarProps {
  projectId?: string;
  currentPage?: string;
}

export function AssistantSidebar({ projectId, currentPage }: AssistantSidebarProps) {
  const { messages, isOpen, loading, consentGiven, toggleOpen, sendMessage, giveConsent } = useAssistantStore();
  const [input, setInput] = useState("");
  const [providerName, setProviderName] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch provider status once on open
  useEffect(() => {
    if (isOpen && !providerName) {
      api.get<{ provider: string; configured: boolean }>("/api/v1/assistant/provider-status")
        .then((d) => setProviderName(d.configured ? d.provider : "Not configured"))
        .catch(() => setProviderName(null));
    }
  }, [isOpen, providerName]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || loading) return;
    sendMessage(input.trim(), projectId || "global", currentPage);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={toggleOpen}
        className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
        title="Open AI Assistant"
      >
        <Bot className="h-5 w-5" />
      </button>
    );
  }

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-[400px] border-l border-border bg-card shadow-xl flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <span className="text-sm font-semibold text-foreground">Synthia</span>
          {providerName && (
            <span className="text-[10px] rounded bg-muted px-1.5 py-0.5 text-muted-foreground capitalize">{providerName}</span>
          )}
        </div>
        <button onClick={toggleOpen} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Consent banner */}
      {!consentGiven && (
        <div className="border-b border-border bg-blue-500/5 px-4 py-3">
          <div className="flex items-start gap-2">
            <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs text-foreground">
                The AI assistant sends project metadata (table names, PII types) to the configured LLM provider. No actual data values are sent.
              </p>
              <button onClick={giveConsent} className="mt-2 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
                I understand
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-8">
            <Bot className="h-8 w-8 mx-auto mb-2 text-muted-foreground/50" />
            <p>Ask me anything about your data.</p>
            <p className="text-xs mt-1">"Which tables have unmasked PII?"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role} content={msg.content} actions={msg.actions} />
        ))}
        {loading && (
          <div className="flex items-center gap-1 text-muted-foreground">
            <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, 2000))}
            onKeyDown={handleKeyDown}
            placeholder={consentGiven ? "Ask about your data..." : "Accept terms above to start"}
            disabled={!consentGiven || loading}
            rows={1}
            className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading || !consentGiven}
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1">{input.length}/2000</p>
      </div>
    </div>
  );
}
