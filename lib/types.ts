export interface Source {
  id: string;
  lang: string;
  query_id: number | null;
  query: string;
  is_gold: boolean;
  chunk_type: string;
  score: number;
  snippet: string;
}

export interface StageTimings {
  embed?: number;
  retrieve?: number;
  rerank?: number;
  guard?: number;
  generate?: number;
  stt?: number;
}

export interface LatencyEntry {
  total_ms: number;
  end_to_end_ms?: number;
  cached?: boolean;
  extractive?: boolean;
  refused?: boolean;
  confidence?: number;
  stages?: StageTimings;
}

export interface Guardrail {
  refused: boolean;
  caveated?: boolean;
  detail?: string;
  reason?: string;
}

export interface RagResult {
  answer: string;
  refused: boolean;
  reason?: string | null;
  extractive?: boolean;
  sources: Source[];
  guardrails?: Guardrail[];
  transcript?: string;
  stt_language_code?: string | null;
  end_to_end_ms?: number;
  latency?: LatencyEntry;
}

export interface BackendStatus {
  ready: boolean;
  loading?: boolean;
  error?: string | null;
  chunks?: number;
  languages?: string[];
  embed_model?: string;
  generation_model?: string;
  stt_model?: string;
}

export interface BenchmarkReport {
  n_queries?: number;
  pipeline?: {
    retrieval_only_ms?: Record<string, number>;
    full_pipeline_ms?: Record<string, number>;
    cache_hit_ms?: Record<string, number>;
  };
  accuracy?: { gold_recall_at_k?: number; gold_retrieved?: string };
  target_ms?: number;
}

export interface LatencyStats {
  count: number;
  cached_count?: number;
  refused_count?: number;
  percentiles_ms?: Record<string, number>;
  stages_ms?: Record<string, { p50: number; p100: number; avg: number }>;
  benchmark_report?: BenchmarkReport;
  note?: string;
}

export interface LatencyBreakdown {
  total_ms: number;
  cached: boolean;
  extractive: boolean;
  refused: boolean;
  confidence: number | null;
  stages: StageTimings;
  end_to_end_ms?: number;
}