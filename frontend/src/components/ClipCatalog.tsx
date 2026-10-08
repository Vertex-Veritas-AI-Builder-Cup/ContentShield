"use client";

import { useCallback, useEffect, useState } from "react";

export type Clip = {
  clip_id: string;
  title: string;
  status: string;
  created_at: string;
};

export function ClipCatalog({ refreshKey = 0 }: { refreshKey?: number }) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
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
    void load();
  }, [load, refreshKey]);

  async function remove(clipId: string) {
    setDeletingId(clipId);
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/clips/${clipId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Could not remove that original.");
      setClips((current) => current.filter((clip) => clip.clip_id !== clipId));
      setPendingDelete(null);
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

      {error && <p className="text-sm text-[#f0b429]">{error}</p>}

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
            <span>{clip.title || "Untitled"}</span>
            {pendingDelete === clip.clip_id ? (
              <span className="flex items-center gap-2 text-xs">
                <button
                  type="button"
                  className="text-[#f0b429] hover:text-[#f4f1ea]"
                  disabled={deletingId === clip.clip_id}
                  onClick={() => void remove(clip.clip_id)}
                >
                  {deletingId === clip.clip_id ? "Removing…" : "Confirm"}
                </button>
                <button
                  type="button"
                  className="text-[#9b958c] hover:text-[#f4f1ea]"
                  onClick={() => setPendingDelete(null)}
                >
                  Keep
                </button>
              </span>
            ) : (
              <button
                type="button"
                className="text-xs text-[#6f6a62] hover:text-[#f4f1ea]"
                onClick={() => setPendingDelete(clip.clip_id)}
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
