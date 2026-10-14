// Shapes shared by the Check page and the scan API.

export type Verdict = "high_risk" | "medium_risk" | "low_risk";

// One timestamped segment pair returned by the retrieval pipeline.
export type MatchedSegment = {
  query_segment_id?: string;
  protected_segment_id?: string;
  query_start_offset_seconds?: number;
  query_end_offset_seconds?: number;
  protected_start_offset_seconds?: number;
  protected_end_offset_seconds?: number;
  similarity?: number;
};

// One protected clip that a suspicious video was compared with.
export type ScanMatch = {
  protected_clip_id: string;
  protected_title?: string;
  content_similarity: number;
  verdict: Verdict;
  matched_segment_count?: number;
  segment_coverage?: number;
  matched_segments?: MatchedSegment[];
};

export type StyleMatchCandidate = {
  protected_clip_id: string;
  protected_title?: string;
  style_similarity: number;
  style_match?: boolean;
};

// The closest original in the independent clip-level style search.
export type StyleMatch = StyleMatchCandidate & {
  style_threshold?: number;
  other_style_matches?: StyleMatchCandidate[];
  disclaimer?: string;
};

// One timestamped reason the two clips look alike.
export type EvidenceItem = {
  query_start_seconds: number;
  query_end_seconds: number;
  protected_start_seconds: number;
  protected_end_seconds: number;
  observation: string;
};

// Gemini's written assessment. This is not a legal decision.
export type VerdictExplanation = {
  verdict_explanation_id: string;
  decision: "likely_match" | "uncertain" | "not_enough_evidence";
  explanation: string;
  confidence_note: string;
  evidence: EvidenceItem[];
  limitations: string[];
  model?: string;
  created_at?: string;
};

// A secondary creator-intelligence signal, never a copyright verdict.
export type StyleNotice = {
  type: "similar_style";
  protected_clip_id: string;
  protected_title?: string;
  style_similarity: number;
  message: string;
  disclaimer: string;
};

// A takedown notice draft the user can review, copy, or download.
export type DmcaDraft = {
  draft_id: string;
  subject: string;
  body: string;
  disclaimer: string;
  created_at?: string;
};

// Short-lived signed URLs returned by the scan detail endpoint.
export type ScanMedia = {
  suspicious_video_url?: string | null;
  protected_video_url?: string | null;
  style_original_video_url?: string | null;
};

// Full record for one check, including any saved explanation or draft.
export type ScanDetail = {
  scan_id: string;
  suspicious_clip_id?: string;
  source_filename?: string;
  scanned_at?: string;
  matches: ScanMatch[];
  top_match: ScanMatch | null;
  processing_ms?: number;
  style_evaluated?: boolean;
  style_skip_reason?: string | null;
  style_match?: StyleMatch | null;
  style_notice?: StyleNotice | null;
  verdict_explanation?: VerdictExplanation | null;
  dmca_draft?: DmcaDraft | null;
  promoted_clip_id?: string | null;
  promoted_title?: string | null;
  promoted_at?: string | null;
  media?: ScanMedia;
  // Kept as fallbacks for older API responses.
  suspicious_video_url?: string | null;
  protected_video_url?: string | null;
};

// Backend address. Falls back to the local API when no env value is set.
export function apiBase() {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

// Read a FastAPI error message, or use a plain fallback if the body is not text.
export async function errorMessage(res: Response, fallback: string) {
  const json = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof json.detail === "string" ? json.detail : fallback;
}
