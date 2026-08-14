"use client";

import { AudioLines, Search, ShieldCheck, Zap } from "lucide-react";

const EXAMPLES = [
  "क्यूबा की मुद्रा क्या है?",
  "हैरिसन फोर्ड के बेटे कौन हैं?",
  "मोलासेस बाढ़ में कितने लोगों की मौत हुई?",
  "What is the currency of Cuba?",
];

export function EmptyState({ onExample }: { onExample: (q: string) => void }) {
  return (
    <div className="animate-fade-in-up mx-auto flex w-full max-w-2xl flex-col items-center gap-8 py-10">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="glass flex h-16 w-16 items-center justify-center rounded-2xl border border-accent/30">
          <AudioLines className="h-8 w-8 text-accent" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-primary sm:text-3xl">
          Ask MSMARCO-XI by voice or text
        </h1>
        <p className="max-w-md text-sm leading-relaxed text-secondary">
          Multilingual retrieval-augmented generation. Voice in via Sarvam,
          retrieval over a FAISS index of MSMARCO-XI, grounded answers from Groq
          — all under a 200ms retrieval budget.
        </p>
      </div>

      <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onExample(q)}
            className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2.5 text-left text-xs text-secondary transition-colors hover:border-accent/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <Search className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
            {q}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[11px] text-muted">
        <span className="flex items-center gap-1.5">
          <Zap className="h-3.5 w-3.5 text-green" aria-hidden="true" /> 200ms retrieval target
        </span>
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="h-3.5 w-3.5 text-accent" aria-hidden="true" /> safety guardrails
        </span>
        <span className="flex items-center gap-1.5">
          <AudioLines className="h-3.5 w-3.5 text-gold" aria-hidden="true" /> Sarvam STT
        </span>
      </div>
    </div>
  );
}