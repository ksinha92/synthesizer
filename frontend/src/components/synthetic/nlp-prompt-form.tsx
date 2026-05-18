"use client";

import { useEffect, useRef, useState } from "react";
import { Brain, Loader2, Sparkles } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CLIENT_TIMEOUT_MS = 35000;
const WARNING_THRESHOLD_S = 25;

const EXAMPLE_PROMPTS = [
  "Generate 1000 insurance claims where 60% are health, 30% auto, 10% property, with amounts $200-$500K",
  "Create 500 users with realistic names, emails, addresses, and phone numbers",
  "Generate 2000 transactions with amounts following a lognormal distribution, 5% flagged as suspicious",
];

interface NLPPromptFormProps {
  projectId: string;
  connectionId: string;
  onPlanGenerated: (plan: Record<string, unknown>) => void;
}

export function NLPPromptForm({ projectId, connectionId, onPlanGenerated }: NLPPromptFormProps) {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  const startTimer = () => {
    setElapsed(0);
    timerRef.current = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setElapsed(0);
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");
    startTimer();

    const controller = new AbortController();
    abortRef.current = controller;

    const timeout = setTimeout(() => controller.abort(), CLIENT_TIMEOUT_MS);

    try {
      const res = await fetch(
        `${API_URL}/api/v1/projects/${projectId}/synthetic/nlp-generate`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: prompt.trim(), connection_id: connectionId }),
          signal: controller.signal,
        }
      );
      clearTimeout(timeout);

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || err.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      onPlanGenerated(data.plan);
    } catch (e) {
      clearTimeout(timeout);
      if ((e as Error).name === "AbortError") {
        setError("Generation timed out. Try a simpler prompt or fewer tables.");
      } else {
        setError(e instanceof Error ? e.message : "Failed to generate plan");
      }
    }
    stopTimer();
    setLoading(false);
    abortRef.current = null;
  };

  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Brain className="h-5 w-5 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Describe the data you need</h3>
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Generate 5000 insurance claims where 20% are auto claims with amounts $500-$50K..."
        rows={4}
        className="w-full rounded-lg border border-input bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
      />

      {/* Example prompts */}
      <div className="flex flex-wrap gap-2">
        {EXAMPLE_PROMPTS.map((ex, i) => (
          <button
            key={i}
            onClick={() => setPrompt(ex)}
            className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Sparkles className="h-3 w-3" />
            {ex.slice(0, 50)}...
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && elapsed >= WARNING_THRESHOLD_S && (
        <p className="text-sm text-yellow-600 dark:text-yellow-400">This is taking longer than usual...</p>
      )}

      <button
        onClick={handleGenerate}
        disabled={!prompt.trim() || loading}
        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
        {loading ? `Generating... ${elapsed}s` : "Generate Plan"}
      </button>
    </div>
  );
}
