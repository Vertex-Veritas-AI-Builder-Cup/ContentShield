"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HealthCheck } from "@/components/HealthCheck";

const tabs = [
  { href: "/", label: "Home" },
  { href: "/catalog", label: "Originals" },
  { href: "/monitor", label: "Check" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-[#10100e]/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link href="/" className="text-[15px] font-medium tracking-tight">
            ContentShield
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            {tabs.map((tab) => {
              const active = pathname === tab.href;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`rounded-md px-2.5 py-1 transition-colors ${
                    active
                      ? "bg-white/10 text-[#f4f1ea]"
                      : "text-[#9b958c] hover:bg-white/5 hover:text-[#f4f1ea]"
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <div className="mx-auto w-full max-w-3xl px-4 py-10">{children}</div>
      <footer className="mx-auto flex max-w-3xl justify-end px-4 pb-8">
        <HealthCheck />
      </footer>
    </div>
  );
}
