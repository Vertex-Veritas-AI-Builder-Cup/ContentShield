import type { ScanDetail, ScanMatch } from "@/components/scanTypes";

export type { MatchedSegment, ScanMatch, Verdict } from "@/components/scanTypes";

// Colors for the three risk levels returned by the content scan.
const badge: Record<ScanMatch["verdict"], { label: string; className: string }> = {
  high_risk: { label: "High risk", className: "text-[#e36a6a]" },
  medium_risk: { label: "Medium risk", className: "text-[#f0b429]" },
  low_risk: { label: "Low risk", className: "text-[#c8e6c4]" },
};

// Support both current 0-1 scores and legacy scores already stored as 0-100.
function score(value: number) {
  const percent = value >= 0 && value <= 1 ? value * 100 : value;
  return `${Math.round(percent)}%`;
}

function coverage(value: number) {
  return `${Math.round(value * 100)}%`;
}

/** Show the primary content similarity score. */
export function MatchResults({ result }: { result: ScanDetail | null }) {
  if (!result) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-white/15 px-6 text-sm text-[#9b958c]">
        The match shows up here.
      </div>
    );
  }

  const top = result.selected_match ?? result.top_match;
  return (
    <div>
      <section className="rounded-2xl border border-white/10 bg-[#181816] px-5 py-6 sm:px-6">
          <p className="text-xs uppercase tracking-[0.18em] text-[#9b958c]">
            {result.selected_match && result.selected_match.protected_clip_id !== result.top_match?.protected_clip_id
              ? "Selected content match"
              : "Content match"}
          </p>
          {top ? (
            <>
              <p className={`mt-4 text-xs ${badge[top.verdict]?.className ?? "text-[#9b958c]"}`}>
                {badge[top.verdict]?.label ?? top.verdict}
              </p>
              <p className="mt-2 text-5xl font-medium tracking-tight">
                {score(top.content_similarity)}
              </p>
              <p className="mt-2 text-sm text-[#9b958c]">Calibrated similarity score, shown as a percentage.</p>
              <p className="mt-2 text-sm text-[#f4f1ea]">
                {top.protected_title || top.protected_clip_id}
              </p>
              <p className="mt-3 text-xs text-[#6f6a62]">
                {typeof top.segment_coverage === "number"
                  ? `Segment coverage ${coverage(top.segment_coverage)}`
                  : "Segment coverage unavailable"}
                {typeof top.matched_segment_count === "number"
                  ? ` · ${top.matched_segment_count} matched segments`
                  : ""}
                {typeof result.processing_ms === "number"
                  ? ` · ${(result.processing_ms / 1000).toFixed(1)}s`
                  : ""}
              </p>
            </>
          ) : (
            <p className="mt-4 text-sm text-[#9b958c]">No close original found.</p>
          )}
      </section>
    </div>
  );
}

/** Show lower-ranked content candidates after the primary review workflow. */
export function OtherContentMatches({ result }: { result: ScanDetail }) {
  const selectedId = result.selected_match?.protected_clip_id ?? result.top_match?.protected_clip_id;
  const matches = [...(result.matches ?? [])]
    .filter((match) => match.protected_clip_id !== selectedId)
    .sort((a, b) => b.content_similarity - a.content_similarity);

  if (matches.length === 0) return null;

  return (
    <section className="mt-8 rounded-2xl border border-white/10 bg-[#181816] p-5 sm:p-6">
      <h2 className="text-sm font-medium">Other content matches</h2>
      <p className="mt-1 text-xs text-[#6f6a62]">Other originals from this check</p>
      <ul className="mt-4">
        {matches.map((match) => (
          <li
            key={match.protected_clip_id}
            className="border-t border-white/10 first:border-t-0 first:pt-0"
          >
            {/* Use a deep link so a selected match can be refreshed or shared safely. */}
            <a
              href={`/monitor?scan=${encodeURIComponent(result.scan_id)}&match=${encodeURIComponent(match.protected_clip_id)}`}
              className="flex items-center justify-between gap-3 py-3 text-sm transition-colors hover:text-[#f0b429]"
            >
              <span className="min-w-0 truncate">
                {match.protected_title || match.protected_clip_id}
              </span>
              <span className="flex shrink-0 items-center gap-3">
                <span className={badge[match.verdict]?.className ?? "text-[#9b958c]"}>
                  {score(match.content_similarity)}
                </span>
                <span className="text-xs text-[#6f6a62]">Review match →</span>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
