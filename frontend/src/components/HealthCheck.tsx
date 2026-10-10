"use client";

import { useState } from "react";

/** Render a small control that reports whether the backend is reachable. */
export function HealthCheck() {
  const [state, setState] = useState<"idle" | "ok" | "down" | "busy">("idle");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  /** Call the backend health endpoint and update the connection state. */
  async function ping() {
    setState("busy");
    try {
      const res = await fetch(`${apiUrl}/health`);
      setState(res.ok ? "ok" : "down");
    } catch {
      setState("down");
    }
  }

  const label =
    state === "busy" ? "Checking" : state === "ok" ? "API up" : state === "down" ? "API down" : "API";

  return (
    <button
      type="button"
      onClick={ping}
      className="text-xs text-[#6f6a62] hover:text-[#9b958c]"
    >
      {label}
    </button>
  );
}
