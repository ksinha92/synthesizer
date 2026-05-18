"use client";

import { useEffect, useState } from "react";
import { Check, Cloud, Cpu, Loader2, Network, X, Zap } from "lucide-react";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";
import { cn } from "@/lib/utils";

type ProviderKey = "claude" | "ollama" | "litellm";

interface LLMSettings {
  provider: ProviderKey;
  has_api_key: boolean;
  ollama_url: string;
  ollama_model: string;
  claude_model: string;
  litellm_url: string;
  has_litellm_api_key: boolean;
  litellm_model: string;
  litellm_verify_ssl: boolean;
  litellm_no_proxy: string;
}

interface TestResult {
  success: boolean;
  latency_ms: number | null;
  error: string | null;
  provider: string;
}

const PROVIDER_TILES: Array<{
  key: ProviderKey;
  label: string;
  caption: string;
  Icon: typeof Cloud;
}> = [
  { key: "claude",  label: "Claude (Anthropic)",  caption: "Cloud API — highest quality",          Icon: Cloud },
  { key: "ollama",  label: "Ollama (Self-hosted)",caption: "Local LLM — private, no API costs",    Icon: Cpu },
  { key: "litellm", label: "LiteLLM Proxy",       caption: "OpenAI-compatible gateway / on-prem",  Icon: Network },
];

export function LLMSettingsPanel() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [provider, setProvider] = useState<ProviderKey>("claude");
  const [claudeApiKey, setClaudeApiKey] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [ollamaModel, setOllamaModel] = useState("llama3.1");
  const [litellmUrl, setLitellmUrl] = useState("");
  const [litellmApiKey, setLitellmApiKey] = useState("");
  const [litellmModel, setLitellmModel] = useState("gpt-4o-mini");
  const [litellmVerifySsl, setLitellmVerifySsl] = useState(true);
  const [litellmNoProxy, setLitellmNoProxy] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await api.get<LLMSettings>("/api/v1/admin/settings/llm");
        setSettings(data);
        setProvider(data.provider);
        setOllamaUrl(data.ollama_url);
        setOllamaModel(data.ollama_model);
        setLitellmUrl(data.litellm_url ?? "");
        setLitellmModel(data.litellm_model ?? "gpt-4o-mini");
        setLitellmVerifySsl(data.litellm_verify_ssl ?? true);
        setLitellmNoProxy(data.litellm_no_proxy ?? "");
      } catch {
        // Not configured yet — keep form defaults
      }
      setLoading(false);
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    if (provider === "litellm" && !litellmUrl.trim()) {
      toast.error("LiteLLM URL is required");
      return;
    }
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        provider,
        ollama_url: ollamaUrl,
        ollama_model: ollamaModel,
        litellm_url: litellmUrl,
        litellm_model: litellmModel,
        litellm_verify_ssl: litellmVerifySsl,
        litellm_no_proxy: litellmNoProxy,
      };
      if (claudeApiKey) body.claude_api_key = claudeApiKey;
      if (litellmApiKey) body.litellm_api_key = litellmApiKey;

      const updated = await api.put<LLMSettings>("/api/v1/admin/settings/llm", body);
      setSettings(updated);
      setClaudeApiKey("");
      setLitellmApiKey("");
      toast.success("LLM settings saved");
    } catch {
      toast.error("Failed to save settings");
    }
    setSaving(false);
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.post<TestResult>("/api/v1/admin/settings/llm/test");
      setTestResult(result);
    } catch {
      setTestResult({ success: false, latency_ms: null, error: "Request failed", provider: "unknown" });
    }
    setTesting(false);
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />)}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Provider selector */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        <h4 className="text-sm font-semibold text-foreground">LLM Provider</h4>
        <p className="text-xs text-muted-foreground">
          Choose the AI backend for the assistant chat, PII detection (Layer 4), and synthetic data NLP generation.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {PROVIDER_TILES.map(({ key, label, caption, Icon }) => {
            const active = provider === key;
            return (
              <button
                key={key}
                onClick={() => setProvider(key)}
                className={cn(
                  "flex items-center gap-3 rounded-lg border p-4 text-left transition-all",
                  active ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
                )}
              >
                <Icon className={cn("h-5 w-5 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
                <div>
                  <p className="text-sm font-medium text-foreground">{label}</p>
                  <p className="text-[11px] text-muted-foreground">{caption}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Provider-specific config */}
      {provider === "claude" && (
        <div className="rounded-lg border border-border bg-card p-5 space-y-4">
          <h4 className="text-sm font-semibold text-foreground">Claude Configuration</h4>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">API Key</label>
            <input
              type="password"
              value={claudeApiKey}
              onChange={(e) => setClaudeApiKey(e.target.value)}
              placeholder={settings?.has_api_key ? "••••••••••••• (configured)" : "sk-ant-..."}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              {settings?.has_api_key ? "Key is configured. Enter a new value to replace it." : "Get your API key from console.anthropic.com"}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Model</label>
            <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
              {settings?.claude_model || "claude-sonnet-4-20250514"}
            </div>
          </div>
        </div>
      )}

      {provider === "ollama" && (
        <div className="rounded-lg border border-border bg-card p-5 space-y-4">
          <h4 className="text-sm font-semibold text-foreground">Ollama Configuration</h4>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Server URL</label>
            <input
              type="text"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Model</label>
            <input
              type="text"
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              placeholder="llama3.1"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono"
            />
            <p className="mt-1 text-[10px] text-muted-foreground">Must be already pulled on the Ollama server (e.g., llama3.1, mistral, codellama)</p>
          </div>
        </div>
      )}

      {provider === "litellm" && (
        <div className="rounded-lg border border-border bg-card p-5 space-y-4">
          <h4 className="text-sm font-semibold text-foreground">LiteLLM Configuration</h4>
          <p className="text-[11px] text-muted-foreground">
            Point at any OpenAI-compatible endpoint — a LiteLLM proxy, Azure OpenAI, Bedrock gateway, or on-prem LLM router.
          </p>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Base URL</label>
            <input
              type="text"
              value={litellmUrl}
              onChange={(e) => setLitellmUrl(e.target.value)}
              placeholder="https://litellm.corp.internal/v1"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono"
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              Trailing <code>/v1</code> is optional — both forms are accepted.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">API Key (SK)</label>
            <input
              type="password"
              value={litellmApiKey}
              onChange={(e) => setLitellmApiKey(e.target.value)}
              placeholder={settings?.has_litellm_api_key ? "••••••••••••• (configured)" : "sk-..."}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              {settings?.has_litellm_api_key
                ? "Key is configured. Enter a new value to replace it."
                : "Bearer token sent as Authorization: Bearer <key>."}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">Model</label>
            <input
              type="text"
              value={litellmModel}
              onChange={(e) => setLitellmModel(e.target.value)}
              placeholder="gpt-4o-mini"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono"
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              Use whatever model alias your LiteLLM router exposes (e.g. <code>gpt-4o-mini</code>, <code>claude-3-5-sonnet</code>, <code>azure/gpt-4</code>).
            </p>
          </div>

          <label className="flex items-start gap-2 cursor-pointer pt-1">
            <input
              type="checkbox"
              checked={litellmVerifySsl}
              onChange={(e) => setLitellmVerifySsl(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-input"
            />
            <span className="text-xs text-foreground">
              Verify SSL certificate
              <span className="block text-[10px] text-muted-foreground">
                Disable only for internal hosts using an untrusted/self-signed CA. Keep enabled for any public endpoint.
              </span>
            </span>
          </label>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1">No-Proxy Hosts</label>
            <input
              type="text"
              value={litellmNoProxy}
              onChange={(e) => setLitellmNoProxy(e.target.value)}
              placeholder="litellm.corp.internal,10.0.0.0/8,.internal"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono"
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              Comma-separated hosts or CIDRs that should bypass <code>HTTP_PROXY</code> / <code>HTTPS_PROXY</code> for LiteLLM calls.
            </p>
          </div>
        </div>
      )}

      {/* Test result */}
      {testResult && (
        <div className={cn(
          "rounded-lg border px-4 py-3 flex items-center gap-3",
          testResult.success
            ? "border-green-500/30 bg-green-500/5 text-green-700 dark:text-green-400"
            : "border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-400"
        )}>
          {testResult.success ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
          <div className="flex-1 text-sm">
            {testResult.success
              ? `Connected to ${testResult.provider} — ${testResult.latency_ms}ms`
              : `Failed: ${testResult.error}`
            }
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleTest}
          disabled={testing}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
        >
          {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
          {testing ? "Testing..." : "Test Connection"}
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
