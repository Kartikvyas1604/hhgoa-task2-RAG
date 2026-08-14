import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  try {
    const fd = await request.formData();
    const file = fd.get("file") as File | null;
    if (!file) {
      return NextResponse.json(
        { error: "Missing audio file" },
        { status: 400 }
      );
    }
    const out = new FormData();
    out.append("file", file, file.name || "voice.webm");
    const lang = fd.get("lang");
    const sessionId = fd.get("session_id");
    if (lang) out.append("lang", String(lang));
    if (sessionId) out.append("session_id", String(sessionId));

    const res = await fetch(`${BACKEND}/api/voice_query`, {
      method: "POST",
      body: out,
      cache: "no-store",
    });
    let data: unknown = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (res.status === 503) {
      return NextResponse.json(
        {
          answer:
            "The RAG models are still loading — this can take a minute or two on first start. Try again shortly.",
          refused: true,
          reason: "warming_up",
          sources: [],
        },
        { status: 200 }
      );
    }
    if (!res.ok) {
      // Surface the backend error (e.g. unsupported audio format) instead of a
      // misleading "backend unreachable" message.
      const detail =
        typeof data === "object" && data && "detail" in data
          ? String((data as { detail: unknown }).detail)
          : res.statusText;
      return NextResponse.json(
        {
          answer: `Voice processing failed: ${detail}`,
          refused: true,
          reason: "backend_error",
          sources: [],
        },
        { status: 200 }
      );
    }
    return NextResponse.json(data, { status: 200 });
  } catch {
    return NextResponse.json(
      {
        answer:
          "Could not reach the RAG backend. Make sure `python server.py` is running in RAG-code.",
        refused: true,
        reason: "backend_unreachable",
        sources: [],
      },
      { status: 200 }
    );
  }
}