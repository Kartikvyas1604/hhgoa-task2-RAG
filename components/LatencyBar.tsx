"use client";

import type { StageTimings } from "@/lib/types";

const STAGE_META: Record<string, { label: string; color: string }> = {
  stt: { label: "STT", color: "bg-info" },
  embed: { label: "Embed", color: "bg-blue" },
  retrieve: { label: "Retrieve", color: "bg-accent" },
  rerank: { label: "Rerank", color: "bg-accent-soft" },
  generate: { label: "LLM", color: "bg-gold" },
  guard: { label: "Guard", color: "bg-green" },
};

const STAGE_ORDER: (keyof StageTimings)[] = [
  "stt",
  "embed",
  "retrieve",
  "rerank",
  "generate",
  "guard",
];

export function LatencyBar({
  stages,
  total,
}: {
  stages: StageTimings;
  total: number;
}) {
  const entries = STAGE_ORDER.filter(
    (k) => typeof stages[k] === "number" && stages[k]! > 0
  ).map((k) => ({
    key: k,
    ...STAGE_META[k],
    ms: stages[k]!,
  }));

  if (entries.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="font-mono">{total.toFixed(0)}ms</span>
      </div>
    );
  }

  const sum = entries.reduce((a, b) => a + b.ms, 0);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-secondary">
          {total.toFixed(0)}ms total
        </span>
        <span className="text-[10px] uppercase tracking-wider text-muted">
          target 200ms
        </span>
      </div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-elevated">
        {entries.map((e) => (
          <span
            key={e.key}
            className={e.color}
            style={{ width: `${(e.ms / sum) * 100}%` }}
            title={`${e.label}: ${e.ms.toFixed(0)}ms`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {entries.map((e) => (
          <span key={e.key} className="flex items-center gap-1 text-[10px] text-muted">
            <span className={`h-1.5 w-1.5 rounded-full ${e.color}`} />
            {e.label} {e.ms.toFixed(0)}ms
          </span>
        ))}
      </div>
    </div>
  );
}