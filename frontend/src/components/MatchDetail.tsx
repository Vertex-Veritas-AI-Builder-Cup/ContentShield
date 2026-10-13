"use client";

import { useEffect, useState } from "react";
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
        <p className="mt-2 text-xs text-[#6f6a62]">Timestamps appear after the automated assessment.</p>
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
  // Start from anything already saved on the scan. The assessment loads automatically.
  const [explanation, setExplanation] = useState<VerdictExplanation | null>(
    detail?.verdict_explanation ?? null,
  );
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  // Optional details the user can add to the takedown draft.
  const [creatorName, setCreatorName] = useState("");
  const [creatorEmail, setCreatorEmail] = useState("");
  const [platform, setPlatform] = useState("");
  const [originalUrl, setOriginalUrl] = useState("");
  const [infringingUrl, setInfringingUrl] = useState("");

  // Generate and persist the evidence summary as soon as a matched scan is opened.
  useEffect(() => {
    if (!detail?.top_match || explanation) return;
    const scanId = detail.scan_id;
    let cancelled = false;

    async function loadExplanation() {
      setExplaining(true);
      setExplainError(null);
      try {
        const res = await fetch(`${apiBase()}/api/scans/${scanId}/explain-verdict`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        if (!res.ok) throw new Error(await errorMessage(res, "Could not prepare the assessment."));
        const json = (await res.json()) as { verdict_explanation: VerdictExplanation };
        if (!cancelled) setExplanation(json.verdict_explanation);
      } catch (err) {
        if (!cancelled) {
          setExplainError(err instanceof Error ? err.message : "Could not prepare the assessment.");
        }
      } finally {
        if (!cancelled) setExplaining(false);
      }
    }

    void loadExplanation();
    return () => {
      cancelled = true;
    };
  }, [detail?.scan_id, detail?.top_match, explanation]);

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

  return (
    <div>
      <MatchResults result={detail} />


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
        <h2 className="text-sm font-medium">Verdict explanation</h2>
        <p className="mt-2 text-xs text-[#9b958c]">Automated assessment. Not a legal verdict.</p>
        {explainError && <p className="mt-3 text-sm text-[#f0b429]">{explainError}</p>}
        {!explanation && !explaining && !explainError && (
          <p className="mt-3 text-sm text-[#9b958c]">
            {detail.top_match
              ? "Preparing the evidence summary…"
              : "No close original was found to assess."}
          </p>
        )}
        {explaining && <p className="mt-3 text-sm text-[#9b958c]">Preparing the evidence summary…</p>}
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
