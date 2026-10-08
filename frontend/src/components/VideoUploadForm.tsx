"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type RegisterResponse = {
  clip_id: string;
  title?: string;
  status: string;
};

type Props = {
  onRegistered?: () => void;
};

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function VideoUploadForm({ onRegistered }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [seconds, setSeconds] = useState<number | null>(null);
  const [over, setOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
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
    setSaved(null);
    setError(null);
    if (!title) {
      setTitle(next.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Drop a short first.");
      return;
    }

    setLoading(true);
    setError(null);
    setSaved(null);

    const body = new FormData();
    body.append("file", file);
    if (title.trim()) body.append("title", title.trim());

    try {
      const res = await fetch(`${apiUrl}/api/clips/register`, {
        method: "POST",
        body,
      });
      const json = (await res.json()) as RegisterResponse & { detail?: string };
      if (!res.ok) {
        throw new Error(
          typeof json.detail === "string" ? json.detail : "Could not save that file.",
        );
      }
      setSaved(json.clip_id);
      setFile(null);
      setTitle("");
      if (inputRef.current) inputRef.current.value = "";
      onRegistered?.();
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
        className={`group relative flex min-h-52 w-full flex-col items-center justify-center overflow-hidden rounded-2xl border text-left transition-colors ${
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
        ) : (
          <div className="pointer-events-none absolute inset-x-8 top-1/2 h-px -translate-y-8 bg-white/10" />
        )}
        <span className="relative text-sm text-[#f4f1ea]">
          {file ? file.name : over ? "Let go" : "Drop a Short or Reel"}
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

      <label className="mt-4 block text-xs text-[#9b958c]">
        Title
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Monday hook"
          className="mt-1 w-full rounded-lg border border-white/10 bg-transparent px-3 py-2 text-sm text-[#f4f1ea] outline-none placeholder:text-[#6f6a62] focus:border-[#f0b429]"
        />
      </label>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="submit"
          disabled={loading || !file}
          className="rounded-full bg-[#f4f1ea] px-4 py-2 text-sm font-medium text-[#10100e] transition-transform hover:-translate-y-0.5 active:translate-y-0 disabled:translate-y-0 disabled:opacity-40"
        >
          {loading ? "Saving…" : "Save original"}
        </button>
        {file && (
          <button
            type="button"
            className="text-sm text-[#9b958c] hover:text-[#f4f1ea]"
            onClick={() => {
              setFile(null);
              setTitle("");
              if (inputRef.current) inputRef.current.value = "";
            }}
          >
            Clear
          </button>
        )}
      </div>

      {saved && (
        <p className="mt-4 text-sm text-[#c8e6c4]">Saved. It is on your shelf.</p>
      )}
      {error && <p className="mt-4 text-sm text-[#f0b429]">{error}</p>}
    </form>
  );
}
