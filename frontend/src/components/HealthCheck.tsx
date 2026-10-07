"use client";

import { useCallback, useState } from "react";

type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

export function HealthCheck() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const checkHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const res = await fetch(`${apiUrl}/health`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const json = (await res.json()) as HealthResponse;
      setData(json);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not reach backend. Is it running on port 8000?",
      );
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  return (
    <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900/80 p-6 shadow-xl">
      <h2 className="mb-1 text-sm font-medium text-zinc-400">API Status</h2>
      <p className="mb-4 font-mono text-xs text-zinc-500">{apiUrl}/health</p>

      <button
        type="button"
        onClick={checkHealth}
        disabled={loading}
        className="w-full rounded-xl bg-violet-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:opacity-50"
      >
        {loading ? "Checking…" : "Check Backend Health"}
      </button>

      {data && (
        <div className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
          <p className="text-sm font-medium text-emerald-400">Connected</p>
          <pre className="mt-2 overflow-x-auto text-xs text-emerald-200/80">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <p className="text-sm font-medium text-red-400">Connection failed</p>
          <p className="mt-1 text-xs text-red-300/80">{error}</p>
          <p className="mt-2 text-xs text-zinc-500">
            Run backend:{" "}
            <code className="text-zinc-400">
              cd backend &amp;&amp; uvicorn app.main:app --reload
            </code>
          </p>
        </div>
      )}
    </div>
  );
}
