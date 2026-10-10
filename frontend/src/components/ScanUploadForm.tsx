"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ScanResult } from "@/components/MatchResults";

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Props = {
  onScanned: (result: ScanResult) => void;
};

export function ScanUploadForm({ onScanned }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);
  const [over, setOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  useEffect(() => {
    if (!file) {
      setPreview(null);
      setSeconds(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function takeFile(next: File | undefined) {
    if (!next) return;
    setFile(next);
    setError(null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Drop a short first.");
      return;
    }

    setLoading(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);

    try {
      const res = await fetch(`${apiUrl}/api/scan`, { method: "POST", body });
      const json = (await res.json()) as ScanResult & { detail?: string };
      if (!res.ok) {
        throw new Error(
          typeof json.detail === "string" ? json.detail : "Could not check that file.",
        );
      }
      onScanned(json);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "The API is not answering.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          takeFile(event.dataTransfer.files?.[0]);
        }}
        className={`relative flex min-h-52 w-full flex-col items-center justify-center overflow-hidden rounded-2xl border text-left transition-colors ${
          over
            ? "border-[#f0b429] bg-[#f0b429]/10"
            : "border-white/15 bg-[#181816] hover:border-white/30"
        }`}
      >
        {preview ? (
          <video
            src={preview}
            muted
            playsInline
            className="absolute inset-0 h-full w-full object-cover opacity-50"
            onLoadedMetadata={(event) =>
              setSeconds(Math.round(event.currentTarget.duration))
            }
          />
        ) : null}
        <span className="relative text-sm text-[#f4f1ea]">
          {file ? file.name : over ? "Let go" : "Drop a short to check"}
        </span>
        <span className="relative mt-1 text-xs text-[#9b958c]">
          {file
            ? `${formatSize(file.size)}${seconds ? ` · ${seconds}s` : ""}`
            : "mp4 or mov, under 90s"}
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/quicktime,.mp4,.mov"
        className="hidden"
        onChange={(event) => takeFile(event.target.files?.[0])}
      />
      <button
        type="submit"
        disabled={loading || !file}
        className="mt-4 rounded-full bg-[#f4f1ea] px-4 py-2 text-sm font-medium text-[#10100e] transition-transform hover:-translate-y-0.5 active:translate-y-0 disabled:translate-y-0 disabled:opacity-40"
      >
        {loading ? "Checking…" : "Check"}
      </button>
      {error && <p className="mt-4 text-sm text-[#f0b429]">{error}</p>}
    </form>
  );
}
