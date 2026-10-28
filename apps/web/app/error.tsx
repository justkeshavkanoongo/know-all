"use client";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto min-h-[70vh] max-w-7xl px-5 py-16 sm:px-8 sm:py-24 lg:px-12">
      <section className="max-w-xl rounded-2xl border border-line bg-surface p-7 sm:p-9" role="alert">
        <p className="eyebrow">Something went wrong</p>
        <h1 className="mt-3 font-display text-3xl font-medium text-ink">The course page couldn’t load.</h1>
        <p className="mt-3 leading-7 text-muted">Check that the API is running, then try again.</p>
        <button className="mt-6 rounded-sm bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy/90" onClick={() => reset()} type="button">
          Try again
        </button>
      </section>
    </main>
  );
}
