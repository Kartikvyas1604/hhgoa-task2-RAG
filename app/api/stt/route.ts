import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  try {
    const fd = await request.formData();
    const file = fd.get("file") as File | null;
    if (!file) {
      return NextResponse.json({ error: "Missing audio file" }, { status: 400 });
    }
    const out = new FormData();
    out.append("file", file, file.name || "voice.webm");

    const res = await fetch(`${BACKEND}/api/stt`, {
      method: "POST",
      body: out,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Could not reach the RAG backend." },
      { status: 502 }
    );
  }
}