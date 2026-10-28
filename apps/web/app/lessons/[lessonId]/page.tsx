import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { LessonLearningExperience } from "@/components/lesson-learning-experience";
import { getLesson } from "@/lib/api";

export const dynamic = "force-dynamic";

export function generateStaticParams() {
  return [{ lessonId: "german-a1-greetings" }];
}

type LessonPageProps = { params: Promise<{ lessonId: string }> };

export const metadata: Metadata = { title: "German A1 — Greetings and introductions" };

export default async function LessonPage({ params }: LessonPageProps) {
  const { lessonId } = await params;
  let lesson;
  try {
    lesson = await getLesson(lessonId);
  } catch {
    return (
      <main className="mx-auto min-h-[70vh] max-w-4xl px-5 py-16 sm:px-8 sm:py-24" role="alert">
        <p className="eyebrow">Lesson unavailable</p>
        <h1 className="mt-3 font-display text-4xl font-medium text-navy">We couldn’t load this lesson.</h1>
        <p className="mt-4 leading-7 text-muted">Please make sure the Know It All API is running, then try again.</p>
        <Link className="mt-7 inline-flex font-semibold text-navy underline decoration-sage underline-offset-4" href="/courses/german">Return to German</Link>
      </main>
    );
  }
  if (!lesson) notFound();

  const lessonContent = lesson;

  return (
    <main className="mx-auto max-w-4xl px-5 pb-20 sm:px-8 sm:pb-28">
      <div className="pt-8 sm:pt-12">
        <Link className="inline-flex rounded-sm text-sm font-semibold text-navy underline decoration-sage underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href="/courses/german">← Back to German</Link>
      </div>
      <header className="border-b border-line py-10 sm:py-16">
        <p className="eyebrow">{lessonContent.course.title} · {lessonContent.level.title}</p>
        <h1 className="mt-3 font-display text-4xl font-medium tracking-[-0.035em] text-navy sm:text-6xl">{lessonContent.title}</h1>
        <p className="mt-4 text-sm text-muted">Reviewed lesson · Content version {lessonContent.content_version}</p>
        <section aria-labelledby="objectives-heading" className="mt-8 rounded-2xl border border-line bg-surface p-5 sm:p-7">
          <h2 id="objectives-heading" className="font-display text-2xl font-medium text-ink">By the end, you can</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-muted sm:text-base">
            {lessonContent.objectives.map((objective) => <li key={objective.id}>{objective.description}</li>)}
          </ul>
        </section>
        <Link className="mt-5 inline-flex rounded-sm font-semibold text-navy underline decoration-sage underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href="#practice">
          Jump to practice exercises ↓
        </Link>
        <Link className="ml-5 mt-5 inline-flex rounded-sm font-semibold text-navy underline decoration-sage underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" href="#assessment">
          Jump to assessment ↓
        </Link>
      </header>

      <section aria-labelledby="vocabulary-heading" className="border-b border-line py-10 sm:py-12">
        <p className="eyebrow">Useful language</p>
        <h2 id="vocabulary-heading" className="mt-2 font-display text-3xl font-medium text-ink">Vocabulary</h2>
        <ul className="mt-6 grid list-none gap-3 p-0 sm:grid-cols-2">
          {lessonContent.vocabulary.map((item) => (
            <li key={item.term} className="rounded-xl border border-line bg-surface p-4">
              <h3 className="font-semibold text-ink">{item.term} <span className="font-normal text-muted">— {item.translation}</span></h3>
              <p className="mt-3 text-sm font-medium text-navy">{item.example}</p>
              <p className="mt-1 text-sm text-muted">{item.example_translation}</p>
              {item.pronunciation_note && <p className="mt-2 text-xs leading-5 text-muted">Pronunciation: {item.pronunciation_note}</p>}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="grammar-heading" className="border-b border-line py-10 sm:py-12">
        <p className="eyebrow">Form and meaning</p>
        <h2 id="grammar-heading" className="mt-2 font-display text-3xl font-medium text-ink">Grammar notes</h2>
        <div className="mt-6 space-y-4">
          {lessonContent.grammar.map((item) => (
            <article key={item.id} className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
              <h3 className="font-display text-xl font-medium text-ink">{item.title}</h3>
              <p className="mt-2 leading-7 text-muted">{item.explanation}</p>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-navy">{item.examples.map((example) => <li key={example}>{example}</li>)}</ul>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="steps-heading" className="border-b border-line py-10 sm:py-12">
        <p className="eyebrow">Build the exchange</p>
        <h2 id="steps-heading" className="mt-2 font-display text-3xl font-medium text-ink">Step by step</h2>
        <div className="mt-6 space-y-8">
          {lessonContent.sections.map((section) => (
            <article key={section.section_id}>
              <h3 className="font-display text-2xl font-medium text-ink">{section.title}</h3>
              <p className="mt-2 leading-7 text-muted">{section.introduction}</p>
              <ol className="mt-4 space-y-4 border-l border-sage pl-5 sm:pl-6">
                {section.steps.map((step, index) => (
                  <li key={`${section.section_id}-${index}`}>
                    <h4 className="font-semibold text-ink">{step.title}</h4>
                    <p className="mt-1 text-sm leading-6 text-muted">{step.explanation}</p>
                    <p className="mt-2 text-sm font-medium text-navy">{step.example}</p>
                  </li>
                ))}
              </ol>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="dialogues-heading" className="border-b border-line py-10 sm:py-12">
        <p className="eyebrow">In conversation</p>
        <h2 id="dialogues-heading" className="mt-2 font-display text-3xl font-medium text-ink">Example dialogues</h2>
        <div className="mt-6 space-y-5">
          {lessonContent.dialogues.map((dialogue) => (
            <article key={dialogue.dialogue_id} className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
              <h3 className="font-display text-xl font-medium text-ink">{dialogue.title}</h3>
              <p className="mt-1 text-sm text-muted">{dialogue.context}</p>
              <ol className="mt-4 space-y-4">
                {dialogue.turns.map((turn, index) => (
                  <li key={`${dialogue.dialogue_id}-${index}`}>
                    <p className="text-sm font-semibold text-sage">{turn.speaker}</p>
                    <p className="mt-1 font-medium text-navy">{turn.text}</p>
                    <p className="mt-1 text-sm text-muted">{turn.translation}</p>
                  </li>
                ))}
              </ol>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="mistakes-heading" className="border-b border-line py-10 sm:py-12">
        <p className="eyebrow">Watch for these</p>
        <h2 id="mistakes-heading" className="mt-2 font-display text-3xl font-medium text-ink">Common mistakes</h2>
        <ul className="mt-6 list-none space-y-3 p-0">
          {lessonContent.common_mistakes.map((mistake) => (
            <li key={mistake.incorrect} className="rounded-xl border border-line bg-surface p-4">
              <p className="text-sm text-muted"><span className="font-semibold text-ink">Instead of:</span> <del>{mistake.incorrect}</del></p>
              <p className="mt-1 text-sm text-navy"><span className="font-semibold">Use:</span> {mistake.correction}</p>
              <p className="mt-2 text-sm leading-6 text-muted">{mistake.explanation}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="recap-heading" className="py-10 sm:py-12">
        <p className="eyebrow">Keep in mind</p>
        <h2 id="recap-heading" className="mt-2 font-display text-3xl font-medium text-ink">Recap</h2>
        <ol className="mt-5 list-decimal space-y-2 pl-5 leading-7 text-muted">{lessonContent.recap.map((item) => <li key={item}>{item}</li>)}</ol>
      </section>

      <LessonLearningExperience lessonId={lessonContent.lesson_id} concepts={lessonContent.concepts} />

      <aside className="rounded-2xl border border-line bg-surface p-5 sm:p-6" aria-label="Lesson concepts">
        <h2 className="font-display text-xl font-medium text-ink">Concepts in this lesson</h2>
        <ul className="mt-3 flex flex-wrap gap-2">{lessonContent.concepts.map((concept) => <li key={concept.id} className="rounded-full bg-paper px-3 py-1.5 text-xs font-semibold text-navy" title={concept.description}>{concept.title}</li>)}</ul>
      </aside>
    </main>
  );
}
