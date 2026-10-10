export type Verdict = "high_risk" | "medium_risk" | "low_risk";

export type ScanMatch = {
  protected_clip_id: string;
  protected_title?: string;
  content_similarity: number;
  verdict: Verdict;
};

export type ScanResult = {
  scan_id: string;
  matches: ScanMatch[];
  top_match: ScanMatch | null;
  processing_ms?: number;
};

const badge: Record<Verdict, { label: string; className: string }> = {
  high_risk: { label: "High risk", className: "text-[#e36a6a]" },
  medium_risk: { label: "Medium risk", className: "text-[#f0b429]" },
  low_risk: { label: "Low risk", className: "text-[#c8e6c4]" },
};

function percent(score: number) {
  return `${Math.round(score * 100)}%`;
}

export function MatchResults({ result }: { result: ScanResult | null }) {
  if (!result) {
    return (
      <div className="flex min-h-52 items-center justify-center rounded-2xl border border-dashed border-white/15 px-6 text-sm text-[#9b958c]">
        The match shows up here.
      </div>
    );
  }

  const top = result.top_match;
  const matches = [...(result.matches ?? [])].sort(
    (a, b) => b.content_similarity - a.content_similarity,
  );

  return (
    <div>
      {top ? (
        <div className="rounded-2xl border border-white/10 bg-[#181816] px-5 py-6">
          <p className={`text-xs ${badge[top.verdict]?.className ?? "text-[#9b958c]"}`}>
            {badge[top.verdict]?.label ?? top.verdict}
          </p>
          <p className="mt-2 text-5xl font-medium tracking-tight">
            {percent(top.content_similarity)}
          </p>
          <p className="mt-2 text-sm text-[#9b958c]">
            {top.protected_title || top.protected_clip_id}
          </p>
          {typeof result.processing_ms === "number" && (
            <p className="mt-3 text-xs text-[#6f6a62]">
              {(result.processing_ms / 1000).toFixed(1)}s
            </p>
          )}
        </div>
      ) : (
        <p className="rounded-2xl border border-white/10 bg-[#181816] px-5 py-6 text-sm text-[#9b958c]">
          No originals to compare yet.
        </p>
      )}

      {matches.length > 0 && (
        <ul className="mt-4">
          {matches.map((match) => (
            <li
              key={match.protected_clip_id}
              className="flex items-center justify-between border-t border-white/10 py-3 text-sm"
            >
              <span>{match.protected_title || match.protected_clip_id}</span>
              <span className={badge[match.verdict]?.className ?? "text-[#9b958c]"}>
                {percent(match.content_similarity)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex min-h-24 items-center justify-center rounded-xl border border-dashed border-white/10 text-xs text-[#6f6a62]">
        Side by side comes next.
      </div>
    </div>
  );
}
