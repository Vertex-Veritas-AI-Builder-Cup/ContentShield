"use client";

import { useState } from "react";
import { MatchResults } from "@/components/MatchResults";
import {
  EvidenceItem,
  ScanDetail,
  VerdictExplanation,
  apiBase,
  errorMessage,
} from "@/components/scanTypes";

// Plain labels for the three explanation decisions.
const decisionLabel: Record<VerdictExplanation["decision"], string> = {
  likely_match: "Likely match",
  uncertain: "Uncertain",
  not_enough_evidence: "Not enough evidence",
};

// Turn 10.25 into "10.3s" for the evidence cards.
function seconds(value: number) {
  return `${value.toFixed(1)}s`;
}

// A start and end time, such as "10.0s–15.0s".
function range(start: number, end: number) {
  return `${seconds(start)}–${seconds(end)}`;
}

// One video column: title, player, and the times that matched.
function VideoPanel({
  label,
  title,
  src,
  ranges,
}: {
  label: string;
  title: string;
  src: string | null;
  ranges: string[];
}) {
  return (
    <div>
      <p className="text-xs text-[#9b958c]">{label}</p>
      <p className="mt-1 truncate text-sm">{title}</p>
      {src ? (
        <video
          src={src}
          controls
          playsInline
          className="mt-3 max-h-80 w-full rounded-xl bg-black object-contain"
        />
      ) : (
        <div className="mt-3 flex min-h-40 items-center justify-center rounded-xl border border-dashed border-white/15 px-4 text-center text-xs text-[#9b958c]">
          The file is stored. A playback link is not ready yet.
        </div>
      )}
      {ranges.length > 0 ? (
        <ul className="mt-2 text-xs text-[#9b958c]">
          {ranges.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-[#6f6a62]">Timestamps show up after verification.</p>
      )}
    </div>
  );
}

/** Show one scan, its videos, and the verdict explanation. */
export function MatchDetail({
  detail,
  suspiciousUrl,
  suspiciousTitle,
}: {
  detail: ScanDetail | null;
  suspiciousUrl: string | null;
  suspiciousTitle: string | null;
}) {
  // Start from an explanation already saved on the scan.
  const [explanation, setExplanation] = useState<VerdictExplanation | null>(
    detail?.verdict_explanation ?? null,
  );
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);

  if (!detail) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-white/15 px-6 text-sm text-[#9b958c]">
        The match shows up here.
      </div>
    );
  }

  const evidence = explanation?.evidence ?? [];
  // Same evidence, split so each video panel shows its own times.
  const suspiciousRanges = evidence.map(
    (item) => `Checked ${range(item.query_start_seconds, item.query_end_seconds)}`,
  );
  const originalRanges = evidence.map(
    (item) => `Original ${range(item.protected_start_seconds, item.protected_end_seconds)}`,
  );
  // Prefer the file just dropped. Use an API link only if the page has one.
  const suspiciousSrc = suspiciousUrl || detail.suspicious_video_url || null;
  const originalSrc = detail.protected_video_url || null;

  // Ask the backend to explain the top match and store that explanation.
  async function verify() {
    setExplaining(true);
    setExplainError(null);
    try {
      const res = await fetch(`${apiBase()}/api/scans/${detail!.scan_id}/explain-verdict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) {
        throw new Error(await errorMessage(res, "Could not verify that match."));
      }
      const json = (await res.json()) as { verdict_explanation: VerdictExplanation };
      setExplanation(json.verdict_explanation);
    } catch (err) {
      setExplainError(err instanceof Error ? err.message : "Could not verify that match.");
    } finally {
      setExplaining(false);
    }
  }

  return (
    <div>
      <MatchResults result={detail} />

      {detail.style_notice && (
        <section className="mt-5 rounded-xl border border-[#f0b429]/30 bg-[#f0b429]/[0.05] p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-[#f0b429]">Style signal</p>
          <p className="mt-2 text-sm font-medium">{detail.style_notice.message}</p>
          <p className="mt-1 text-xs text-[#9b958c]">
            Style similarity {detail.style_notice.style_similarity.toFixed(2)}. This is creator
            intelligence, not a copyright or legal conclusion.
          </p>
        </section>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <VideoPanel
          label="Suspicious short"
          title={suspiciousTitle || detail.suspicious_clip_id || "Checked file"}
          src={suspiciousSrc}
          ranges={suspiciousRanges}
        />
        <VideoPanel
          label="Original"
          title={detail.top_match?.protected_title || detail.top_match?.protected_clip_id || "No original"}
          src={originalSrc}
          ranges={originalRanges}
        />
      </div>

      <section className="mt-8">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium">Verdict explanation</h2>
          <button
            type="button"
            disabled={!detail.top_match || explaining}
            onClick={() => void verify()}
            className="rounded-full bg-[#f4f1ea] px-4 py-2 text-sm font-medium text-[#10100e] disabled:opacity-40"
          >
            {explaining ? "Verifying…" : "Verify match"}
          </button>
        </div>
        <p className="mt-2 text-xs text-[#9b958c]">Automated assessment. Not a legal verdict.</p>
        {explainError && <p className="mt-3 text-sm text-[#f0b429]">{explainError}</p>}
        {!explanation && !explaining && !explainError && (
          <p className="mt-3 text-sm text-[#9b958c]">
            {detail.top_match
              ? "Verify the match to read why these clips lined up."
              : "Nothing to verify until a close original is found."}
          </p>
        )}
        {explaining && <p className="mt-3 text-sm text-[#9b958c]">Reading the match…</p>}
        {explanation && (
          <div className="mt-4">
            <p className="text-sm font-medium">{decisionLabel[explanation.decision] ?? explanation.decision}</p>
            <p className="mt-2 text-sm leading-6">{explanation.explanation}</p>
            <p className="mt-2 text-sm text-[#9b958c]">{explanation.confidence_note}</p>
            {explanation.limitations.length > 0 && (
              <ul className="mt-3 list-disc pl-4 text-xs text-[#9b958c]">
                {explanation.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {evidence.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-medium">Evidence</h2>
          <ul className="mt-3 grid gap-3">
            {evidence.map((item: EvidenceItem) => (
              <li
                key={`${item.query_start_seconds}-${item.protected_start_seconds}-${item.observation}`}
                className="rounded-xl border border-white/10 bg-[#181816] px-4 py-3"
              >
                <p className="text-xs text-[#f0b429]">
                  Checked {range(item.query_start_seconds, item.query_end_seconds)} · Original{" "}
                  {range(item.protected_start_seconds, item.protected_end_seconds)}
                </p>
                <p className="mt-2 text-sm leading-6">{item.observation}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
