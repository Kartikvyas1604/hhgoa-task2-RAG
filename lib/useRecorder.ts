"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseRecorderReturn {
  isRecording: boolean;
  error: string | null;
  level: number;
  start: () => Promise<void>;
  stop: () => Promise<Blob | null>;
}

function writeStr(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

function buildWav(samples: Float32Array, srcRate: number): Blob {
  const targetRate = 16000;
  const ratio = srcRate / targetRate;
  const newLen = Math.max(1, Math.floor(samples.length / ratio));
  const out = new Float32Array(newLen);
  for (let i = 0; i < newLen; i++) {
    const idx = i * ratio;
    const i0 = Math.floor(idx);
    const frac = idx - i0;
    const i1 = Math.min(i0 + 1, samples.length - 1);
    out[i] = samples[i0] * (1 - frac) + samples[i1] * frac;
  }

  const buf = new ArrayBuffer(44 + out.length * 2);
  const view = new DataView(buf);
  writeStr(view, 0, "RIFF");
  view.setUint32(4, 36 + out.length * 2, true);
  writeStr(view, 8, "WAVE");
  writeStr(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetRate, true);
  view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(view, 36, "data");
  view.setUint32(40, out.length * 2, true);

  let off = 44;
  for (let i = 0; i < out.length; i++) {
    const s = Math.max(-1, Math.min(1, out[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    off += 2;
  }
  return new Blob([buf], { type: "audio/wav" });
}

export function useRecorder(): UseRecorderReturn {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
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

      let ctx: AudioContext;
      try {
        ctx = new AudioContext({ sampleRate: 16000 });
      } catch {
        ctx = new AudioContext();
      }
      audioCtxRef.current = ctx;
      if (ctx.state === "suspended") await ctx.resume();

      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;

      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        const ch = e.inputBuffer.getChannelData(0);
        chunksRef.current.push(new Float32Array(ch));
      };
      // Connect into a live graph without audible monitoring so the processor fires.
      const sink = ctx.createMediaStreamDestination();
      src.connect(analyser);
      analyser.connect(processor);
      processor.connect(sink);

      processorRef.current = processor;
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

      setIsRecording(true);
    } catch {
      setError(
        "Microphone access denied. Check browser permissions or use text input."
      );
    }
  }, []);

  const stop = useCallback(async (): Promise<Blob | null> => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    setLevel(0);

    const ctx = audioCtxRef.current;
    const chunks = chunksRef.current;
    const hadAudio = chunks.length > 0;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    processorRef.current?.disconnect();
    analyserRef.current?.disconnect();
    audioCtxRef.current?.close().catch(() => {});
    streamRef.current = null;
    processorRef.current = null;
    analyserRef.current = null;
    audioCtxRef.current = null;
    setIsRecording(false);

    if (!hadAudio || !ctx) return null;

    let total = 0;
    for (const c of chunks) total += c.length;
    const merged = new Float32Array(total);
    let offset = 0;
    for (const c of chunks) {
      merged.set(c, offset);
      offset += c.length;
    }

    const rate = ctx.sampleRate || 16000;
    return buildWav(merged, rate);
  }, []);

  return { isRecording, error, level, start, stop };
}