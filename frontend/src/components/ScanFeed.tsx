"use client";

import { useCallback, useEffect, useState } from "react";
import { Verdict } from "@/components/scanTypes";

type HighMatch = {
  protected_title: string;
  content_similarity: number;
};

type ScanRow = {
  scan_id: string;
  top_similarity: number;
  verdict: Verdict;
  scanned_at: string;
  protected_title?: string;
  source_filename?: string;
  high_matches?: HighMatch[];
};

const badge: Record<Verdict, { label: string; className: string }> = {
  high_risk: { label: "High", className: "text-[#e36a6a]" },
  medium_risk: { label: "Medium", className: "text-[#f0b429]" },
  low_risk: { label: "Low", className: "text-[#c8e6c4]" },
};

function matchPercent(score: number) {
  return `${Math.round(score)}%`;
}

// One line per original. A single match still gets a score so every row looks the same.
function pairedOriginals(scan: ScanRow) {
  const high = scan.high_matches ?? [];
  if (high.length > 0) {
    return high.map((match) => ({
      title: match.protected_title,
      score: match.content_similarity ?? 0,
      verdict: "high_risk" as Verdict,
    }));
  }
  if (scan.protected_title) {
    return [{ title: scan.protected_title, score: scan.top_similarity ?? 0, verdict: scan.verdict }];
  }
  return [];
}

/** Format an API timestamp for the recent-scan history list. */
function when(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Fetch and render the most recent scan summaries from the backend. */
export function ScanFeed({
  refreshKey = 0,
  onOpen,
}: {
  refreshKey?: number;
  // Called when a past check is clicked, so the page can open that scan.
  onOpen?: (scanId: string) => void;
}) {
  const [scans, setScans] = useState<ScanRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  /** Fetch the current scan history and expose loading/error state to the view. */
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/scans`);
      if (!res.ok) throw new Error("Could not load past checks.");
      const json = (await res.json()) as { scans: ScanRow[] };
      setScans(json.scans ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load past checks.");
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    // Refresh the feed on mount and after a new scan is submitted.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load updates state asynchronously after the request completes.
    void load();
  }, [load, refreshKey]);

  return (
    <section className="mt-12">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-medium">Recent checks</h2>
        <span className="text-xs text-[#9b958c]">{loading ? "…" : scans.length}</span>
      </div>
      {error && <p className="text-sm text-[#f0b429]">{error}</p>}
      {!loading && !error && scans.length === 0 && (
        <p className="text-sm text-[#9b958c]">No checks yet.</p>
      )}
      <ul>
        {scans.map((scan) => (
          <li key={scan.scan_id} className="border-t border-white/10">
            <button
              type="button"
              className="grid w-full grid-cols-1 gap-3 py-3 text-left text-sm hover:bg-white/[0.03] sm:grid-cols-[1fr_1fr_7.5rem] sm:gap-4"
              onClick={() => onOpen?.(scan.scan_id)}
            >
              <span className="min-w-0">
                <span className="block text-[11px] text-[#6f6a62]">Checked video</span>
                <span className="mt-1 block truncate">
                  {scan.source_filename || "Name not saved"}
                </span>
                <span className="mt-1 block text-xs text-[#6f6a62]">{when(scan.scanned_at)}</span>
              </span>
              <span className="min-w-0">
                <span className="block text-[11px] text-[#6f6a62]">Your original</span>
                {pairedOriginals(scan).length === 0 ? (
                  <span className="mt-1 block text-[#9b958c]">No original matched</span>
                ) : (
                  pairedOriginals(scan).map((match, index) => (
                    <span key={`${match.title}-${index}`} className="mt-1 block truncate">
                      {match.title}
                    </span>
                  ))
                )}
              </span>
              <span>
                <span className="block text-[11px] text-[#6f6a62]">Match score</span>
                {pairedOriginals(scan).length === 0 ? (
                  <span className="mt-1 block text-[#9b958c]">None</span>
                ) : (
                  pairedOriginals(scan).map((match, index) => (
                    <span
                      key={`${match.title}-${index}`}
                      className={`mt-1 block ${badge[match.verdict]?.className ?? "text-[#9b958c]"}`}
                    >
                      {matchPercent(match.score)} {badge[match.verdict]?.label ?? match.verdict}
                    </span>
                  ))
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
