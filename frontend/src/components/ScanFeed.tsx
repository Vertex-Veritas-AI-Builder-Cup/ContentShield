"use client";

import { useCallback, useEffect, useState } from "react";
import { Verdict } from "@/components/MatchResults";

type ScanRow = {
  scan_id: string;
  top_similarity: number;
  verdict: Verdict;
  scanned_at: string;
};

const badge: Record<Verdict, { label: string; className: string }> = {
  high_risk: { label: "High", className: "text-[#e36a6a]" },
  medium_risk: { label: "Medium", className: "text-[#f0b429]" },
  low_risk: { label: "Low", className: "text-[#c8e6c4]" },
};

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

export function ScanFeed({ refreshKey = 0 }: { refreshKey?: number }) {
  const [scans, setScans] = useState<ScanRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
          <li
            key={scan.scan_id}
            className="flex items-center justify-between border-t border-white/10 py-3 text-sm"
          >
            <span className="text-[#9b958c]">{when(scan.scanned_at)}</span>
            <span className="flex items-center gap-3">
              <span>{Math.round((scan.top_similarity ?? 0) * 100)}%</span>
              <span className={badge[scan.verdict]?.className ?? "text-[#9b958c]"}>
                {badge[scan.verdict]?.label ?? scan.verdict}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
