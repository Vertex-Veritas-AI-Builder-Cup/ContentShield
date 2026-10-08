"use client";

import { useState } from "react";
import { ClipCatalog } from "@/components/ClipCatalog";
import { VideoUploadForm } from "@/components/VideoUploadForm";

export default function CatalogPage() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="pt-2">
      <h1 className="text-2xl font-medium tracking-tight">Originals</h1>
      <p className="mt-1 text-sm text-[#9b958c]">
        YouTube Shorts, Reels, or a file from your phone.
      </p>
      <div className="mt-6">
        <VideoUploadForm onRegistered={() => setRefreshKey((value) => value + 1)} />
      </div>
      <ClipCatalog refreshKey={refreshKey} />
    </div>
  );
}
