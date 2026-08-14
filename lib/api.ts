import type {
  RagResult,
  BackendStatus,
  LatencyStats,
} from "@/lib/types";

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Request failed (${res.status})${text ? `: ${text}` : ""}`);
  }
  return (await res.json()) as T;
}

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return (await res.json()) as T;
}

export function queryRag(question: string, lang?: string, sessionId?: string) {
  return postJSON<RagResult>("/api/rag", {
    question,
    lang: lang || null,
    session_id: sessionId || null,
  });
}

export function voiceQuery(blob: Blob, lang?: string, sessionId?: string) {
  const fd = new FormData();
  fd.append("file", blob, "voice.webm");
  if (lang) fd.append("lang", lang);
  if (sessionId) fd.append("session_id", sessionId);
  return fetch("/api/voice", { method: "POST", body: fd }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Voice query failed (${res.status})${text ? `: ${text}` : ""}`);
    }
    return (await res.json()) as RagResult;
  });
}

export function fetchStatus() {
  return getJSON<BackendStatus>("/api/status");
}

export function fetchLatency() {
  return getJSON<LatencyStats>("/api/latency");
}