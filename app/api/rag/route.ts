import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  const body = await request.json();
  try {
    const res = await fetch(`${BACKEND}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json();
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
    return NextResponse.json(data, { status: res.status });
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