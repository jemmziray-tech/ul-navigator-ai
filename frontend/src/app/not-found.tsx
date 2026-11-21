import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" className="grid min-h-dvh place-items-center px-4 text-center">
      <div>
        <p className="font-display text-6xl font-semibold text-emerald">404</p>
        <h1 className="mt-3 text-xl font-semibold">This page wandered off campus</h1>
        <p className="mt-2 text-muted">The page you&apos;re looking for doesn&apos;t exist.</p>
        <Link href="/" className="mt-6 inline-block rounded-xl bg-forest px-4 py-2 text-sm font-medium text-white">Back to home</Link>
      </div>
    </main>
  );
}
