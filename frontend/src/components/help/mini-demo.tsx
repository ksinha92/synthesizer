"use client";

import { useState } from "react";
import { ArrowRight, RotateCcw, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DemoKind } from "@/content/help-content";

interface MiniDemoProps {
  kind: DemoKind;
}

export function MiniDemo({ kind }: MiniDemoProps) {
  if (kind === "mask-preview") return <MaskPreview />;
  if (kind === "pii-classifier") return <PiiClassifier />;
  if (kind === "subset-builder") return <SubsetBuilder />;
  return null;
}

// ── Mask preview: pick a generator, see real → masked transformation. ──────────

// Illustrative shape-only previews of the masking strategies that actually
// ship in Synthia. The applied transforms below are simplified visualizations
// — production runs server-side with proper crypto (HMAC-SHA256 for HASH, the
// faker library with deterministic per-row seeding for FAKER_REPLACE, and a
// Fernet-keyed format-preserving cipher for FPE). The point of the preview is
// to show what each STRATEGY produces, not to reproduce its algorithm.
const MASK_OPTIONS: Array<{
  key: string;
  label: string;
  apply: (s: string) => string;
  shape: string;
  reversible: boolean;
}> = [
  {
    key: "redact",
    label: "Redact",
    // Real REDACT: replaces every character with the configured redaction
    // character ("X" by default), preserving length but not structure.
    apply: (s) => "X".repeat(s.length),
    shape: "Every character is replaced with the configured redaction character (X by default). Length is preserved, structure is not. One-way.",
    reversible: false,
  },
  {
    key: "hash",
    label: "Hash",
    apply: (s) => {
      // Toy fingerprint for the preview only. Production uses
      // `hmac.new(salted_key, value, hashlib.sha256).hexdigest()[:16]`.
      let h = 0;
      for (const c of s) h = ((h << 5) - h + c.charCodeAt(0)) | 0;
      return (h >>> 0).toString(16).padStart(16, "0");
    },
    shape: "Deterministic 16-char hex digest (first 16 chars of HMAC-SHA256). Same input + same deployment salt always yields the same digest. Optionally a consistency-group label is mixed into the salt so the same value hashes identically across every column in the group. The preview here is a toy fingerprint just to show output shape — not the real HMAC.",
    reversible: false,
  },
  {
    key: "faker_replace",
    label: "Faker replace",
    apply: (s) => {
      // Pool just illustrates that the output is realistic but synthetic.
      // Production uses the `faker` Python library with deterministic
      // per-row seeding so linked columns stay consistent.
      const names = ["jordan.lee@acme.com", "sam.parker@globex.io", "alex.kim@initech.net"];
      let i = 0;
      for (const ch of s) i = (i + ch.charCodeAt(0)) % names.length;
      return names[i];
    },
    shape: "Realistic synthetic value drawn from the faker library that matches the inferred type. Optionally seeded by linked-column values so first_name + last_name + email stay coherent per row.",
    reversible: false,
  },
  {
    key: "partial_mask",
    label: "Partial mask",
    apply: (s) => {
      // Real PARTIAL_MASK preserves head/tail and masks the middle.
      if (s.length <= 4) return "X".repeat(s.length);
      const keep = Math.max(2, Math.min(4, Math.floor(s.length / 4)));
      return s.slice(0, keep) + "X".repeat(s.length - keep * 2) + s.slice(-keep);
    },
    shape: "Keeps a configurable head/tail and masks the middle (useful for credit-card last-4 or phone area-code patterns).",
    reversible: false,
  },
  {
    key: "fpe",
    label: "FPE (format-preserving)",
    apply: (s) => {
      // Real FPE is FF3-1, a Feistel block cipher operating over a per-class
      // alphabet (digits / lowercase / mixed). The preview just rotates
      // characters within their class so the OUTPUT visibly stays the same
      // shape — it is NOT FF3 and not cryptographically secure.
      const rot = (c: string, base: number, mod: number) =>
        String.fromCharCode(base + ((c.charCodeAt(0) - base + 7) % mod));
      return Array.from(s)
        .map((c) => {
          if (/[a-z]/.test(c)) return rot(c, 97, 26);
          if (/[A-Z]/.test(c)) return rot(c, 65, 26);
          if (/\d/.test(c)) return rot(c, 48, 10);
          return c;
        })
        .join("");
    },
    shape: "FF3-1 format-preserving encryption operating per character class (digits / lowercase / mixed). The ciphertext is the same length and alphabet as the source. The AES-128 key is HKDF-derived from the deployment SECRET_KEY, so reversal requires the same SECRET_KEY. The preview is a simple per-class rotation just to show that 'format-preserving' means output shape matches input shape.",
    reversible: true,
  },
];

function MaskPreview() {
  const [value, setValue] = useState("jane.doe@acme.com");
  const [option, setOption] = useState(MASK_OPTIONS[2]);
  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" aria-hidden />
          <h4 className="text-sm font-semibold text-foreground">Generator output shapes</h4>
        </div>
        <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Illustrative
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        Pick one of the masking strategies Synthia actually supports to preview the <em>shape</em>{" "}
        of its output. This is a client-side illustration; production runs server-side with the
        primitives in <code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">infrastructure/engine/masking_engine.py</code>{" "}
        — HMAC-SHA256 over a deployment-wide salt for Hash (optionally mixed with a consistency
        group), the faker library with per-row seeding for Faker replace, and FF3-1 format-preserving
        encryption with an HKDF-derived AES-128 key for FPE.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {MASK_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => setOption(opt)}
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
              option.key === opt.key
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-background text-muted-foreground hover:bg-muted",
            )}
            aria-pressed={option.key === opt.key}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block text-xs">
          <span className="mb-1 block font-medium text-foreground">Input</span>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          />
        </label>
        <div className="text-xs">
          <span className="mb-1 block font-medium text-foreground">Output ({option.label})</span>
          <div className="rounded-md border border-border bg-muted/40 px-2 py-1.5 font-mono text-xs text-foreground tabular-nums">
            {option.apply(value) || <span className="text-muted-foreground">(enter input)</span>}
          </div>
        </div>
      </div>
      <div className="rounded-md border border-border bg-muted/20 p-3 text-[11px] leading-relaxed text-muted-foreground">
        <p>{option.shape}</p>
        <p className="mt-1">
          <span className="font-medium text-foreground">Reversible:</span>{" "}
          {option.reversible
            ? "yes — only with the stored mapping/key"
            : "no — one-way transformation"}
        </p>
      </div>
    </div>
  );
}

// ── PII classifier demo: paste text, see which substrings get classified. ──────

const PII_DETECTORS: Array<{
  type: string;
  color: string;
  test: (s: string) => Array<[number, number]>;
}> = [
  {
    type: "email",
    color: "--chart-1",
    test: (s) => Array.from(s.matchAll(/[\w.+-]+@[\w-]+\.[\w.-]+/g)).map((m) => [m.index!, m.index! + m[0].length]),
  },
  {
    type: "phone",
    color: "--chart-2",
    test: (s) => Array.from(s.matchAll(/(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/g)).map((m) => [m.index!, m.index! + m[0].length]),
  },
  {
    type: "ssn",
    color: "--chart-6",
    test: (s) => Array.from(s.matchAll(/\b\d{3}-\d{2}-\d{4}\b/g)).map((m) => [m.index!, m.index! + m[0].length]),
  },
  {
    type: "credit_card",
    color: "--chart-5",
    test: (s) => Array.from(s.matchAll(/\b(?:\d[ -]?){13,19}\b/g)).map((m) => [m.index!, m.index! + m[0].length]),
  },
];

function PiiClassifier() {
  const [text, setText] = useState(
    "Contact jane.doe@acme.com or call (415) 555-0142. SSN 123-45-6789. Card 4111 1111 1111 1111.",
  );

  const segments = (() => {
    const hits: Array<{ start: number; end: number; type: string; color: string }> = [];
    for (const d of PII_DETECTORS) {
      for (const [start, end] of d.test(text)) hits.push({ start, end, type: d.type, color: d.color });
    }
    hits.sort((a, b) => a.start - b.start);
    // Drop overlapping (first-wins)
    const dedup: typeof hits = [];
    let cursor = -1;
    for (const h of hits) {
      if (h.start < cursor) continue;
      dedup.push(h);
      cursor = h.end;
    }
    // Build segments alternating between hits and plain text
    const out: Array<{ text: string; type?: string; color?: string }> = [];
    let i = 0;
    for (const h of dedup) {
      if (i < h.start) out.push({ text: text.slice(i, h.start) });
      out.push({ text: text.slice(h.start, h.end), type: h.type, color: h.color });
      i = h.end;
    }
    if (i < text.length) out.push({ text: text.slice(i) });
    return { segments: out, hits: dedup };
  })();

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" aria-hidden />
          <h4 className="text-sm font-semibold text-foreground">Pattern detector preview</h4>
        </div>
        <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Illustrative
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        Paste any text — this regex-only pattern matcher highlights a few well-known PII shapes
        (email, phone, SSN, credit card). It is <em>not</em> the production classifier. Real
        discovery is column-aware, layers regex with column-name heuristics and ML, and emits a
        confidence score per column rather than highlighting substrings.
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        className="w-full resize-y rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        aria-label="Sample text to classify"
      />
      <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed">
        {segments.segments.map((seg, i) =>
          seg.type ? (
            <span
              key={i}
              className="rounded px-1 py-0.5 font-mono"
              style={{
                background: `hsl(var(${seg.color}) / 0.18)`,
                color: `hsl(var(${seg.color}))`,
              }}
              title={seg.type}
            >
              {seg.text}
            </span>
          ) : (
            <span key={i}>{seg.text}</span>
          ),
        )}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        <span className="text-muted-foreground">Detected:</span>
        {segments.hits.length === 0 ? (
          <span className="text-muted-foreground">nothing</span>
        ) : (
          PII_DETECTORS.map((d) => {
            const count = segments.hits.filter((h) => h.type === d.type).length;
            if (count === 0) return null;
            return (
              <span
                key={d.type}
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                style={{ background: `hsl(var(${d.color}) / 0.12)`, color: `hsl(var(${d.color}))` }}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: `hsl(var(${d.color}))` }} />
                {d.type} · {count}
              </span>
            );
          })
        )}
      </div>
    </div>
  );
}

// ── Subset builder demo: pick a seed, watch the dependency walk. ───────────────

function SubsetBuilder() {
  const [seedCount, setSeedCount] = useState(3);
  const [step, setStep] = useState(0);

  const customers = Array.from({ length: 10 }, (_, i) => i);
  const orders = Array.from({ length: 18 }, (_, i) => ({ id: i, customer: i % 10 }));
  const items = Array.from({ length: 25 }, (_, i) => ({ id: i, order: i % 18 }));

  const seedCustomers = customers.slice(0, seedCount);
  const seedOrders = step >= 1 ? orders.filter((o) => seedCustomers.includes(o.customer)) : [];
  const seedOrderIds = new Set(seedOrders.map((o) => o.id));
  const seedItems = step >= 2 ? items.filter((it) => seedOrderIds.has(it.order)) : [];

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" aria-hidden />
          <h4 className="text-sm font-semibold text-foreground">FK-walk concept</h4>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Illustrative
          </span>
          <button
            type="button"
            onClick={() => setStep(0)}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-[11px] hover:bg-muted/50"
          >
            <RotateCcw className="h-3 w-3" /> Reset
          </button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        A toy three-table example to convey the <em>idea</em> of subsetting. Pick seed customers and
        step forward to see how each FK hop expands the slice. The real subsetter handles cycles,
        virtual FKs, joint cardinalities, and many-to-many relationships — not modelled here.
      </p>
      <div className="flex items-center gap-3 text-xs">
        <label className="flex items-center gap-2">
          <span className="font-medium text-foreground">Seed customers:</span>
          <input
            type="range"
            min={1}
            max={5}
            value={seedCount}
            onChange={(e) => {
              setSeedCount(Number(e.target.value));
              setStep(0);
            }}
            className="accent-primary"
          />
          <span className="tabular-nums text-foreground">{seedCount}</span>
        </label>
        <button
          type="button"
          disabled={step >= 2}
          onClick={() => setStep((s) => Math.min(s + 1, 2))}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {step === 0 ? "Walk → orders" : step === 1 ? "Walk → line items" : "Done"}
          {step < 2 && <ArrowRight className="h-3 w-3" />}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[10px]">
        <DotTable label="Customers" count={customers.length} seeded={seedCustomers} highlightAll={false} />
        <DotTable
          label="Orders"
          count={orders.length}
          seeded={seedOrders.map((o) => o.id)}
          highlightAll={false}
        />
        <DotTable
          label="Order items"
          count={items.length}
          seeded={seedItems.map((it) => it.id)}
          highlightAll={false}
        />
      </div>
      <p className="text-[11px] text-muted-foreground">
        Seeded: {seedCustomers.length} customers · {seedOrders.length} orders · {seedItems.length} items
      </p>
    </div>
  );
}

function DotTable({
  label,
  count,
  seeded,
  highlightAll,
}: {
  label: string;
  count: number;
  seeded: number[];
  highlightAll: boolean;
}) {
  const set = new Set(seeded);
  return (
    <div className="rounded-md border border-border bg-muted/20 p-2">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="font-medium text-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">{set.size}/{count}</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {Array.from({ length: count }).map((_, i) => (
          <span
            key={i}
            className={cn(
              "h-2 w-2 rounded-full transition-all",
              set.has(i) || highlightAll
                ? "bg-[hsl(var(--chart-2))] scale-110"
                : "bg-foreground/15",
            )}
          />
        ))}
      </div>
    </div>
  );
}
