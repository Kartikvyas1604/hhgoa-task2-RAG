"use client";

import { useEffect, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import type { LatencyStats } from "@/lib/types";
import { fetchLatency } from "@/lib/api";

const METRIC_LABELS: Record<string, string> = {
  total_ms: "Total (RAG)",
  end_to_end_ms: "End-to-end",
  retrieval_only_ms: "Retrieval only",
  full_pipeline_ms: "Full pipeline",
  cache_hit_ms: "Cache hit",
};

export function LatencyPanel() {
  const [stats, setStats] = useState<LatencyStats | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      setStats(await fetchLatency());
    } catch {
      setStats(null);
    } finally {
      setLoading(false);
    }
  }

  function refreshClick() {
    setLoading(true);
    void refresh();
  }

  useEffect(() => {
    // Polling external latency stats — setState only in async callbacks
    // (known rule false positive for fetch-on-mount + interval).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  const pct = stats?.percentiles_ms ?? {};
  const bench = stats?.benchmark_report;

  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-primary">
          <Activity className="h-4 w-4 text-accent" aria-hidden="true" />
          Latency analytics
        </h2>
        <button
          type="button"
          onClick={refreshClick}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-xs text-secondary transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          refresh
        </button>
      </header>

      {loading && !stats ? (
        <div className="flex flex-col gap-2">
          <div className="skeleton h-8 rounded-md" />
          <div className="skeleton h-24 rounded-md" />
        </div>
      ) : stats && stats.count > 0 ? (
        <>
          <div className="grid grid-cols-3 gap-2">
            {["p50", "p70", "p100"].map((p) => (
              <div
                key={p}
                className="flex flex-col gap-0.5 rounded-lg border border-border bg-surface px-3 py-2"
              >
                <span className="text-[10px] uppercase tracking-wider text-muted">
                  P{p.slice(1)}
                </span>
                <span
                  className={`font-mono text-lg font-semibold ${
                    (pct[p] ?? 0) <= 200 ? "text-green" : "text-gold"
                  }`}
                >
                  {Math.round(pct[p] ?? 0)}
                  <span className="text-xs text-muted">ms</span>
                </span>
              </div>
            ))}
          </div>
          {stats.stages_ms && (
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-surface px-3 py-2">
              {Object.entries(stats.stages_ms)
                .sort((a, b) => (b[1].p50 ?? 0) - (a[1].p50 ?? 0))
                .map(([stage, v]) => (
                  <div key={stage} className="flex items-center justify-between text-xs">
                    <span className="text-secondary">{stage}</span>
                    <span className="font-mono text-muted">
                      {Math.round(v.p50)}ms p50 · {Math.round(v.p100)}ms p100
                    </span>
                  </div>
                ))}
            </div>
          )}
          <p className="text-[11px] text-muted">
            {stats.count} queries ·{" "}
            {stats.cached_count ?? 0} cached · {stats.refused_count ?? 0} refused
            {stats.note ? ` · ${stats.note}` : ""}
          </p>
        </>
      ) : stats && stats.count === 0 ? (
        <div className="rounded-lg border border-border bg-surface px-4 py-3 text-xs text-secondary">
          No queries yet. Ask a question to start collecting latency data.
        </div>
      ) : (
        <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-xs text-danger">
          Backend unreachable — start <code className="font-mono">python server.py</code>.
        </div>
      )}

      {bench?.pipeline && (
        <div className="flex flex-col gap-1 rounded-lg border border-border bg-elevated px-3 py-2">
          <span className="text-[10px] uppercase tracking-wider text-muted">
            benchmark · {bench.n_queries ?? "—"} queries · target 200ms
          </span>
          {Object.entries(bench.pipeline).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-xs">
              <span className="text-secondary">
                {METRIC_LABELS[k] ?? k}
              </span>
              <span className="font-mono text-muted">
                {v.p50 != null && `p50 ${Math.round(v.p50)}ms · `}
                {v.p70 != null && `p70 ${Math.round(v.p70)}ms · `}
                p100 {Math.round(v.p100 ?? 0)}ms
              </span>
            </div>
          ))}
          {bench.accuracy && (
            <p className="text-[11px] text-muted">
              gold recall@k: {bench.accuracy.gold_recall_at_k ?? "—"}
              {bench.accuracy.mrr_at_k != null && ` · MRR@k: ${bench.accuracy.mrr_at_k}`}
            </p>
          )}
          {bench.per_language_ms && (
            <div className="flex flex-col gap-0.5 border-t border-border pt-1.5">
              {Object.entries(bench.per_language_ms).map(([lang, v]) => (
                <div key={lang} className="flex items-center justify-between text-[11px]">
                  <span className="text-secondary">{lang.toUpperCase()}</span>
                  <span className="font-mono text-muted">
                    p50 {Math.round(v.full_pipeline?.p50 ?? 0)}ms · p100{" "}
                    {Math.round(v.full_pipeline?.p100 ?? 0)}ms
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}