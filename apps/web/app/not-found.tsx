import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-7xl items-center px-5 py-16 sm:px-8 lg:px-12">
      <section className="max-w-xl" aria-labelledby="not-found-heading">
        <p className="eyebrow">404 · Course not found</p>
        <h1 id="not-found-heading" className="mt-4 font-display text-4xl font-medium tracking-tight text-navy sm:text-5xl">This path isn’t in the catalog.</h1>
        <p className="mt-4 leading-7 text-muted">The course may have moved, or the address may be incomplete.</p>
        <Link className="mt-7 inline-flex rounded-sm font-semibold text-navy underline decoration-sage underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href="/">
          Return to all courses
        </Link>
      </section>
    </main>
  );
}
