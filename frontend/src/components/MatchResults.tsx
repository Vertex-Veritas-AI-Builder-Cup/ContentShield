import type { ScanDetail, ScanMatch } from "@/components/scanTypes";

export type { MatchedSegment, ScanMatch, Verdict } from "@/components/scanTypes";

// Colors for the three risk levels returned by the content scan.
const badge: Record<ScanMatch["verdict"], { label: string; className: string }> = {
  high_risk: { label: "High risk", className: "text-[#e36a6a]" },
  medium_risk: { label: "Medium risk", className: "text-[#f0b429]" },
  low_risk: { label: "Low risk", className: "text-[#c8e6c4]" },
};

// Show 0.92 as a score. Do not turn it into a probability.
function score(value: number) {
  return value.toFixed(2);
}

/** Show the content similarity results. */
export function MatchResults({ result }: { result: ScanDetail | null }) {
  if (!result) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-white/15 px-6 text-sm text-[#9b958c]">
        The match shows up here.
      </div>
    );
  }

  const top = result.top_match;
  // Highest content similarity first, in case the API order changes.
  const matches = [...(result.matches ?? [])].sort(
    (a, b) => b.content_similarity - a.content_similarity,
  );
  return (
    <div>
      <div>
        <section className="rounded-2xl border border-white/10 bg-[#181816] px-5 py-6">
          <p className="text-xs uppercase tracking-[0.18em] text-[#9b958c]">Content match</p>
          {top ? (
            <>
              <p className={`mt-4 text-xs ${badge[top.verdict]?.className ?? "text-[#9b958c]"}`}>
                {badge[top.verdict]?.label ?? top.verdict}
              </p>
              <p className="mt-2 text-5xl font-medium tracking-tight">
                {score(top.content_similarity)}
              </p>
              <p className="mt-2 text-sm text-[#9b958c]">Similarity score, not a probability.</p>
              <p className="mt-2 text-sm text-[#f4f1ea]">
                {top.protected_title || top.protected_clip_id}
              </p>
              <p className="mt-3 text-xs text-[#6f6a62]">
                {typeof top.segment_coverage === "number"
                  ? `Segment coverage ${score(top.segment_coverage)}`
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

      {matches.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-medium">Other content matches</h2>
          <ul className="mt-3">
            {matches.map((match) => (
              <li
                key={match.protected_clip_id}
                className="flex items-center justify-between gap-3 border-t border-white/10 py-3 text-sm"
              >
                <span className="min-w-0 truncate">
                  {match.protected_title || match.protected_clip_id}
                </span>
                <span className={badge[match.verdict]?.className ?? "text-[#9b958c]"}>
                  {score(match.content_similarity)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
