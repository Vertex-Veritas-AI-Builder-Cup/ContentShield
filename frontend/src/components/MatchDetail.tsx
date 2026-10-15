"use client";

import { FormEvent, useEffect, useState } from "react";
import { MatchResults, OtherContentMatches } from "@/components/MatchResults";
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

// Normalize explanations saved before the product terminology was standardized.
function displayCopy(value: string) {
  return value
    .replace(/suspicious video/gi, "checked video")
    .replace(/protected original/gi, "original")
    .replace(/protected video/gi, "original")
    .replace(/query video/gi, "checked video");
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

/** Show one scan, its videos, the verdict explanation, and a DMCA draft. */
export function MatchDetail({
  detail,
  suspiciousUrl,
  suspiciousTitle,
  onPromoted,
}: {
  detail: ScanDetail | null;
  suspiciousUrl: string | null;
  suspiciousTitle: string | null;
  onPromoted?: () => void;
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
    return (
      <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-white/15 px-6 text-sm text-[#9b958c]">
        The match shows up here.
      </div>
    );
  }

  // Keep the local preview mounted while the backend finishes the asynchronous check.
  const suspiciousSrc =
    suspiciousUrl || detail.media?.suspicious_video_url || detail.suspicious_video_url || null;

  if (detail.status === "processing") {
    return (
      <div className="rounded-2xl border border-white/10 bg-[#181816] p-5 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-[#f0b429]">Content review</p>
            <h2 className="mt-1 text-xl font-medium tracking-tight">Checking your video</h2>
            <p className="mt-1 text-sm text-[#9b958c]">Comparing it with your Originals. This can take a moment.</p>
          </div>
          <span className="animate-pulse text-xs text-[#6f6a62]">In progress</span>
        </div>
        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <VideoPanel
            label="Checked video"
            title={suspiciousTitle || detail.source_filename || detail.suspicious_clip_id || "Checked file"}
            src={suspiciousSrc}
            ranges={[]}
          />
          <div className="animate-pulse rounded-xl border border-white/10 bg-[#10100e] p-4">
            <div className="h-3 w-24 rounded-full bg-white/10" />
            <div className="mt-4 h-5 w-36 rounded-full bg-white/10" />
            <div className="mt-5 h-3 w-full rounded-full bg-white/[0.07]" />
            <div className="mt-2 h-3 w-4/5 rounded-full bg-white/[0.07]" />
            <p className="mt-6 text-xs text-[#6f6a62]">Original comparison will appear when the check is ready.</p>
          </div>
        </div>
      </div>
    );
  }

  if (detail.status === "failed") {
    return (
      <div className="rounded-2xl border border-[#e36a6a]/30 bg-[#181816] p-5 sm:p-6">
        <p className="text-sm text-[#e36a6a]">
          Content comparison failed{detail.processing_error ? `: ${detail.processing_error}` : "."}
        </p>
        {suspiciousSrc && (
          <div className="mt-5 max-w-xl">
            <VideoPanel
              label="Checked video"
              title={suspiciousTitle || detail.source_filename || "Checked file"}
              src={suspiciousSrc}
              ranges={[]}
            />
          </div>
        )}
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
  const originalSrc = detail.media?.protected_video_url || detail.protected_video_url || null;
  const canMoveToOriginals = !detail.top_match || detail.top_match.verdict === "low_risk";
  const contentScore = detail.top_match
    ? detail.top_match.content_similarity <= 1
      ? detail.top_match.content_similarity * 100
      : detail.top_match.content_similarity
    : null;

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
          <p className="text-xs uppercase tracking-[0.2em] text-[#f0b429]">Content review</p>
          <h2 className="mt-1 text-xl font-medium tracking-tight">Compare matching moments</h2>
          <p className="mt-1 text-sm text-[#9b958c]">Review the checked video, the original, and the evidence behind this score.</p>
        </div>
        {detail.top_match && (
          <p className="text-sm text-[#9b958c]">
            Score <span className="ml-1 text-lg font-medium text-[#f4f1ea]">{contentScore?.toFixed(0)}%</span>
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
          <h2 className="text-sm font-medium">Verdict</h2>
          <p className="text-xs text-[#6f6a62]">Automated assessment · not legal advice</p>
        </div>
        {explainError && <p className="mt-3 text-sm text-[#f0b429]">{explainError}</p>}
        {!explanation && !explaining && !explainError && (
          <p className="mt-3 text-sm text-[#9b958c]">
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
            <p className="text-xl font-medium tracking-tight text-[#f4f1ea]">{decisionLabel[explanation.decision] ?? explanation.decision}</p>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[#d4d0c8]">{displayCopy(explanation.explanation)}</p>
            <p className="mt-2 max-w-4xl text-xs leading-5 text-[#9b958c]">{displayCopy(explanation.confidence_note)}</p>
            {explanation.limitations.length > 0 && (
              <ul className="mt-4 list-disc space-y-1 border-t border-white/10 pt-3 pl-4 text-xs leading-5 text-[#9b958c]">
                {explanation.limitations.map((item) => (
                  <li key={item}>{displayCopy(item)}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section className="mt-4 rounded-2xl border border-white/10 bg-[#181816] p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-medium">Evidence</h2>
          {evidence.length > 0 && <p className="text-xs text-[#6f6a62]">{evidence.length} {evidence.length === 1 ? "segment" : "segments"}</p>}
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
                    <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">Checked video</p>
                    <p className="mt-1 text-sm font-medium text-[#f0b429]">{range(item.query_start_seconds, item.query_end_seconds)}</p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">Original</p>
                    <p className="mt-1 text-sm font-medium text-[#f0b429]">{range(item.protected_start_seconds, item.protected_end_seconds)}</p>
                  </div>
                </div>
                <p className="mt-4 text-[11px] uppercase tracking-[0.14em] text-[#6f6a62]">Why these moments match</p>
                <p className="mt-2 text-sm leading-6 text-[#d4d0c8]">{displayCopy(item.observation)}</p>
              </li>
            ))}
          </ul>
        ) : explaining ? (
          <div className="mt-4 animate-pulse rounded-xl border border-white/10 bg-[#10100e] p-5">
            <div className="h-16 rounded-lg bg-white/[0.07]" />
            <div className="mt-4 h-3 w-40 rounded-full bg-white/10" />
            <div className="mt-3 h-3 w-full rounded-full bg-white/[0.07]" />
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-dashed border-white/15 bg-[#10100e] px-5 py-6 text-sm text-[#9b958c]">
            {explanation ? "No timestamped content evidence was returned for this verdict." : "Content evidence will appear here after the verdict is prepared."}
          </div>
        )}
      </section>

      {(canMoveToOriginals || promotedClipId) && (
      <section className="mt-8 rounded-2xl border border-[#c8e6c4]/20 bg-[#c8e6c4]/[0.04] p-5 sm:p-6">
        <p className="text-[11px] uppercase tracking-[0.18em] text-[#8fb68a]">Next step</p>
        <h2 className="mt-1 text-lg font-medium">{promotedClipId ? "Saved to Originals" : "Save this checked video as an original"}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#9b958c]">
          {promotedClipId ? `${promotedTitle || "This video"} is being fingerprinted for future checks.` : "This check is low risk. Add the video to Originals so future uploads can be compared against it."}
        </p>
        <button
          type="button"
          onClick={() => void moveToOriginals()}
          disabled={!detail.suspicious_clip_id || promoting || Boolean(promotedClipId)}
          className="mt-4 rounded-full bg-[#c8e6c4] px-5 py-2.5 text-sm font-medium text-[#10100e] transition-transform hover:-translate-y-0.5 disabled:translate-y-0 disabled:cursor-default disabled:opacity-60"
        >
          {promoting ? "Saving…" : promotedClipId ? "Saved to Originals" : "Move to Originals"}
        </button>
        {promotedClipId && (
          <p className="mt-2 text-xs text-[#c8e6c4]">
            Added as {promotedTitle || "a new original"}. Fingerprinting is running in the background.
          </p>
        )}
        {promotionError && <p className="mt-2 text-sm text-[#f0b429]">{promotionError}</p>}
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
                className="shrink-0 rounded-full border border-white/15 px-3 py-1.5 text-xs text-[#d4d0c8] hover:border-white/30 hover:text-[#f4f1ea]"
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
    </div>
  );
}
