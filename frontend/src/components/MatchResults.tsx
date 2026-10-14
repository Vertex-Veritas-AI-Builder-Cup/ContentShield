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

function styleSkipMessage(reason?: string | null) {
  if (reason === "no_compatible_style_embeddings") {
    return "No compatible protected style embeddings are available.";
  }
  if (reason === "style_analysis_unavailable") {
    return "Style analysis was unavailable for this check.";
  }
  return "Style analysis did not return a result.";
}

/** Show the content and independent style similarity results side by side. */
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
  const styleMatch = result.style_match;

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
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

        <section className="rounded-2xl border border-white/10 bg-[#181816] px-5 py-6">
          <p className="text-xs uppercase tracking-[0.18em] text-[#9b958c]">Style match</p>
          {styleMatch ? (
            <>
              <p
                className={`mt-4 text-xs ${
                  styleMatch.style_match ? "text-[#f0b429]" : "text-[#c8e6c4]"
                }`}
              >
                {styleMatch.style_match ? "Similar style" : "Below style threshold"}
              </p>
              <p className="mt-2 text-5xl font-medium tracking-tight">
                {score(styleMatch.style_similarity)}
              </p>
              <p className="mt-2 text-sm text-[#9b958c]">Independent editing-style score.</p>
              <p className="mt-2 text-sm text-[#f4f1ea]">
                {styleMatch.protected_title || styleMatch.protected_clip_id}
              </p>
              {typeof styleMatch.style_threshold === "number" && (
                <p className="mt-3 text-xs text-[#6f6a62]">
                  Notice threshold {score(styleMatch.style_threshold)}
                </p>
              )}
            </>
          ) : (
            <>
              <p className="mt-4 text-sm text-[#9b958c]">
                {result.style_evaluated === false
                  ? styleSkipMessage(result.style_skip_reason)
                  : "No style result was returned."}
              </p>
              {result.style_evaluated !== false && (
                <p className="mt-2 text-xs text-[#6f6a62]">
                  Style analysis runs independently of content similarity.
                </p>
              )}
            </>
          )}
          {result.style_notice && (
            <div className="mt-4 rounded-xl border border-[#f0b429]/30 bg-[#f0b429]/10 px-3 py-3">
              <p className="text-sm text-[#f0b429]">{result.style_notice.message}</p>
              <p className="mt-1 text-xs text-[#9b958c]">{result.style_notice.disclaimer}</p>
            </div>
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
