"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseRecorderReturn {
  isRecording: boolean;
  error: string | null;
  level: number;
  start: () => Promise<void>;
  stop: () => Promise<Blob | null>;
}

export function useRecorder(): UseRecorderReturn {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close().catch(() => {});
    };
  }, []);

  const start = useCallback(async () => {
    setError(null);
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(
        (t) => MediaRecorder.isTypeSupported(t)
      ) ?? "";
      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorderRef.current = rec;
      rec.start();

      try {
        const ctx = new AudioContext();
        const src = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        src.connect(analyser);
        audioCtxRef.current = ctx;
        analyserRef.current = analyser;
        const data = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(data);
          const avg = data.reduce((a, b) => a + b, 0) / data.length;
          setLevel(Math.min(1, avg / 180));
          rafRef.current = requestAnimationFrame(tick);
        };
        tick();
      } catch {
        /* analyser is optional polish */
      }

      setIsRecording(true);
    } catch {
      setError(
        "Microphone access denied. Check browser permissions or use text input."
      );
    }
  }, []);

  const stop = useCallback(async (): Promise<Blob | null> => {
    const rec = mediaRecorderRef.current;
    if (!rec) return null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    setLevel(0);

    return new Promise<Blob | null>((resolve) => {
      rec.onstop = () => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        audioCtxRef.current?.close().catch(() => {});
        streamRef.current = null;
        audioCtxRef.current = null;
        analyserRef.current = null;
        setIsRecording(false);
        const blob =
          chunksRef.current.length > 0
            ? new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" })
            : null;
        resolve(blob);
      };
      rec.stop();
    });
  }, []);

  return { isRecording, error, level, start, stop };
}