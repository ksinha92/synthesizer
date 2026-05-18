"use client";

import { cn } from "@/lib/utils";
import type { IllustrationKind } from "@/content/help-content";

interface IllustrationProps {
  kind: IllustrationKind;
  accent?: string; // chart-N CSS var key, e.g. "--chart-3"
  className?: string;
}

/** Animated SVG illustrations sized to fill their parent. Each one is a small,
 *  hand-tuned scene that fits the topic and uses the design-system chart colors. */
export function Illustration({ kind, accent = "--chart-1", className }: IllustrationProps) {
  const stroke = `hsl(var(${accent}))`;
  return (
    <div className={cn("relative h-full w-full overflow-hidden rounded-xl bg-card", className)}>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-30 dark:opacity-40"
        style={{
          background: `radial-gradient(circle at 30% 30%, hsl(var(${accent}) / 0.35), transparent 60%), radial-gradient(circle at 70% 80%, hsl(var(--chart-3) / 0.18), transparent 50%)`,
        }}
      />
      <svg
        viewBox="0 0 320 200"
        className="relative h-full w-full"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label={`Illustration for ${kind}`}
      >
        {renderScene(kind, stroke)}
      </svg>
    </div>
  );
}

function renderScene(kind: IllustrationKind, stroke: string): React.ReactNode {
  switch (kind) {
    case "data-flow":
      return (
        <g>
          <defs>
            <linearGradient id="df-grad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={stroke} stopOpacity="0.1" />
              <stop offset="50%" stopColor={stroke} stopOpacity="0.8" />
              <stop offset="100%" stopColor={stroke} stopOpacity="0.1" />
            </linearGradient>
          </defs>
          <rect x="20" y="60" width="60" height="80" rx="10" stroke={stroke} strokeWidth="1.5" />
          <line x1="30" y1="80" x2="70" y2="80" stroke={stroke} strokeOpacity="0.5" strokeWidth="1" />
          <line x1="30" y1="100" x2="70" y2="100" stroke={stroke} strokeOpacity="0.5" strokeWidth="1" />
          <line x1="30" y1="120" x2="70" y2="120" stroke={stroke} strokeOpacity="0.5" strokeWidth="1" />
          <rect x="240" y="60" width="60" height="80" rx="10" stroke={stroke} strokeWidth="1.5" />
          <line x1="250" y1="80" x2="290" y2="80" stroke={stroke} strokeOpacity="0.5" strokeWidth="1" />
          <line x1="250" y1="100" x2="290" y2="100" stroke={stroke} strokeOpacity="0.5" strokeWidth="1" />
          <line x1="250" y1="120" x2="290" y2="120" stroke={stroke} strokeOpacity="0.5" strokeWidth="1" />
          <path d="M85 100 Q160 60 235 100" stroke="url(#df-grad)" strokeWidth="2.5" fill="none" />
          <circle cx="160" cy="80" r="3" fill={stroke}>
            <animate attributeName="cx" from="85" to="235" dur="2.5s" repeatCount="indefinite" />
            <animate attributeName="cy" values="100;80;100" dur="2.5s" repeatCount="indefinite" />
          </circle>
          <circle cx="160" cy="80" r="3" fill={stroke} opacity="0.6">
            <animate attributeName="cx" from="85" to="235" begin="-1.25s" dur="2.5s" repeatCount="indefinite" />
            <animate attributeName="cy" values="100;80;100" begin="-1.25s" dur="2.5s" repeatCount="indefinite" />
          </circle>
        </g>
      );

    case "shield-network":
      return (
        <g>
          <path d="M160 30 L210 60 V110 Q210 145 160 170 Q110 145 110 110 V60 Z" stroke={stroke} strokeWidth="2" />
          <path d="M140 105 l15 15 l30 -40" stroke={stroke} strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {[40, 80, 250, 280].map((cx, i) => (
            <g key={i}>
              <circle cx={cx} cy={50 + (i % 2) * 80} r="6" stroke={stroke} strokeWidth="1.5" />
              <line x1={cx} y1={50 + (i % 2) * 80} x2="160" y2="100" stroke={stroke} strokeOpacity="0.3" strokeDasharray="2 2" />
            </g>
          ))}
        </g>
      );

    case "scanner":
      return (
        <g>
          <rect x="40" y="40" width="240" height="120" rx="8" stroke={stroke} strokeWidth="1.5" />
          {Array.from({ length: 8 }).map((_, i) => (
            <line
              key={i}
              x1="50"
              y1={55 + i * 14}
              x2={50 + (i % 4) * 40 + 80}
              y2={55 + i * 14}
              stroke={stroke}
              strokeOpacity={0.2 + (i % 4) * 0.15}
              strokeWidth="2"
            />
          ))}
          <line x1="40" y1="100" x2="280" y2="100" stroke={stroke} strokeWidth="2">
            <animate attributeName="y1" values="40;160;40" dur="3s" repeatCount="indefinite" />
            <animate attributeName="y2" values="40;160;40" dur="3s" repeatCount="indefinite" />
          </line>
        </g>
      );

    case "mask-reveal":
      return (
        <g>
          <text x="40" y="80" fontFamily="ui-monospace, SFMono-Regular, monospace" fontSize="14" fill={stroke}>
            jane.doe@acme.com
          </text>
          <text x="40" y="130" fontFamily="ui-monospace, SFMono-Regular, monospace" fontSize="14" fill={stroke} opacity="0.5">
            ████████.███@███.███
          </text>
          <rect x="36" y="68" width="200" height="20" stroke={stroke} strokeOpacity="0.4" strokeDasharray="3 3" />
          <path d="M236 78 Q255 78 270 110 Q255 142 236 130" stroke={stroke} strokeWidth="1.5" fill="none" />
          <path d="M260 100 L270 110 L260 120" stroke={stroke} strokeWidth="1.5" fill="none" />
        </g>
      );

    case "synthetic-loop":
      return (
        <g>
          <circle cx="160" cy="100" r="55" stroke={stroke} strokeWidth="1.5" strokeDasharray="3 4" />
          <circle cx="160" cy="100" r="55" stroke={stroke} strokeWidth="2" strokeDasharray="20 200">
            <animateTransform attributeName="transform" type="rotate" from="0 160 100" to="360 160 100" dur="3s" repeatCount="indefinite" />
          </circle>
          {[0, 60, 120, 180, 240, 300].map((angle) => {
            const x = 160 + Math.cos((angle * Math.PI) / 180) * 75;
            const y = 100 + Math.sin((angle * Math.PI) / 180) * 75;
            return <circle key={angle} cx={x} cy={y} r="4" fill={stroke} opacity="0.7" />;
          })}
          <text x="160" y="105" textAnchor="middle" fontSize="11" fill={stroke} fontFamily="ui-monospace">
            synthesize
          </text>
        </g>
      );

    case "subset-slice":
      return (
        <g>
          <rect x="40" y="40" width="240" height="120" rx="6" stroke={stroke} strokeWidth="1.5" strokeOpacity="0.4" />
          {Array.from({ length: 12 }).map((_, i) => (
            <circle
              key={i}
              cx={60 + (i % 6) * 40}
              cy={70 + Math.floor(i / 6) * 30}
              r="6"
              stroke={stroke}
              strokeWidth="1"
              strokeOpacity={i < 5 ? 1 : 0.25}
              fill={i < 5 ? `${stroke}` : "transparent"}
              fillOpacity={i < 5 ? 0.3 : 0}
            />
          ))}
          {[0, 1, 2, 3].map((i) => (
            <line
              key={i}
              x1={60 + i * 40}
              y1="70"
              x2={60 + (i + 1) * 40}
              y2="70"
              stroke={stroke}
              strokeWidth="1.5"
            />
          ))}
          <path
            d="M50 60 Q90 50 130 60 L130 80 Q90 90 50 80 Z"
            stroke={stroke}
            strokeWidth="2"
            fill={stroke}
            fillOpacity="0.08"
          />
        </g>
      );

    case "workflow-graph":
      return (
        <g>
          {[60, 120, 180, 240].map((cx, i) => (
            <g key={i}>
              <circle cx={cx} cy={i % 2 === 0 ? 80 : 130} r="14" stroke={stroke} strokeWidth="1.5" fill="hsl(var(--card))" />
              <text x={cx} y={i % 2 === 0 ? 85 : 135} textAnchor="middle" fontSize="11" fill={stroke}>
                {i + 1}
              </text>
            </g>
          ))}
          <line x1="74" y1="80" x2="106" y2="130" stroke={stroke} strokeWidth="1.5" />
          <line x1="134" y1="130" x2="166" y2="80" stroke={stroke} strokeWidth="1.5" />
          <line x1="194" y1="80" x2="226" y2="130" stroke={stroke} strokeWidth="1.5" />
          <circle cx="74" cy="80" r="3" fill={stroke}>
            <animate attributeName="cx" values="74;106;134;166;194;226" dur="4s" repeatCount="indefinite" />
            <animate attributeName="cy" values="80;130;130;80;80;130" dur="4s" repeatCount="indefinite" />
          </circle>
        </g>
      );

    case "job-pipeline":
      return (
        <g>
          <rect x="40" y="85" width="240" height="30" rx="15" stroke={stroke} strokeWidth="1.5" />
          <rect x="44" y="89" width="120" height="22" rx="11" fill={stroke} fillOpacity="0.4">
            <animate attributeName="width" values="0;232;232" dur="2.5s" repeatCount="indefinite" />
          </rect>
          {[80, 130, 180, 230].map((cx, i) => (
            <circle key={i} cx={cx} cy="100" r="3" fill={stroke} />
          ))}
        </g>
      );

    case "report-doc":
      return (
        <g>
          <rect x="100" y="30" width="120" height="150" rx="8" stroke={stroke} strokeWidth="1.5" fill="hsl(var(--card))" />
          <line x1="115" y1="55" x2="195" y2="55" stroke={stroke} strokeWidth="2" />
          <line x1="115" y1="75" x2="205" y2="75" stroke={stroke} strokeOpacity="0.5" />
          <line x1="115" y1="90" x2="180" y2="90" stroke={stroke} strokeOpacity="0.5" />
          <line x1="115" y1="105" x2="205" y2="105" stroke={stroke} strokeOpacity="0.5" />
          <rect x="115" y="120" width="90" height="40" rx="4" stroke={stroke} strokeWidth="1" />
          <path d="M125 145 L135 155 L155 130" stroke={stroke} strokeWidth="2" fill="none" />
        </g>
      );

    case "ephemeral-bubble":
      return (
        <g>
          {[0, 60, 120].map((delay, i) => (
            <circle key={i} cx={80 + i * 80} cy="100" r="20" stroke={stroke} strokeWidth="1.5" fill="hsl(var(--card))">
              <animate
                attributeName="r"
                values="20;28;20"
                dur="3s"
                repeatCount="indefinite"
                begin={`${-delay / 60}s`}
              />
              <animate
                attributeName="opacity"
                values="1;0.4;1"
                dur="3s"
                repeatCount="indefinite"
                begin={`${-delay / 60}s`}
              />
            </circle>
          ))}
        </g>
      );

    case "preset-stamp":
      return (
        <g>
          <rect x="40" y="50" width="100" height="100" rx="12" stroke={stroke} strokeWidth="2" />
          <text x="90" y="105" textAnchor="middle" fontSize="14" fill={stroke}>preset</text>
          {[180, 220, 260].map((x, i) => (
            <g key={x}>
              <rect x={x} y={60 + i * 25} width="50" height="20" rx="4" stroke={stroke} strokeWidth="1" strokeOpacity="0.6" />
              <line x1={140} y1={70 + i * 25} x2={x} y2={70 + i * 25} stroke={stroke} strokeOpacity="0.3" strokeDasharray="2 2" />
            </g>
          ))}
        </g>
      );

    case "rule-pattern":
      return (
        <g>
          <text x="40" y="80" fontFamily="ui-monospace" fontSize="14" fill={stroke}>
            /^EMP-\d{"{6}"}$/
          </text>
          <line x1="40" y1="90" x2="230" y2="90" stroke={stroke} strokeWidth="1.5" />
          {["EMP-123456", "EMP-789012", "ACC-543210"].map((s, i) => (
            <text key={s} x="40" y={115 + i * 18} fontFamily="ui-monospace" fontSize="12" fill={stroke} fillOpacity={i < 2 ? 1 : 0.3}>
              {s} {i < 2 ? "✓" : "✗"}
            </text>
          ))}
        </g>
      );

    case "webhook-fan":
      return (
        <g>
          <circle cx="80" cy="100" r="18" stroke={stroke} strokeWidth="2" fill="hsl(var(--card))" />
          <text x="80" y="105" textAnchor="middle" fontSize="10" fill={stroke}>event</text>
          {[60, 100, 140].map((y) => (
            <g key={y}>
              <line x1="98" y1="100" x2="220" y2={y} stroke={stroke} strokeWidth="1.5" />
              <rect x="220" y={y - 12} width="60" height="24" rx="4" stroke={stroke} strokeWidth="1" />
              <circle cx="160" cy={(100 + y) / 2} r="3" fill={stroke}>
                <animate
                  attributeName="cx"
                  from="98"
                  to="220"
                  dur="2s"
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="cy"
                  from="100"
                  to={String(y)}
                  dur="2s"
                  repeatCount="indefinite"
                />
              </circle>
            </g>
          ))}
        </g>
      );

    case "admin-keys":
      return (
        <g>
          <circle cx="120" cy="100" r="22" stroke={stroke} strokeWidth="2" />
          <circle cx="120" cy="100" r="6" fill={stroke} />
          <line x1="142" y1="100" x2="220" y2="100" stroke={stroke} strokeWidth="3" />
          <line x1="200" y1="100" x2="200" y2="115" stroke={stroke} strokeWidth="3" />
          <line x1="215" y1="100" x2="215" y2="110" stroke={stroke} strokeWidth="3" />
          <text x="80" y="55" fontSize="11" fill={stroke} fillOpacity="0.7">
            users · roles · audit
          </text>
        </g>
      );

    case "project-tree":
      return (
        <g>
          <rect x="130" y="40" width="60" height="30" rx="6" stroke={stroke} strokeWidth="2" />
          <text x="160" y="60" textAnchor="middle" fontSize="11" fill={stroke}>Project</text>
          {[60, 160, 260].map((cx, i) => (
            <g key={cx}>
              <line x1="160" y1="70" x2={cx} y2="115" stroke={stroke} strokeWidth="1.5" />
              <rect x={cx - 25} y="115" width="50" height="24" rx="4" stroke={stroke} strokeWidth="1.2" />
              <text x={cx} y="131" textAnchor="middle" fontSize="9" fill={stroke}>
                {["conn", "policy", "jobs"][i]}
              </text>
              {[0, 1].map((j) => (
                <g key={j}>
                  <line x1={cx} y1="139" x2={cx - 12 + j * 24} y2="160" stroke={stroke} strokeOpacity="0.5" strokeWidth="1" />
                  <circle cx={cx - 12 + j * 24} cy="165" r="4" stroke={stroke} strokeWidth="1" fill="hsl(var(--card))" />
                </g>
              ))}
            </g>
          ))}
        </g>
      );

    default:
      return <circle cx="160" cy="100" r="40" stroke={stroke} strokeWidth="2" />;
  }
}
