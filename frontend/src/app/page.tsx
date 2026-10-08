import Link from "next/link";

export default function Home() {
  return (
    <section className="pt-8">
      <p className="text-sm text-[#f0b429]">YouTube Shorts · Reels · any file</p>
      <h1 className="mt-3 max-w-md text-4xl font-medium leading-tight tracking-tight">
        Your short. Then the copy.
      </h1>
      <p className="mt-4 max-w-sm text-[#9b958c]">
        Save a few originals. Check one suspicious clip against them.
      </p>
      <Link
        href="/catalog"
        className="mt-8 inline-flex items-center rounded-full bg-[#f0b429] px-5 py-2.5 text-sm font-medium text-[#1a1408] transition-transform hover:-translate-y-0.5 active:translate-y-0"
      >
        Add an original
      </Link>
    </section>
  );
}
