"use client";

import { Languages } from "lucide-react";

const OPTIONS: { value: string; label: string; title: string }[] = [
  { value: "auto", label: "Auto", title: "Detect automatically" },
  { value: "hi", label: "हिन्दी", title: "Hindi" },
  { value: "en", label: "English", title: "English" },
  { value: "gu", label: "ગુજરાતી", title: "Gujarati" },
  { value: "mr", label: "मराठी", title: "Marathi" },
];

export function LanguageSelector({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 px-1" role="group" aria-label="Answer language">
      <Languages className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
      {OPTIONS.map((o) => {
        const active = value === o.value;
        return (
          <button
            key={o.value}
            type="button"
            title={o.title}
            disabled={disabled}
            onClick={() => onChange(o.value)}
            className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-40 ${
              active
                ? "border-accent/60 bg-accent/15 text-accent"
                : "border-border bg-surface text-secondary hover:border-accent/30 hover:text-primary"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}