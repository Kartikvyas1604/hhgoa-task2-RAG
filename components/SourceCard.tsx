"use client";

import { FileText, CheckCircle2 } from "lucide-react";
import type { Source } from "@/lib/types";

const LANG_LABELS: Record<string, string> = {
  hi: "हिन्दी",
  en: "English",
  as: "অসমীয়া",
  bn: "বাংলা",
  gu: "ગુજરાતી",
  kn: "ಕನ್ನಡ",
  ml: "മലയാളം",
  mr: "मराठी",
  ne: "नेपाली",
  or: "ଓଡ଼ିଆ",
  pa: "ਪੰਜਾਬੀ",
  sa: "संस्कृतम्",
  ta: "தமிழ்",
  te: "తెలుగు",
  ur: "اردو",
};

export function SourceCard({ source }: { source: Source }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-elevated p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[11px] font-medium text-secondary">
          <FileText className="h-3 w-3" aria-hidden="true" />
          {LANG_LABELS[source.lang] ?? source.lang}
        </span>
        <span className="flex items-center gap-2 text-[11px]">
          {source.is_gold && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green/10 px-1.5 py-0.5 text-green">
              <CheckCircle2 className="h-3 w-3" aria-hidden="true" /> gold
            </span>
          )}
          <span className="font-mono text-muted">
            conf {source.score.toFixed(2)}
          </span>
        </span>
      </div>
      <p className="line-clamp-3 text-xs leading-relaxed text-secondary">
        {source.snippet}
      </p>
      {source.query_id != null && (
        <span className="font-mono text-[10px] text-muted">
          qid {source.query_id} · {source.chunk_type}
        </span>
      )}
    </div>
  );
}