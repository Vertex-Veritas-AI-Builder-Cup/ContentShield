"use client";

import { FormEvent, useEffect, useState } from "react";
import { MatchResults } from "@/components/MatchResults";
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

      <section className="mt-8">
        <h2 className="text-sm font-medium">Protect this upload</h2>
        <p className="mt-2 text-xs text-[#9b958c]">
          Move the checked video into Originals and fingerprint it so future checks can find it.
        </p>
        <button
          type="button"
          onClick={() => void moveToOriginals()}
          disabled={!detail.suspicious_clip_id || promoting || Boolean(promotedClipId)}
          className="mt-3 rounded-full border border-white/15 px-4 py-2 text-sm text-[#f4f1ea] disabled:opacity-40"
        >
          {promoting ? "Moving…" : promotedClipId ? "Moved to Originals" : "Move to Originals"}
        </button>
        {promotedClipId && (
          <p className="mt-2 text-xs text-[#c8e6c4]">
            Added as {promotedTitle || "a new original"}. Fingerprinting is running in the background.
          </p>
        )}
        {promotionError && <p className="mt-2 text-sm text-[#f0b429]">{promotionError}</p>}
      </section>

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
            placeholder="Copied-video page URL (optional)"
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
            <p className="text-sm font-medium">{draft.subject}</p>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{draft.body}</p>
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
      </section>
    </div>
  );
}
