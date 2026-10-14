"use client";

import { useCallback, useEffect, useState } from "react";

export type Clip = {
  clip_id: string;
  title: string;
  status: string;
  created_at: string;
};

/** Load and render protected originals, including confirmation-based deletion. */
export function ClipCatalog({ refreshKey = 0 }: { refreshKey?: number }) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  /** Fetch the latest protected clip catalog from the backend. */
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`${apiUrl}/api/clips`);
      if (!res.ok) throw new Error("Could not load originals.");
      const json = (await res.json()) as { clips: Clip[] };
      setClips(json.clips ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load originals.");
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    // Refresh the catalog on mount and whenever the parent signals a change.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load updates state asynchronously after the request completes.
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    if (!clips.some((clip) => clip.status === "processing")) return;
    const timer = window.setTimeout(() => void load(), 5000);
    return () => window.clearTimeout(timer);
  }, [clips, load]);

  /** Delete one protected original after the user confirms the action. */
  async function remove(clipId: string) {
    setDeletingId(clipId);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`${apiUrl}/api/clips/${encodeURIComponent(clipId)}`, {
        method: "DELETE",
      });
      const json = (await res.json().catch(() => ({}))) as { detail?: string; deleted?: string };
      if (!res.ok || json.deleted !== clipId) {
        throw new Error(
          typeof json.detail === "string" ? json.detail : "Could not remove that original.",
        );
      }
      setPendingDelete(null);
      await load();
      setNotice("Removed. Add another above if you want.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove that original.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="mt-12">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-medium">Originals</h2>
        <span className="text-xs text-[#9b958c]">
          {loading ? "…" : clips.length}
        </span>
      </div>

      {notice && <p className="mb-3 text-sm text-[#c8e6c4]">{notice}</p>}
      {error && <p className="mb-3 text-sm text-[#f0b429]">{error}</p>}

      {!loading && !error && clips.length === 0 && (
        <p className="rounded-xl border border-dashed border-white/15 px-4 py-6 text-sm text-[#9b958c]">
          Empty shelf. Add the short people keep copying.
        </p>
      )}

      <ul>
        {clips.map((clip) => (
          <li
            key={clip.clip_id}
            className="group flex items-center justify-between border-t border-white/10 py-3 transition-colors hover:bg-white/[0.03]"
          >
            <span className="min-w-0 truncate pr-4">
              <span className="block truncate">{clip.title || "Untitled"}</span>
              {clip.status !== "fingerprinted" && (
                <span
                  className={`mt-1 block text-xs ${
                    clip.status === "failed" ? "text-[#e36a6a]" : "text-[#f0b429]"
                  }`}
                >
                  {clip.status === "failed" ? "Fingerprinting failed" : "Fingerprinting in progress"}
                </span>
              )}
            </span>
            {pendingDelete === clip.clip_id ? (
              <span className="flex shrink-0 items-center gap-3 text-xs">
                <button
                  type="button"
                  className="text-[#f0b429] hover:text-[#f4f1ea] disabled:opacity-50"
                  disabled={deletingId === clip.clip_id}
                  onClick={() => void remove(clip.clip_id)}
                >
                  {deletingId === clip.clip_id ? "Removing…" : "Confirm"}
                </button>
                <button
                  type="button"
                  className="text-[#9b958c] hover:text-[#f4f1ea]"
                  disabled={deletingId === clip.clip_id}
                  onClick={() => setPendingDelete(null)}
                >
                  Keep
                </button>
              </span>
            ) : (
              <button
                type="button"
                className="shrink-0 text-xs text-[#9b958c] hover:text-[#f4f1ea] disabled:opacity-40"
                disabled={deletingId !== null}
                onClick={() => {
                  setNotice(null);
                  setPendingDelete(clip.clip_id);
                }}
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
