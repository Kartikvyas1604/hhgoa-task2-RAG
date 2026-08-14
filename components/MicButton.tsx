"use client";

import { Mic, Square } from "lucide-react";

export function MicButton({
  isRecording,
  level,
  onStart,
  onStop,
  disabled,
}: {
  isRecording: boolean;
  level: number;
  onStart: () => void;
  onStop: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={isRecording ? onStop : onStart}
      disabled={disabled}
      aria-label={isRecording ? "Stop recording" : "Ask by voice"}
      title={isRecording ? "Stop recording" : "Ask by voice"}
      className={[
        "relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        isRecording
          ? "recording-pulse border-red/50 bg-red/20 text-red"
          : "border-border bg-elevated text-secondary hover:border-accent/40 hover:text-accent",
        disabled ? "cursor-not-allowed opacity-40" : "",
      ].join(" ")}
    >
      {isRecording && level > 0.02 && (
        <span
          className="pointer-events-none absolute bottom-1 left-1 right-1 mx-auto block rounded-full bg-red/50"
          style={{ height: `${Math.max(4, level * 18)}px`, width: 3 }}
          aria-hidden="true"
        />
      )}
      {isRecording ? (
        <Square className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Mic className="h-5 w-5" aria-hidden="true" />
      )}
    </button>
  );
}