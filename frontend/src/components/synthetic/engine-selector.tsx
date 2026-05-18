"use client";

import { Zap, BarChart3, Brain } from "lucide-react";
import { useSyntheticStore } from "@/stores/synthetic-store";
import { cn } from "@/lib/utils";

const ENGINES = [
  { key: "faker", label: "Faker", subtitle: "Fast", speed: "~1K/sec", description: "Basic patterns", icon: Zap },
  { key: "statistical", label: "Statistical", subtitle: "Accurate", speed: "~100/sec", description: "Preserves distributions", icon: BarChart3 },
  { key: "llm", label: "LLM", subtitle: "Intelligent", speed: "~10/sec", description: "NLP prompt driven", icon: Brain },
] as const;

export function EngineSelector() {
  const { selectedEngine, setEngine } = useSyntheticStore();

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {ENGINES.map((engine) => (
        <button
          key={engine.key}
          onClick={() => setEngine(engine.key)}
          className={cn(
            "relative rounded-lg border p-4 text-left transition-all",
            selectedEngine === engine.key
              ? "border-primary bg-primary/5 shadow-sm"
              : "border-border hover:border-primary/50"
          )}
        >
          <engine.icon className={cn("h-6 w-6 mb-2", selectedEngine === engine.key ? "text-primary" : "text-muted-foreground")} />
          <h3 className="text-sm font-semibold text-foreground">{engine.label}</h3>
          <p className="text-xs text-primary font-medium">{engine.subtitle}</p>
          <p className="mt-1 text-xs text-muted-foreground">{engine.speed}</p>
          <p className="text-xs text-muted-foreground">{engine.description}</p>
        </button>
      ))}
    </div>
  );
}
