"use client";

import type { BackendStatus } from "@/lib/types";

export function StatusBadge({
  status,
  loading,
}: {
  status: BackendStatus | null;
  loading: boolean;
}) {
  if (loading || !status) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-secondary">
        <span className="skeleton h-2 w-2 rounded-full" />
        checking backend…
      </span>
    );
  }
  if (!status.ready) {
    const offline = status.error === "backend_unreachable";
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-danger/30 bg-danger/10 px-3 py-1 text-xs text-danger">
        <span className="h-2 w-2 rounded-full bg-danger" />
        {offline ? "backend offline" : status.loading ? "loading models…" : "initializing"}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-green/30 bg-green/10 px-3 py-1 text-xs text-green">
      <span className="h-2 w-2 animate-pulse rounded-full bg-green" />
      online · {status.chunks?.toLocaleString() ?? "—"} chunks
    </span>
  );
}