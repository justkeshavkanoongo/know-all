import Link from "next/link";

import { CourseCard } from "@/components/course-card";
import { getCourses } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let courses;
  try {
    courses = await getCourses();
  } catch {
    return (
      <main className="mx-auto min-h-[70vh] max-w-7xl px-5 py-16 sm:px-8 sm:py-24 lg:px-12">
        <div className="max-w-xl rounded-2xl border border-line bg-surface p-7 sm:p-9" role="alert">
          <p className="eyebrow">Catalog unavailable</p>
          <h1 className="mt-3 font-display text-3xl font-medium text-ink">We couldn’t reach the course catalog.</h1>
          <p className="mt-3 leading-7 text-muted">Please make sure the Know It All API is running, then try again.</p>
          <Link className="mt-6 inline-flex rounded-sm font-semibold text-navy underline decoration-sage underline-offset-4" href="/">
            Try again
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-5 pb-20 sm:px-8 sm:pb-28 lg:px-12">
      <section className="grid gap-8 border-b border-line py-14 sm:py-20 lg:grid-cols-[1fr_22rem] lg:items-end lg:gap-16 lg:py-24">
        <div className="max-w-3xl">
          <p className="eyebrow">A place for curious minds</p>
          <h1 className="mt-5 max-w-3xl font-display text-5xl font-medium leading-[1.05] tracking-[-0.035em] text-navy sm:text-6xl lg:text-7xl">
            A richer way to learn, one idea at a time.
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-muted sm:text-lg sm:leading-8">
            Explore language, literature, psychology and philosophy through clear learning paths built for lasting understanding.
          </p>
        </div>
        <aside className="border-l-2 border-sage pl-5 lg:mb-1" aria-label="About the catalog">
          <p className="font-display text-xl leading-7 text-ink">Start with a subject that keeps you asking better questions.</p>
          <p className="mt-3 text-sm leading-6 text-muted">Five focused course outlines. Each one is a beginning, with room to grow.</p>
        </aside>
      </section>

      <section aria-labelledby="courses-heading" className="pt-12 sm:pt-16">
        <div className="mb-7 flex flex-col gap-2 sm:mb-9 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">The catalog</p>
            <h2 id="courses-heading" className="mt-2 font-display text-3xl font-medium tracking-tight text-ink sm:text-4xl">Choose a path to explore</h2>
          </div>
          <p className="text-sm text-muted">{courses.length} subjects to begin with</p>
        </div>

        {courses.length === 0 ? (
          <div className="rounded-2xl border border-line bg-surface p-8" role="status">
            <h3 className="font-display text-2xl text-ink">The catalog is taking shape.</h3>
            <p className="mt-2 text-muted">Please check back when courses are available.</p>
          </div>
        ) : (
          <ul className="grid list-none gap-4 p-0 sm:grid-cols-2 xl:grid-cols-3">
            {courses.map((course, index) => (
              <li key={course.id}>
                <CourseCard course={course} index={index} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
