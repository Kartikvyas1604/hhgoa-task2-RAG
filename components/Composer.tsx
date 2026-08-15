"use client";

import { useCallback, useState } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { MicButton } from "@/components/MicButton";
import { LanguageSelector } from "@/components/LanguageSelector";
import { useRecorder } from "@/lib/useRecorder";

export function Composer({
  onSend,
  onVoice,
  busy,
  disabled,
  lang,
  onLangChange,
}: {
  onSend: (text: string) => void;
  onVoice: (blob: Blob) => void;
  busy: boolean;
  disabled: boolean;
  lang: string;
  onLangChange: (v: string) => void;
}) {
  const [text, setText] = useState("");
  const [waitingForStop, setWaitingForStop] = useState(false);
  const { isRecording, error, level, start, stop } = useRecorder();

  const submit = useCallback(() => {
    const t = text.trim();
    if (!t || busy) return;
    setText("");
    onSend(t);
  }, [text, busy, onSend]);

  const handleVoiceStart = useCallback(async () => {
    await start();
  }, [start]);

  const handleVoiceStop = useCallback(async () => {
    setWaitingForStop(true);
    try {
      const blob = await stop();
      if (blob) await onVoice(blob);
    } finally {
      setWaitingForStop(false);
    }
  }, [stop, onVoice]);

  return (
    <div className="flex flex-col gap-1.5">
      <LanguageSelector value={lang} onChange={onLangChange} disabled={busy || disabled} />
      <div className="glass flex items-end gap-2 rounded-2xl border border-border p-2 focus-within:border-accent/40">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          rows={1}
          placeholder={isRecording ? "Listening…" : "Ask a question in any supported language…"}
          disabled={busy || disabled || isRecording}
          aria-label="Your question"
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none"
        />
        <MicButton
          isRecording={isRecording}
          level={level}
          onStart={handleVoiceStart}
          onStop={handleVoiceStop}
          disabled={busy || disabled || (waitingForStop && !isRecording)}
        />
        <button
          type="button"
          onClick={submit}
          disabled={busy || disabled || !text.trim() || isRecording}
          aria-label="Send"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-all hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <ArrowUp className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>
      <p className="min-h-4 px-1 text-[11px] text-muted" aria-live="polite">
        {isRecording
          ? "Recording — tap the red square to stop."
          : waitingForStop
            ? "Processing audio…"
            : error
              ? error
              : "Enter to send · Shift+Enter for a new line · or hold the mic"}
      </p>
    </div>
  );
}