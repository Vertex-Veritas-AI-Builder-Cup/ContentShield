"use client";

import { FormEvent, useEffect, useState } from "react";
import { MatchedSegment, ScanMatch } from "@/components/MatchResults";

type VerdictExplanation = {
  verdict_explanation_id: string;
  decision: "likely_match" | "uncertain" | "not_enough_evidence";
  explanation: string;
  confidence_note: string;
  evidence: EvidenceItem[];
  limitations: string[];
  model: string;
  created_at: string;
};

type EvidenceItem = {
  query_start_seconds: number;
  query_end_seconds: number;
  protected_start_seconds: number;
  protected_end_seconds: number;
  observation: string;
};

type ScanDetail = {
  scan_id: string;
  source_filename?: string;
  top_match: ScanMatch | null;
  verdict_explanation?: VerdictExplanation | null;
  dmca_draft?: DmcaDraft | null;
  media?: {
    protected_video_url?: string | null;
    suspicious_video_url?: string | null;
  };
  protected_clip?: { title?: string; creator_name?: string } | null;
};

type DmcaDraft = {
  draft_id: string;
  subject: string;
  body: string;
  disclaimer: string;
};

type Props = {
  scanId: string | null;
  topMatch: ScanMatch | null;
};

/** Format seconds so evidence cards are easy to scan at a glance. */
function timestamp(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${value.toFixed(1)}s`;
}

/** Render one timestamp range from the scan's retrieval result. */
function SegmentSummary({ segment }: { segment: MatchedSegment }) {
  return (
    <span>
      Suspicious {timestamp(segment.query_start_offset_seconds)}–
      {timestamp(segment.query_end_offset_seconds)} · original{" "}
      {timestamp(segment.protected_start_offset_seconds)}–
      {timestamp(segment.protected_end_offset_seconds)}
    </span>
  );
}

/** Fetch and render the explanation, evidence media, and reviewable draft for one scan. */
export function VerdictExplanationPanel({ scanId, topMatch }: Props) {
  const [detail, setDetail] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatorName, setCreatorName] = useState("");
  const [creatorEmail, setCreatorEmail] = useState("");
  const [platform, setPlatform] = useState("");
  const [originalUrl, setOriginalUrl] = useState("");
  const [infringingUrl, setInfringingUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  useEffect(() => {
    if (!scanId) {
      return;
    }

    /** Load persisted scan detail whenever the selected scan changes. */
    async function loadDetail() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${apiUrl}/api/scans/${scanId}`);
        const body = (await response.json()) as ScanDetail & { detail?: string };
        if (!response.ok) throw new Error(body.detail || "Could not load scan detail.");
        setDetail(body);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load scan detail.");
      } finally {
        setLoading(false);
      }
    }

    void loadDetail();
  }, [apiUrl, scanId]);

  /** Ask the backend to create a grounded verdict explanation for the top match. */
  async function explainVerdict() {
    if (!scanId) return;
    setExplaining(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/scans/${scanId}/explain-verdict`, {
        method: "POST",
      });
      const body = (await response.json()) as {
        verdict_explanation?: VerdictExplanation;
        detail?: string;
      };
      if (!response.ok || !body.verdict_explanation) {
        throw new Error(body.detail || "Could not explain this verdict.");
      }
      setDetail((current) =>
        current ? { ...current, verdict_explanation: body.verdict_explanation } : current,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not explain this verdict.");
    } finally {
      setExplaining(false);
    }
  }

  /** Generate a deterministic DMCA draft using the stored scan evidence. */
  async function createDraft(event: FormEvent) {
    event.preventDefault();
    if (!scanId) return;
    setDrafting(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/scans/${scanId}/dmca`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          creator_name: creatorName,
          creator_email: creatorEmail,
          platform,
          original_url: originalUrl,
          infringing_url: infringingUrl,
        }),
      });
      const body = (await response.json()) as { dmca_draft?: DmcaDraft; detail?: string };
      if (!response.ok || !body.dmca_draft) {
        throw new Error(body.detail || "Could not create the draft.");
      }
      setDetail((current) => (current ? { ...current, dmca_draft: body.dmca_draft } : current));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the draft.");
    } finally {
      setDrafting(false);
    }
  }

  /** Copy the generated draft body so a creator can paste it into a platform form. */
  async function copyDraft() {
    if (!detail?.dmca_draft) return;
    await navigator.clipboard.writeText(detail.dmca_draft.body);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  if (!scanId) return null;
  const explanation = detail?.verdict_explanation;
  const media = detail?.media;

  return (
    <section className="mt-8 rounded-2xl border border-white/10 bg-[#181816] p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-[#9b958c]">Verdict explanation</p>
          <h2 className="mt-2 text-xl font-medium">Evidence for this match</h2>
          <p className="mt-1 text-sm text-[#9b958c]">
            This is an automated assessment, not a legal verdict.
          </p>
        </div>
        <button
          type="button"
          onClick={explainVerdict}
          disabled={explaining || loading || !topMatch}
          className="rounded-full bg-[#f4f1ea] px-4 py-2 text-sm font-medium text-[#10100e] disabled:opacity-40"
        >
          {explaining ? "Explaining…" : explanation ? "Refresh explanation" : "Explain verdict"}
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-[#f0b429]">{error}</p>}

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {[
          ["Protected original", media?.protected_video_url, detail?.protected_clip?.title],
          ["Suspicious upload", media?.suspicious_video_url, detail?.source_filename],
        ].map(([label, url, title]) => (
          <div key={label} className="overflow-hidden rounded-xl border border-white/10 bg-[#10100e]">
            {url ? (
              <video src={url} controls className="aspect-video w-full bg-black object-contain" />
            ) : (
              <div className="flex aspect-video items-center justify-center text-xs text-[#6f6a62]">
                Video preview unavailable locally
              </div>
            )}
            <div className="p-3">
              <p className="text-xs text-[#9b958c]">{label}</p>
              <p className="mt-1 truncate text-sm">{title || "Untitled video"}</p>
            </div>
          </div>
        ))}
      </div>

      {topMatch?.matched_segments && topMatch.matched_segments.length > 0 && (
        <div className="mt-5">
          <h3 className="text-sm font-medium">Retrieved matching segments</h3>
          <ul className="mt-2 space-y-2 text-xs text-[#9b958c]">
            {topMatch.matched_segments.map((segment, index) => (
              <li key={`${segment.query_segment_id || "segment"}-${index}`}>
                <SegmentSummary segment={segment} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {explanation && (
        <div className="mt-6 border-t border-white/10 pt-5">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-lg font-medium">{explanation.decision.replaceAll("_", " ")}</h3>
            <span className="text-xs text-[#9b958c]">{explanation.model}</span>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#d4d0c8]">{explanation.explanation}</p>
          <p className="mt-2 text-xs text-[#9b958c]">{explanation.confidence_note}</p>
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {explanation.evidence.map((item, index) => (
              <article key={`${item.query_start_seconds}-${index}`} className="rounded-xl border border-white/10 p-4">
                <p className="text-xs text-[#f0b429]">
                  Suspicious {timestamp(item.query_start_seconds)}–{timestamp(item.query_end_seconds)} · original{" "}
                  {timestamp(item.protected_start_seconds)}–{timestamp(item.protected_end_seconds)}
                </p>
                <p className="mt-2 text-sm text-[#d4d0c8]">{item.observation}</p>
              </article>
            ))}
          </div>
          {explanation.limitations.length > 0 && (
            <div className="mt-4 rounded-xl bg-white/[0.03] p-4 text-xs text-[#9b958c]">
              <p className="font-medium text-[#d4d0c8]">Limitations</p>
              <ul className="mt-2 list-disc space-y-1 pl-4">
                {explanation.limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      <form onSubmit={createDraft} className="mt-6 border-t border-white/10 pt-5">
        <div>
          <h3 className="text-lg font-medium">Prepare a reviewable notice draft</h3>
          <p className="mt-1 text-xs text-[#9b958c]">Optional details help personalize the draft.</p>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {[
            ["Creator name", creatorName, setCreatorName],
            ["Creator email", creatorEmail, setCreatorEmail],
            ["Platform", platform, setPlatform],
            ["Original URL", originalUrl, setOriginalUrl],
            ["Suspicious URL", infringingUrl, setInfringingUrl],
          ].map(([label, value, setter]) => (
            <input
              key={label as string}
              value={value as string}
              onChange={(event) => (setter as (value: string) => void)(event.target.value)}
              placeholder={label as string}
              className="rounded-lg border border-white/10 bg-[#10100e] px-3 py-2 text-sm outline-none placeholder:text-[#6f6a62] focus:border-white/30"
            />
          ))}
        </div>
        <button
          type="submit"
          disabled={drafting || !explanation}
          className="mt-3 rounded-full border border-white/20 px-4 py-2 text-sm disabled:opacity-40"
        >
          {drafting ? "Preparing…" : "Generate DMCA draft"}
        </button>
      </form>

      {detail?.dmca_draft && (
        <article className="mt-5 rounded-xl border border-[#f0b429]/30 bg-[#f0b429]/[0.05] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-medium">{detail.dmca_draft.subject}</h3>
            <button type="button" onClick={copyDraft} className="text-xs text-[#f0b429]">
              {copied ? "Copied" : "Copy draft"}
            </button>
          </div>
          <pre className="mt-4 whitespace-pre-wrap font-sans text-sm leading-6 text-[#d4d0c8]">
            {detail.dmca_draft.body}
          </pre>
          <p className="mt-4 text-xs text-[#f0b429]">{detail.dmca_draft.disclaimer}</p>
        </article>
      )}
    </section>
  );
}
