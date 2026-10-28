import Link from "next/link";

export default function LessonNotFound() {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-4xl items-center px-5 py-16 sm:px-8">
      <section className="max-w-xl" aria-labelledby="lesson-not-found-heading">
        <p className="eyebrow">404 · Lesson not found</p>
        <h1 id="lesson-not-found-heading" className="mt-4 font-display text-4xl font-medium tracking-tight text-navy sm:text-5xl">This lesson isn’t available.</h1>
        <p className="mt-4 leading-7 text-muted">The lesson may have moved, or the address may be incomplete.</p>
        <Link className="mt-7 inline-flex rounded-sm font-semibold text-navy underline decoration-sage underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href="/courses/german">Return to German</Link>
      </section>
    </main>
  );
}
