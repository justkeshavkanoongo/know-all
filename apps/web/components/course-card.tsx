import Link from "next/link";

import type { CourseSummary } from "@/lib/api";

type CourseCardProps = {
  course: CourseSummary;
  index: number;
};

const numerals = ["01", "02", "03", "04", "05"];

export function CourseCard({ course, index }: CourseCardProps) {
  return (
    <article className="group flex min-h-64 flex-col rounded-2xl border border-line bg-surface p-6 shadow-[0_2px_10px_rgba(36,48,71,0.025)] transition-colors hover:border-sage/70 sm:p-7">
      <div className="mb-8 flex items-start justify-between gap-4">
        <span className="eyebrow">Course {numerals[index] ?? String(index + 1).padStart(2, "0")}</span>
        <span aria-label={`${course.level_count} learning levels`} className="rounded-full bg-paper px-3 py-1 text-xs font-medium text-muted">
          {course.level_count} levels
        </span>
      </div>
      <h2 className="font-display text-3xl font-medium tracking-tight text-ink sm:text-4xl">
        <Link className="rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href={`/courses/${course.slug}`}>
          {course.title}
        </Link>
      </h2>
      <p className="mt-3 max-w-md text-sm leading-6 text-muted sm:text-base">{course.description}</p>
      <div className="mt-auto flex items-center justify-between gap-4 pt-7">
        <span className="text-xs text-muted">{course.module_count} representative modules</span>
        <Link className="inline-flex items-center gap-2 rounded-sm text-sm font-semibold text-navy focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href={`/courses/${course.slug}`}>
          Explore <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">→</span>
        </Link>
      </div>
    </article>
  );
}
