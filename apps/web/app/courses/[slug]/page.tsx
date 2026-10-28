import Link from "next/link";
import { notFound } from "next/navigation";

import { CoursePathway } from "@/components/course-pathway";
import { getCourse } from "@/lib/api";

export const dynamic = "force-dynamic";

type CoursePageProps = {
  params: Promise<{ slug: string }>;
};

export default async function CoursePage({ params }: CoursePageProps) {
  const { slug } = await params;
  const course = await getCourse(slug);
  if (!course) notFound();

  return (
    <main className="mx-auto min-h-[75vh] max-w-7xl px-5 pb-20 sm:px-8 sm:pb-28 lg:px-12">
      <div className="pt-8 sm:pt-12">
        <Link className="inline-flex rounded-sm text-sm font-semibold text-navy underline decoration-sage underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href="/">
          ← Back to the catalog
        </Link>
      </div>

      <header className="max-w-4xl border-b border-line py-10 sm:py-16">
        <p className="eyebrow">Course outline</p>
        <h1 className="mt-3 font-display text-5xl font-medium tracking-[-0.035em] text-navy sm:text-6xl">{course.title}</h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-muted">{course.description}</p>
        <p className="mt-6 max-w-3xl border-l-2 border-sage pl-4 text-sm leading-6 text-ink">{course.learning_rationale}</p>
        <p className="mt-6 max-w-3xl text-sm leading-6 text-muted" role="note">{course.curriculum_note}</p>
      </header>

      <section aria-labelledby="pathway-heading" className="pt-10 sm:pt-14">
        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Learning structure</p>
            <h2 id="pathway-heading" className="mt-2 font-display text-3xl font-medium text-ink sm:text-4xl">A pathway from foundations to depth</h2>
          </div>
          <p className="text-sm text-muted">{course.level_count} levels · {course.module_count} representative modules</p>
        </div>
        <CoursePathway levels={course.levels} />
      </section>
    </main>
  );
}
