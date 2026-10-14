"use client";

import { useEffect, useState } from "react";
import { MatchDetail } from "@/components/MatchDetail";
import { ScanFeed } from "@/components/ScanFeed";
import { ScanUploadForm } from "@/components/ScanUploadForm";
import { ScanDetail, apiBase, errorMessage } from "@/components/scanTypes";

/** Render suspicious-video upload, match detail, and scan history. */
export default function CheckPage() {
  const [detail, setDetail] = useState<ScanDetail | null>(null);
  // Local preview of the file just checked. Past checks do not have this.
  const [suspiciousUrl, setSuspiciousUrl] = useState<string | null>(null);
  const [suspiciousTitle, setSuspiciousTitle] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  // Bumps after a new check so the recent list reloads.
  const [refreshKey, setRefreshKey] = useState(0);

  // Free the preview URL when it is replaced or the page closes.
  useEffect(() => {
    return () => {
      if (suspiciousUrl) URL.revokeObjectURL(suspiciousUrl);
    };
  }, [suspiciousUrl]);

  // Load one scan. Keep the just-finished result if the detail route is not ready yet.
  async function openScan(scanId: string, fallback?: ScanDetail) {
    setOpening(true);
    setDetailError(null);
    if (fallback) setDetail(fallback);
    try {
      const res = await fetch(`${apiBase()}/api/scans/${encodeURIComponent(scanId)}`);
      if (res.ok) {
        setDetail((await res.json()) as ScanDetail);
        return;
      }
      if (!fallback) {
        setDetail(null);
        setDetailError(await errorMessage(res, "That check could not be opened."));
      }
    } catch {
      if (!fallback) setDetailError("The API is not answering.");
    } finally {
      setOpening(false);
    }
  }

  return (
    <div className="pt-2">
      <h1 className="text-2xl font-medium tracking-tight">Check</h1>
      <p className="mt-1 text-sm text-[#9b958c]">Drop a short you think was copied.</p>
      <div className="mt-6">
        <ScanUploadForm
          onScanned={(scan, file) => {
            const nextUrl = URL.createObjectURL(file);
            setSuspiciousUrl(nextUrl);
            setSuspiciousTitle(file.name);
            setRefreshKey((value) => value + 1);
            void openScan(scan.scan_id, scan);
          }}
        />
      </div>
      <div className="mt-8">
        {opening && <p className="mb-3 text-sm text-[#9b958c]">Opening that check…</p>}
        {detailError && <p className="mb-3 text-sm text-[#f0b429]">{detailError}</p>}
        {/* New key resets the detail form when a different scan is opened. */}
        <MatchDetail
          key={`${detail?.scan_id ?? "empty"}-${detail?.verdict_explanation?.verdict_explanation_id ?? ""}-${detail?.dmca_draft?.draft_id ?? ""}`}
          detail={detail}
          suspiciousUrl={suspiciousUrl}
          suspiciousTitle={suspiciousTitle}
          onPromoted={() => {
            if (detail) void openScan(detail.scan_id);
          }}
        />
      </div>
      <ScanFeed
        refreshKey={refreshKey}
        onOpen={(scanId) => {
          setSuspiciousUrl(null);
          setSuspiciousTitle(null);
          void openScan(scanId);
        }}
      />
    </div>
  );
}
