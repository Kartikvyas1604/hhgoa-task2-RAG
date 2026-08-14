"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AudioLines, Waves } from "lucide-react";
import type { BackendStatus, RagResult } from "@/lib/types";
import { fetchStatus, queryRag, voiceQuery } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { ChatMessage, type Msg } from "@/components/ChatMessage";
import { Composer } from "@/components/Composer";
import { EmptyState } from "@/components/EmptyState";
import { LatencyPanel } from "@/components/LatencyPanel";

let idCounter = 0;
const nextId = () => `m${Date.now()}-${idCounter++}`;
const sessionId =
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `s${Date.now()}`;

export default function Page() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputBusyRef = useRef(false);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await fetchStatus());
    } catch {
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    // Polling external backend status — setState happens in async .then/.finally
    // after await, so this is not a synchronous cascade (known rule false positive).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshStatus();
    const t = setInterval(refreshStatus, 5000);
    return () => clearInterval(t);
  }, [refreshStatus]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const pushUser = useCallback((content: string, via: "text" | "voice", result?: RagResult) => {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content, via, result },
    ]);
  }, []);

  const pushAssistant = useCallback((result: RagResult) => {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "assistant", content: result.answer, result },
    ]);
  }, []);

  const handleSend = useCallback(
    async (text: string) => {
      if (inputBusyRef.current) return;
      inputBusyRef.current = true;
      setBusy(true);
      pushUser(text, "text");
      try {
        const result = await queryRag(text, undefined, sessionId);
        pushAssistant(result);
      } catch {
        pushAssistant({
          answer: "Something went wrong talking to the backend.",
          refused: true,
          reason: "error",
          sources: [],
        });
      } finally {
        inputBusyRef.current = false;
        setBusy(false);
      }
    },
    [pushUser, pushAssistant]
  );

  const handleVoice = useCallback(
    async (blob: Blob) => {
      if (inputBusyRef.current) return;
      inputBusyRef.current = true;
      setBusy(true);
      try {
        const result = await voiceQuery(blob, undefined, sessionId);
        const transcript = result.transcript || "—";
        pushUser(transcript, "voice", result);
        pushAssistant(result);
      } catch {
        pushUser("—", "voice");
        pushAssistant({
          answer: "Voice processing failed — check the backend and try again.",
          refused: true,
          reason: "error",
          sources: [],
        });
      } finally {
        inputBusyRef.current = false;
        setBusy(false);
      }
    },
    [pushUser, pushAssistant]
  );

  const isEmpty = messages.length === 0;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-5 lg:grid lg:grid-cols-[1fr_320px] lg:gap-8 lg:py-8">
      {/* Chat column */}
      <main className="flex h-[calc(100dvh-9rem)] flex-col gap-3 lg:h-[calc(100dvh-6.5rem)]">
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="glass flex h-10 w-10 items-center justify-center rounded-xl border border-accent/30">
              <Waves className="h-5 w-5 text-accent" aria-hidden="true" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-sm font-semibold tracking-tight text-primary">
                ShabdVani
                <span className="ml-2 text-[10px] uppercase tracking-widest text-accent">
                  voice RAG
                </span>
              </h1>
              <span className="text-[11px] text-muted">
                MSMARCO-XI · FAISS · Sarvam · Groq
              </span>
            </div>
          </div>
          <StatusBadge status={status} loading={statusLoading} />
        </header>

        <div
          ref={scrollRef}
          className="card flex-1 overflow-y-auto p-4"
          aria-label="Conversation"
        >
          {isEmpty ? (
            <EmptyState onExample={handleSend} />
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((m) => (
                <ChatMessage key={m.id} msg={m} />
              ))}
              {busy && (
                <div className="animate-msg-in flex items-center gap-1.5 pl-1">
                  <span className="flex gap-1" aria-label="Thinking">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="thinking-dot h-1.5 w-1.5 rounded-full bg-accent"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </span>
                  <span className="text-xs text-muted">grounding an answer…</span>
                </div>
              )}
            </div>
          )}
        </div>

        <Composer
          onSend={handleSend}
          onVoice={handleVoice}
          busy={busy}
          disabled={!status?.ready}
        />
      </main>

      {/* Latency analytics column */}
      <aside className="hidden lg:block">
        <div className="sticky top-8">
          <LatencyPanel />
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-[11px] text-muted">
            <AudioLines className="h-3.5 w-3.5 shrink-0 text-gold" aria-hidden="true" />
            Voice flows through Sarvam STT → pipeline → grounded Groq answer.
          </div>
        </div>
      </aside>

      {/* Mobile latency panel */}
      <section className="lg:hidden">
        <LatencyPanel />
      </section>
    </div>
  );
}