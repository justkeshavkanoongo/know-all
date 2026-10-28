import type { CourseLevel } from "@/lib/api";

type CoursePathwayProps = {
  levels: CourseLevel[];
};

export function CoursePathway({ levels }: CoursePathwayProps) {
  return (
    <ol className="grid gap-4 md:grid-cols-2">
      {levels.map((level, index) => (
        <li key={level.id} className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
          <div className="flex items-start gap-4">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-paper font-display text-sm font-semibold text-navy" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0">
              <p className="eyebrow">{level.label}</p>
              <h3 className="mt-1 font-display text-xl font-medium text-ink">{level.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted">{level.description}</p>
            </div>
          </div>
          <ul className="mt-5 space-y-3 border-t border-line pt-4">
            {level.modules.map((module) => (
              <li key={module.id}>
                <h4 className="text-sm font-semibold text-ink">{module.title}</h4>
                <p className="mt-1 text-sm leading-5 text-muted">{module.description}</p>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
