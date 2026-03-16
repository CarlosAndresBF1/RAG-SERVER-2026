/* API response types matching the RAG backend Pydantic schemas. */

// ── Stats ─────────────────────────────────────────────────────────────

export interface StatsOverview {
  total_documents: number;
  total_chunks: number;
  ingests_per_day: { date: string; count: number }[];
}

export interface CoverageCell {
  message_type: string;
  source_type: string;
  chunk_count: number;
}

export interface CoverageData {
  matrix: CoverageCell[];
  message_types: string[];
  source_types: string[];
}

export interface FeedbackRow {
  id: string;
  query: string;
  rating: number;
  comment: string | null;
  tool_name: string | null;
  chunk_ids: string[];
  created_at: string | null;
}

export interface FeedbackTrendPoint {
  date: string;
  count: number;
  avg_rating: number;
}

export interface FeedbackStats {
  total: number;
  average_rating: number;
  positivity_rate: number;
  distribution: {
    positive: number;
    neutral: number;
    negative: number;
  };
  trend: FeedbackTrendPoint[];
  rows: FeedbackRow[];
  page: number;
  page_size: number;
}

export interface DbStats {
  database_size: string;
  row_counts: Record<string, number>;
  table_sizes: { table: string; size: string }[];
}

// ── Sources ───────────────────────────────────────────────────────────

export interface SourceItem {
  id: string;
  source_path: string;
  source_type: string;
  file_hash: string;
  total_chunks: number;
  is_current: boolean;
  ingested_at: string;
}

export interface SourceListResponse {
  items: SourceItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChunkSummary {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  section: string | null;
  subsection: string | null;
  metadata: Record<string, unknown>;
}

export interface SourceDetailResponse {
  id: string;
  source_path: string;
  source_type: string;
  file_hash: string;
  total_chunks: number;
  is_current: boolean;
  ingested_at: string;
  chunks: ChunkSummary[];
}

// ── Jobs ──────────────────────────────────────────────────────────────

export interface IngestJob {
  id: string;
  source_path: string;
  source_type: string;
  status: "pending" | "running" | "completed" | "failed";
  chunks_created: number;
  error_message: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobsResponse {
  total: number;
  limit: number;
  offset: number;
  jobs: IngestJob[];
}

// ── Search ────────────────────────────────────────────────────────────

export interface Citation {
  source_path: string;
  section: string;
  chunk_index: number;
}

export interface EvidenceItem {
  text: string;
  relevance: number;
  citations: Citation[];
  message_type: string | null;
  source_type: string | null;
}

export interface SearchResponse {
  query: string;
  evidence: EvidenceItem[];
  gaps: string[];
  followups: string[];
  metadata: {
    total_candidates: number;
    search_time_ms: number;
  };
}

// ── Tokens ────────────────────────────────────────────────────────────

export interface McpToken {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  usage_count: number;
  rate_limit_rpm: number;
  created_at: string;
  revoked_at: string | null;
}

export interface TokenAuditEntry {
  id: string;
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  tool_name: string | null;
  created_at: string;
}

// ── Health ────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  services: {
    database: string;
    embedding_model: string;
    reranker: string;
  };
}

// ── Upload ────────────────────────────────────────────────────────────

export interface UploadResponse {
  filename: string;
  size_bytes: number;
  path: string;
}

// ── Ingest ────────────────────────────────────────────────────────────

export interface IngestResponse {
  status: "completed" | "skipped" | "failed";
  document_id: string | null;
  source_path: string;
  source_type: string | null;
  chunks_created: number | null;
  duration_ms: number;
  reason: string | null;
  error: string | null;
}
