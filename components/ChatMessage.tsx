"use client";

import { AlertTriangle, Check, Sparkles, ShieldAlert, Mic } from "lucide-react";
import type { RagResult } from "@/lib/types";
import { LatencyBar } from "@/components/LatencyBar";
import { SourceCard } from "@/components/SourceCard";

export interface Msg {
  id: string;
  role: "user" | "assistant";
  content: string;
  result?: RagResult;
  via?: "text" | "voice";
}

const LANG_LABEL: Record<string, string> = {
  hi: "हिन्दी",
  en: "English",
  gu: "ગુજરાતી",
  mr: "मराठी",
};

export function ChatMessage({ msg }: { msg: Msg }) {
  if (msg.role === "user") {
    return (
      <div className="animate-msg-in flex justify-end">
        <div className="flex max-w-[85%] flex-col items-end gap-1.5 sm:max-w-[75%]">
          {msg.via === "voice" && msg.result?.transcript && (
            <span className="flex items-center gap-1 text-[11px] text-muted">
              <Mic className="h-3 w-3" aria-hidden="true" />
              {msg.result.transcript}
            </span>
          )}
          <div className="rounded-2xl rounded-br-md border border-accent/25 bg-elevated px-4 py-2.5 text-sm text-primary">
            {msg.content}
          </div>
        </div>
      </div>
    );
  }

  const r = msg.result;
  const refused = r?.refused;
  const showSources =
    !!r && r.sources.length > 0 && (!refused || r.reason === "not_grounded" || r.reason === "out_of_corpus");

  const refusalText =
    r?.reason === "unsafe_input"
      ? "This input contains blocked content and was refused."
      : r?.reason === "unsupported_language"
        ? "This system is trained on Hindi, English, Gujarati and Marathi only — questions in other languages are refused."
        : r?.reason === "warming_up"
          ? "The RAG models are still loading — wait a moment and try again."
          : r?.reason === "out_of_corpus"
            ? "This question is outside the indexed corpus (below the confidence threshold), so the system refuses to guess."
            : r?.reason === "not_grounded"
              ? "No grounded answer was found in the retrieved passages, so the system refuses to hallucinate. Try a question about a topic in the corpus, or rephrase it."
              : r?.reason === "backend_unreachable"
                ? "The RAG backend is not running."
                : r?.answer || "Refused by safety checks.";

  return (
    <div className="animate-msg-in flex justify-start">
      <div className="flex w-full max-w-[92%] flex-col gap-2 sm:max-w-[85%]">
        {refused ? (
          <div className="flex items-start gap-2 rounded-2xl rounded-bl-md border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div className="flex flex-col gap-0.5">
              <span className="font-medium">Guardrail blocked</span>
              <span className="text-xs text-secondary">{refusalText}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2 rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-3">
            {r?.extractive && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-green">
                <Check className="h-3 w-3" aria-hidden="true" />
                answered directly from a gold passage (no LLM call)
              </span>
            )}
            {r?.latency?.lang && !refused && (
              <span className="text-[10px] uppercase tracking-widest text-accent">
                {LANG_LABEL[r.latency.lang] ?? r.latency.lang}
              </span>
            )}
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-primary">
              {r?.answer ?? msg.content}
            </p>
            {r?.guardrails?.some((g) => g.caveated) && (
              <span className="flex items-center gap-1.5 text-xs text-gold">
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                Low-confidence answer — verify independently.
              </span>
            )}
            {r?.latency && (
              <div className="mt-1">
                <LatencyBar
                  stages={r.latency.stages ?? {}}
                  total={r.latency.end_to_end_ms ?? r.latency.total_ms}
                />
              </div>
            )}
          </div>
        )}

        {showSources && (
          <div className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted">
              <Sparkles className="h-3 w-3" aria-hidden="true" />
              retrieved passages
            </span>
            <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
              {r.sources.slice(0, 4).map((s, i) => (
                <SourceCard key={`${s.id}-${i}`} source={s} />
              ))}
            </div>
          </div>
        )}

        {r && (r.latency?.cached || r.latency?.refused) && (
          <div className="flex gap-2 text-[10px] text-muted">
            {r.latency.cached && <span>cached</span>}
            {r.latency.refused && <span>refused</span>}
          </div>
        )}
      </div>
    </div>
  );
}