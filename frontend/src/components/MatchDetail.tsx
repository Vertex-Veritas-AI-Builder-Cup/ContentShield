"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  MatchResults,
  OtherContentMatches,
  OtherStyleMatches,
} from "@/components/MatchResults";
import {
  DmcaDraft,
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

// Keep model-written copy aligned with the product's user-facing terminology,
// including explanations that were persisted before the labels were standardized.
function displayCopy(value: string) {
  return value
    .replace(/suspicious video/gi, "checked video")
    .replace(/protected original/gi, "original")
    .replace(/protected video/gi, "original")
    .replace(/the video segment/gi, "the checked-video segment")
    .replace(/query video/gi, "checked video");
}

// One video column: title, player, and the times that matched.
function VideoPanel({
  label,
  title,
  src,
  ranges,
  emptyRangeMessage = "Timestamps appear after the automated assessment.",
}: {
  label: string;
  title: string;
  src: string | null;
  ranges: string[];
  emptyRangeMessage?: string;
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
        <p className="mt-2 text-xs text-[#6f6a62]">{emptyRangeMessage}</p>
      )}
    </div>
  );
}

/** Show one scan, its videos, the verdict explanation, and a DMCA draft. */
export function MatchDetail({
  detail,
  suspiciousUrl,
  suspiciousTitle,
  onPromoted,
  loading = false,
}: {
  detail: ScanDetail | null;
  suspiciousUrl: string | null;
  suspiciousTitle: string | null;
  onPromoted?: () => void;
  loading?: boolean;
}) {
  // Start from anything already saved on the scan. The assessment loads automatically.
  const [explanation, setExplanation] = useState<VerdictExplanation | null>(
    detail?.verdict_explanation ?? null,
  );
  const [draft, setDraft] = useState<DmcaDraft | null>(detail?.dmca_draft ?? null);
  const [explaining, setExplaining] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [draftExpanded, setDraftExpanded] = useState(true);
  const [promoting, setPromoting] = useState(false);
  const [promotionError, setPromotionError] = useState<string | null>(null);
  const [promotedClipId, setPromotedClipId] = useState<string | null>(
    detail?.promoted_clip_id ?? null,
  );
  const [promotedTitle, setPromotedTitle] = useState<string | null>(
    detail?.promoted_title ?? null,
  );
  const [copied, setCopied] = useState(false);
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
    if (loading) {
      return (
        <div className="animate-pulse" aria-label="Loading match results" aria-busy="true">
          <div className="grid gap-4 sm:grid-cols-2">
            {["Content match", "Style match"].map((label) => (
              <section key={label} className="min-h-64 rounded-2xl border border-white/10 bg-[#181816] p-6">
                <p className="text-xs uppercase tracking-[0.18em] text-[#6f6a62]">{label}</p>
                <div className="mt-5 h-3 w-20 rounded-full bg-white/10" />
                <div className="mt-4 h-14 w-28 rounded-lg bg-white/10" />
                <div className="mt-4 h-3 w-44 max-w-full rounded-full bg-white/[0.07]" />
                <div className="mt-5 h-3 w-32 rounded-full bg-white/[0.07]" />
              </section>
            ))}
          </div>
          <section className="mt-6 rounded-2xl border border-white/10 bg-[#181816] p-6">
            <div className="h-3 w-28 rounded-full bg-white/10" />
            <div className="mt-5 h-6 w-36 rounded-full bg-white/10" />
            <div className="mt-4 h-3 w-full rounded-full bg-white/[0.07]" />
            <div className="mt-2 h-3 w-3/4 rounded-full bg-white/[0.07]" />
          </section>
        </div>
      );
    }
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
  const suspiciousSrc =
    suspiciousUrl || detail.media?.suspicious_video_url || detail.suspicious_video_url || null;
  const originalSrc = detail.media?.protected_video_url || detail.protected_video_url || null;
  const styleMatch = detail.style_match;
  const styleOriginalSrc =
    detail.media?.style_original_video_url ||
    (styleMatch?.protected_clip_id === detail.top_match?.protected_clip_id ? originalSrc : null);
  const canMoveToOriginals = !detail.top_match || detail.top_match.verdict === "low_risk";

  // Send only the fields the user filled in, then show the returned draft.
  async function createDraft(event: FormEvent) {
    event.preventDefault();
    setDrafting(true);
    setDraftError(null);
    setCopied(false);
    const payload: Record<string, string> = {};
    if (creatorName.trim()) payload.creator_name = creatorName.trim();
    if (creatorEmail.trim()) payload.creator_email = creatorEmail.trim();
    if (platform.trim()) payload.platform = platform.trim();
    if (originalUrl.trim()) payload.original_url = originalUrl.trim();
    if (infringingUrl.trim()) payload.infringing_url = infringingUrl.trim();

    try {
      const res = await fetch(`${apiBase()}/api/scans/${detail!.scan_id}/dmca`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(await errorMessage(res, "Could not draft that notice."));
      }
      const json = (await res.json()) as { dmca_draft: DmcaDraft };
      setDraft(json.dmca_draft);
      setDraftExpanded(true);
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : "Could not draft that notice.");
    } finally {
      setDrafting(false);
    }
  }

  async function moveToOriginals() {
    if (!detail || promoting || promotedClipId) return;
    setPromoting(true);
    setPromotionError(null);
    try {
      const res = await fetch(`${apiBase()}/api/scans/${detail.scan_id}/move-to-original`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Could not move that video."));
      const json = (await res.json()) as { clip_id: string; title?: string };
      setPromotedClipId(json.clip_id);
      setPromotedTitle(json.title ?? null);
      onPromoted?.();
    } catch (err) {
      setPromotionError(err instanceof Error ? err.message : "Could not move that video.");
    } finally {
      setPromoting(false);
    }
  }

  // Copy the subject and body so the user can paste them elsewhere.
  async function copyDraft() {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.body}`);
      setCopied(true);
    } catch {
      setDraftError("Could not copy that draft.");
    }
  }

  // Save the draft as a text file in the browser.
  function downloadDraft() {
    if (!draft) return;
    const blob = new Blob(
      [`${draft.subject}\n\n${draft.body}\n\n${draft.disclaimer}\n`],
      { type: "text/plain" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${draft.draft_id}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div>
      <MatchResults result={detail} />


      <div className="mt-8 flex flex-col justify-between gap-4 border-l-2 border-[#f0b429] pl-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-[#f0b429]">Content match</p>
          <h2 className="mt-1 text-xl font-medium tracking-tight">Content similarity review</h2>
          <p className="mt-1 text-sm text-[#9b958c]">Compare matching moments, review the verdict, and inspect its evidence.</p>
        </div>
        {detail.top_match && (
          <p className="text-sm text-[#9b958c]">
            Score <span className="ml-1 text-lg font-medium text-[#f4f1ea]">{detail.top_match.content_similarity.toFixed(2)}</span>
          </p>
        )}
      </div>

      <div className="mt-6">
        <p className="text-[11px] uppercase tracking-[0.18em] text-[#6f6a62]">Video comparison</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <VideoPanel
            label="Checked video"
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
      </div>

      <section className="mt-6 rounded-2xl border border-white/10 bg-[#181816] p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-medium">Verdict</h2>
          </div>
          <p className="text-xs text-[#6f6a62]">Automated assessment · not legal advice</p>
        </div>
        {explainError && (
          <p className="mt-4 rounded-xl border border-[#f0b429]/20 bg-[#f0b429]/5 px-4 py-3 text-sm text-[#f0b429]">
            {explainError}
          </p>
        )}
        {!explanation && !explaining && !explainError && (
          <p className="mt-4 text-sm text-[#9b958c]">
            {detail.top_match
              ? "Preparing the evidence summary…"
              : "No close original was found to assess."}
          </p>
        )}
        {explaining && (
          <div className="mt-5 animate-pulse" aria-label="Preparing content verdict" aria-busy="true">
            <div className="h-6 w-36 rounded-full bg-white/10" />
            <div className="mt-4 h-3 w-full rounded-full bg-white/[0.07]" />
            <div className="mt-2 h-3 w-5/6 rounded-full bg-white/[0.07]" />
            <div className="mt-4 h-3 w-2/3 rounded-full bg-white/[0.07]" />
          </div>
        )}
        {explanation && (
          <div className="mt-4 border-l-2 border-[#f0b429] pl-4">
            <p className="text-xl font-medium tracking-tight text-[#f4f1ea]">
              {decisionLabel[explanation.decision] ?? explanation.decision}
            </p>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[#d4d0c8]">
              {displayCopy(explanation.explanation)}
            </p>
            <p className="mt-2 max-w-4xl text-xs leading-5 text-[#9b958c]">
              {displayCopy(explanation.confidence_note)}
            </p>
            {explanation.limitations.length > 0 && (
              <div className="mt-4 border-t border-white/10 pt-3">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">Limitations</p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-[#9b958c]">
                  {explanation.limitations.map((item) => (
                    <li key={item}>{displayCopy(item)}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="mt-4 rounded-2xl border border-white/10 bg-[#181816] p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-medium">Evidence</h2>
            </div>
            {evidence.length > 0 && (
              <p className="text-xs text-[#6f6a62]">
                {evidence.length} {evidence.length === 1 ? "segment" : "segments"}
              </p>
            )}
          </div>
          {evidence.length > 0 ? (
            <ul className="mt-3 grid gap-3">
              {evidence.map((item: EvidenceItem) => (
              <li
                key={`${item.query_start_seconds}-${item.protected_start_seconds}-${item.observation}`}
                className="rounded-xl border border-white/10 bg-[#10100e] p-4 sm:p-5"
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">
                      Checked video
                    </p>
                    <p className="mt-1 text-sm font-medium text-[#f0b429]">
                      {range(item.query_start_seconds, item.query_end_seconds)}
                    </p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">
                      Original
                    </p>
                    <p className="mt-1 text-sm font-medium text-[#f0b429]">
                      {range(item.protected_start_seconds, item.protected_end_seconds)}
                    </p>
                  </div>
                </div>
                <div className="mt-4">
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">
                    Why these moments match
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[#d4d0c8]">
                    {displayCopy(item.observation)}
                  </p>
                </div>
              </li>
              ))}
            </ul>
          ) : explaining ? (
            <div className="mt-4 animate-pulse rounded-xl border border-white/10 bg-[#10100e] p-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="h-16 rounded-lg bg-white/[0.07]" />
                <div className="h-16 rounded-lg bg-white/[0.07]" />
              </div>
              <div className="mt-4 h-3 w-40 rounded-full bg-white/10" />
              <div className="mt-3 h-3 w-full rounded-full bg-white/[0.07]" />
              <div className="mt-2 h-3 w-4/5 rounded-full bg-white/[0.07]" />
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-white/15 bg-[#10100e] px-5 py-6 text-sm text-[#9b958c]">
              {explanation
                ? "No timestamped content evidence was returned for this verdict."
                : "Content evidence will appear here after the verdict is prepared."}
            </div>
          )}
        </section>

      <div className="mt-10 flex flex-col justify-between gap-4 border-l-2 border-[#9b958c] pl-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-[#d4d0c8]">Style match</p>
          <h2 className="mt-1 text-xl font-medium tracking-tight">Editing-style review</h2>
          <p className="mt-1 text-sm text-[#9b958c]">Review the closest editing-pattern comparison independently from content.</p>
        </div>
        {styleMatch && (
          <p className="text-sm text-[#9b958c]">
            Score <span className="ml-1 text-lg font-medium text-[#f4f1ea]">{styleMatch.style_similarity.toFixed(2)}</span>
          </p>
        )}
      </div>

      <div className="mt-6">
        <p className="text-[11px] uppercase tracking-[0.18em] text-[#6f6a62]">Video comparison</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <VideoPanel
            label="Checked video"
            title={suspiciousTitle || detail.source_filename || detail.suspicious_clip_id || "Checked file"}
            src={suspiciousSrc}
            ranges={[]}
            emptyRangeMessage="Style Match compares editing patterns across the full video."
          />
          <VideoPanel
            label="Original"
            title={styleMatch?.protected_title || styleMatch?.protected_clip_id || "No style original"}
            src={styleOriginalSrc}
            ranges={[]}
            emptyRangeMessage="Style Match compares editing patterns across the full original."
          />
        </div>
      </div>

      <section className="mt-6 rounded-2xl border border-white/10 bg-[#181816] p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-medium">Verdict</h2>
          </div>
          <p className="text-xs text-[#6f6a62]">Creator intelligence · not legal advice</p>
        </div>
        <div className={`mt-4 border-l-2 pl-4 ${styleMatch?.style_match ? "border-[#f0b429]" : "border-[#c8e6c4]"}`}>
            {styleMatch ? (
              <>
                <p
                  className={`text-xl font-medium tracking-tight ${
                    styleMatch.style_match ? "text-[#f0b429]" : "text-[#c8e6c4]"
                  }`}
                >
                  {styleMatch.style_match ? "Similar editing style" : "Below style threshold"}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#9b958c]">
                  The checked video was compared with the closest original using clip-level editing patterns.
                </p>
                <p className="mt-2 text-xs leading-5 text-[#6f6a62]">
                  A style score of {styleMatch.style_similarity.toFixed(2)} was compared with
                  {typeof styleMatch.style_threshold === "number"
                    ? ` the ${styleMatch.style_threshold.toFixed(2)} decision threshold.`
                    : " the configured decision threshold."}
                </p>
              </>
            ) : (
              <>
                <p className="mt-3 text-lg font-medium">Unavailable</p>
                <p className="mt-2 text-sm leading-6 text-[#9b958c]">
                  {detail.style_evaluated === false
                    ? "A reliable style comparison could not be produced for this check."
                    : "No style result was returned for this check."}
                </p>
              </>
            )}
        </div>
      </section>

      <section className="mt-4 rounded-2xl border border-white/10 bg-[#181816] p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-medium">Evidence</h2>
          </div>
          <p className="text-xs text-[#6f6a62]">Clip-level editing signals</p>
        </div>
        {styleMatch ? (
          <article className="mt-4 rounded-xl border border-white/10 bg-[#10100e] p-4 sm:p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg bg-white/[0.03] px-3 py-3">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">Checked video</p>
                <p className="mt-1 text-sm font-medium text-[#f0b429]">Clip-level pattern analyzed</p>
              </div>
              <div className="rounded-lg bg-white/[0.03] px-3 py-3">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">Original</p>
                <p className="mt-1 truncate text-sm font-medium text-[#f0b429]">
                  {styleMatch.protected_title || styleMatch.protected_clip_id}
                </p>
              </div>
            </div>
            <div className="mt-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">
                Why the style matched
              </p>
              <p className="mt-2 text-sm leading-6 text-[#d4d0c8]">
                The clip-level pacing and shot-length pattern produced a style score of{" "}
                {styleMatch.style_similarity.toFixed(2)}
                {typeof styleMatch.style_threshold === "number"
                  ? ` against a ${styleMatch.style_threshold.toFixed(2)} threshold.`
                  : "."}
              </p>
              <p className="mt-2 text-xs leading-5 text-[#6f6a62]">
                Style evidence is not timestamped and does not establish copying, ownership, or infringement.
              </p>
            </div>
          </article>
        ) : (
          <div className="mt-4 rounded-xl border border-dashed border-white/15 bg-[#10100e] px-5 py-6 text-sm text-[#9b958c]">
            No style evidence is available for this check.
          </div>
        )}
      </section>

      {(canMoveToOriginals || promotedClipId) && (
        <section className="mt-8 rounded-2xl border border-[#c8e6c4]/20 bg-[#c8e6c4]/[0.04] p-5 sm:p-6">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
            <div className="max-w-2xl">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[#8fb68a]">Next step</p>
              <h2 className="mt-1 text-lg font-medium">
                {promotedClipId ? "Saved to Originals" : "Save this checked video as an original"}
              </h2>
              <p className="mt-2 text-sm leading-6 text-[#9b958c]">
                {promotedClipId
                  ? `${promotedTitle || "This video"} is being fingerprinted for future checks.`
                  : "This check is low risk. Add the video to Originals so future uploads can be compared against it."}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void moveToOriginals()}
              disabled={!detail.suspicious_clip_id || promoting || Boolean(promotedClipId)}
              className="shrink-0 rounded-full bg-[#c8e6c4] px-5 py-2.5 text-sm font-medium text-[#10100e] transition-transform hover:-translate-y-0.5 active:translate-y-0 disabled:translate-y-0 disabled:cursor-default disabled:opacity-60"
            >
              {promoting ? "Saving…" : promotedClipId ? "Saved to Originals" : "Move to Originals"}
            </button>
          </div>
          {promotionError && (
            <p className="mt-4 rounded-xl border border-[#f0b429]/20 bg-[#f0b429]/5 px-4 py-3 text-sm text-[#f0b429]">
              {promotionError}
            </p>
          )}
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-medium">DMCA draft</h2>
        <p className="mt-2 text-xs text-[#9b958c]">
          A draft for you or a lawyer to review. It is not sent anywhere.
        </p>
        <form onSubmit={createDraft} className="mt-4 grid gap-3 sm:grid-cols-2">
          <input
            value={creatorName}
            onChange={(event) => setCreatorName(event.target.value)}
            placeholder="Creator name"
            className="rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[#6f6a62] focus:border-[#f0b429]"
          />
          <input
            value={creatorEmail}
            onChange={(event) => setCreatorEmail(event.target.value)}
            placeholder="Email"
            className="rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[#6f6a62] focus:border-[#f0b429]"
          />
          <input
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
            placeholder="Platform"
            className="rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[#6f6a62] focus:border-[#f0b429]"
          />
          <input
            value={originalUrl}
            onChange={(event) => setOriginalUrl(event.target.value)}
            placeholder="Original page URL (optional)"
            className="rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[#6f6a62] focus:border-[#f0b429]"
          />
          <input
            value={infringingUrl}
            onChange={(event) => setInfringingUrl(event.target.value)}
            placeholder="Checked video page URL (optional)"
            className="rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[#6f6a62] focus:border-[#f0b429] sm:col-span-2"
          />
          <button
            type="submit"
            disabled={!detail.top_match || !explanation || drafting}
            className="w-fit rounded-full border border-white/15 px-4 py-2 text-sm text-[#f4f1ea] disabled:opacity-40"
          >
            {drafting ? "Writing…" : "Generate DMCA draft"}
          </button>
        </form>
        {!explanation && (
          <p className="mt-3 text-xs text-[#6f6a62]">Verify the match before drafting a notice.</p>
        )}
        {draftError && <p className="mt-3 text-sm text-[#f0b429]">{draftError}</p>}
        {draft && (
          <div className="mt-4 rounded-xl border border-white/10 bg-[#181816] px-4 py-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">Generated draft</p>
                <p className="mt-1 truncate text-sm font-medium">{draft.subject}</p>
              </div>
              <button
                type="button"
                aria-expanded={draftExpanded}
                onClick={() => setDraftExpanded((value) => !value)}
                className="shrink-0 rounded-full border border-white/15 px-3 py-1.5 text-xs text-[#d4d0c8] transition-colors hover:border-white/30 hover:text-[#f4f1ea]"
              >
                {draftExpanded ? "Minimize" : "Expand"}
              </button>
            </div>
            {draftExpanded && (
              <div className="mt-4 border-t border-white/10 pt-4">
                <p className="whitespace-pre-wrap text-sm leading-6">{draft.body}</p>
                <p className="mt-4 text-xs text-[#f0b429]">{draft.disclaimer}</p>
                <div className="mt-4 flex gap-3 text-sm">
                  <button type="button" className="text-[#f4f1ea] hover:text-[#f0b429]" onClick={() => void copyDraft()}>
                    {copied ? "Copied" : "Copy"}
                  </button>
                  <button type="button" className="text-[#9b958c] hover:text-[#f4f1ea]" onClick={downloadDraft}>
                    Download
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <OtherContentMatches result={detail} />
      <OtherStyleMatches result={detail} />
    </div>
  );
}
