import { HealthCheck } from "@/components/HealthCheck";

export default function Home() {
  return (
    <div className="min-h-full bg-zinc-950 text-zinc-50">
      <main className="mx-auto flex min-h-full max-w-4xl flex-col items-center justify-center px-6 py-16">
        <div className="mb-2 text-sm font-medium tracking-widest text-violet-400 uppercase">
          Vertex Veritas
        </div>
        <h1 className="mb-3 text-center text-4xl font-bold tracking-tight sm:text-5xl">
          ContentShield
        </h1>
        <p className="mb-10 max-w-xl text-center text-zinc-400">
          Real-time IP theft &amp; style clone detection for creators. Built for
          H2S Google Cloud AI Builder Cup.
        </p>

        <div className="mb-10 flex flex-wrap justify-center gap-3">
          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-sm text-violet-300">
            Content Match
          </span>
          <span className="rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-4 py-1.5 text-sm text-fuchsia-300">
            Style Match
          </span>
        </div>

        <HealthCheck />

        <p className="mt-10 text-center text-xs text-zinc-600">
          Day 1 scaffold — backend health check wired. Upload &amp; matching
          coming next.
        </p>
      </main>
    </div>
  );
}
