"use client";

import { useState } from "react";
import { MatchResults, ScanResult } from "@/components/MatchResults";
import { ScanFeed } from "@/components/ScanFeed";
import { ScanUploadForm } from "@/components/ScanUploadForm";

/** Render suspicious-video upload, match results, and scan history. */
export default function CheckPage() {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="pt-2">
      <h1 className="text-2xl font-medium tracking-tight">Check</h1>
      <p className="mt-1 text-sm text-[#9b958c]">
        Drop a short you think was copied.
      </p>
      <div className="mt-6 grid gap-8 md:grid-cols-2">
        <ScanUploadForm
          onScanned={(scan) => {
            setResult(scan);
            setRefreshKey((value) => value + 1);
          }}
        />
        <MatchResults result={result} />
      </div>
      <ScanFeed refreshKey={refreshKey} />
    </div>
  );
}
