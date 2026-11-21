"use client";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main id="main" className="grid min-h-dvh place-items-center px-4 text-center">
      <div>
        <h1 className="text-xl font-semibold">Something went wrong</h1>
        <p className="mt-2 text-muted">An unexpected error occurred while rendering this page.</p>
        <button onClick={reset} className="mt-6 rounded-xl bg-forest px-4 py-2 text-sm font-medium text-white">Try again</button>
      </div>
    </main>
  );
}
