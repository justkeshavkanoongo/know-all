"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import type { AssessmentAttempt, AssessmentResult, PracticeSet } from "@/lib/api";
import {
  browserProgressStorage,
  emptyProgress,
  MASTERY_RULES,
  progressView,
  recordAssessmentResult,
  recordPracticeOutcome,
  type ConceptDefinition,
  type ProgressLoadStatus,
  type ProgressState,
  XP_RULES,
} from "@/lib/progress";

type ProgressContextValue = {
  status: ProgressLoadStatus | "loading";
  view: ReturnType<typeof progressView>;
  recordPractice: (practice: PracticeSet, exerciseId: string, conceptId: string, correct: boolean) => void;
  recordAssessment: (attempt: AssessmentAttempt, result: AssessmentResult) => void;
  reset: () => void;
};

const ProgressContext = createContext<ProgressContextValue | null>(null);

export function ProgressProvider({ lessonId, concepts, children }: { lessonId: string; concepts: ConceptDefinition[]; children: React.ReactNode }) {
  const [state, setState] = useState<ProgressState>(emptyProgress);
  const stateRef = useRef(state);
  const [status, setStatus] = useState<ProgressLoadStatus | "loading">("loading");
  const [storage, setStorage] = useState<ReturnType<typeof browserProgressStorage> | null>(null);

  useEffect(() => {
    try {
      const repository = browserProgressStorage();
      const loaded = repository.load();
      setStorage(repository);
      stateRef.current = loaded.state;
      setState(loaded.state);
      setStatus(loaded.status);
    } catch {
      setStorage(null);
      stateRef.current = emptyProgress();
      setState(emptyProgress());
      setStatus("unavailable");
    }
  }, []);

  const update = useCallback((transform: (current: ProgressState) => ProgressState) => {
    if (status === "loading" || status === "corrupt" || status === "outdated") return;
    const next = transform(stateRef.current);
    stateRef.current = next;
    setState(next);
    if (storage && !storage.save(next)) setStatus("unavailable");
  }, [status, storage]);

  const recordPractice = useCallback((practice: PracticeSet, exerciseId: string, conceptId: string, correct: boolean) => {
    update((current) => recordPracticeOutcome(current, { lesson_id: lessonId, practice, exercise_id: exerciseId, concept_id: conceptId, correct }));
  }, [lessonId, update]);

  const recordAssessment = useCallback((attempt: AssessmentAttempt, result: AssessmentResult) => {
    update((current) => recordAssessmentResult(current, attempt, result));
  }, [update]);

  const reset = useCallback(() => {
    const cleared = storage?.reset() ?? false;
    stateRef.current = emptyProgress();
    setState(emptyProgress());
    setStatus(cleared ? "empty" : "unavailable");
  }, [storage]);

  const value = useMemo<ProgressContextValue>(() => ({
    status,
    view: progressView(state, concepts, lessonId),
    recordPractice,
    recordAssessment,
    reset,
  }), [status, state, concepts, lessonId, recordPractice, recordAssessment, reset]);

  return <ProgressContext.Provider value={value}>{children}</ProgressContext.Provider>;
}

function useProgress(): ProgressContextValue {
  const value = useContext(ProgressContext);
  if (!value) throw new Error("Progress UI must be rendered inside ProgressProvider.");
  return value;
}

export function ProgressPanel({ lessonId, concepts }: { lessonId: string; concepts: ConceptDefinition[] }) {
  const { status, view, reset } = useProgress();
  if (status === "loading") return <section aria-labelledby="progress-heading" className="border-t border-line py-10 sm:py-12"><h2 id="progress-heading" className="font-display text-3xl font-medium text-ink">Your learning progress</h2><p className="mt-4 text-sm text-muted" role="status">Loading your saved progress…</p></section>;

  const unavailable = status === "unavailable";
  const invalid = status === "corrupt" || status === "outdated";
  return (
    <section aria-labelledby="progress-heading" className="border-t border-line py-10 sm:py-12">
      <p className="eyebrow">Your learning, over time</p>
      <h2 id="progress-heading" className="mt-2 font-display text-3xl font-medium text-ink">Your learning progress</h2>
      {unavailable && <p className="mt-4 rounded-xl border border-line bg-surface p-4 text-sm leading-6 text-muted" role="status">Browser storage is unavailable. Progress is held in memory for this page only and will not survive leaving it.</p>}
      {invalid && <div className="mt-4 rounded-xl border border-line bg-surface p-4" role="alert"><p className="text-sm leading-6 text-muted">{status === "corrupt" ? "Saved progress could not be read safely." : "Saved progress uses an unsupported version."} It has not been overwritten. Reset local progress to start fresh; previous data cannot be migrated automatically.</p><button type="button" className="mt-3 rounded-sm border border-line px-4 py-2 text-sm font-semibold text-navy focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" onClick={() => { if (window.confirm("Clear this browser's saved learning progress?")) reset(); }}>Reset local progress</button></div>}
      {!invalid && <>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <article className="rounded-xl border border-line bg-surface p-4"><p className="text-xs font-semibold uppercase tracking-wide text-muted">Lesson</p><p className="mt-2 font-semibold text-ink">{view.lesson_completed ? "Completed" : "In progress"}</p><p className="mt-1 text-sm text-muted">Completion follows a full checked practice set or submitted assessment.</p></article>
          <article className="rounded-xl border border-line bg-surface p-4"><p className="text-xs font-semibold uppercase tracking-wide text-muted">Practice</p><p className="mt-2 font-semibold text-ink">{view.completed_practice_sets} set{view.completed_practice_sets === 1 ? "" : "s"} complete</p><p className="mt-1 text-sm text-muted">{view.practice_outcomes} checked exercise outcomes</p></article>
          <article className="rounded-xl border border-line bg-surface p-4"><p className="text-xs font-semibold uppercase tracking-wide text-muted">Assessment</p><p className="mt-2 font-semibold text-ink">{view.assessment_history.length ? `${view.assessment_history.at(-1)?.score_percent}% latest score` : "No submitted assessment"}</p><p className="mt-1 text-sm text-muted">{view.assessment_history.length ? `${view.assessment_history.length} attempt recorded locally` : "Scores appear after server scoring."}</p></article>
          <article className="rounded-xl border border-line bg-surface p-4"><p className="text-xs font-semibold uppercase tracking-wide text-muted">Experience</p><p className="mt-2 font-semibold text-ink">Level {view.level} · {view.total_xp} XP</p><p className="mt-1 text-sm text-muted">{view.xp_to_next_level} XP to level {view.level + 1}</p><progress aria-label={`${view.xp_in_level} of ${XP_RULES.xpPerLevel} XP toward level ${view.level + 1}`} className="mt-3 h-2 w-full accent-sage" max={XP_RULES.xpPerLevel} value={view.xp_in_level} /></article>
        </div>
        <div className="mt-7 grid gap-6 lg:grid-cols-2">
          <section aria-labelledby="concept-progress-heading"><h3 id="concept-progress-heading" className="font-display text-xl font-medium text-ink">Concept progress</h3><p className="mt-1 text-sm leading-6 text-muted">Mastery requires at least {MASTERY_RULES.minimumEvidence} distinct checked answers and {MASTERY_RULES.minimumCorrectPercent}% accuracy. A correct answer alone is evidence, not mastery.</p><ul className="mt-3 space-y-2">{view.concepts.map((concept) => { const description = concepts.find((item) => item.id === concept.concept_id)?.description; return <li key={concept.concept_id} className="rounded-xl border border-line bg-surface p-4"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold text-ink">{concept.title}</span><span className="rounded-full bg-paper px-3 py-1 text-xs font-semibold text-navy">{concept.status === "mastered" ? "Mastered" : concept.status === "in_progress" ? "In progress" : "Not started"}</span></div>{description && <p className="mt-1 text-sm text-muted">{description}</p>}<p className="mt-2 text-xs text-muted">{concept.correct_count}/{concept.evidence_count} correct{concept.correct_percent === null ? "" : ` · ${concept.correct_percent}%`} · {concept.evidence_count}/{MASTERY_RULES.minimumEvidence} evidence items needed</p></li>; })}</ul></section>
          <section aria-labelledby="achievements-heading"><h3 id="achievements-heading" className="font-display text-xl font-medium text-ink">Achievements</h3><ul className="mt-3 space-y-2">{view.achievements.map((achievement) => <li key={achievement.id} className="rounded-xl border border-line bg-surface p-4"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold text-ink">{achievement.title}</span><span className="text-xs font-semibold text-sage">{achievement.unlocked ? "Earned" : "In progress"}</span></div><p className="mt-1 text-sm text-muted">{achievement.description}</p><p className="mt-2 text-xs text-muted">{achievement.progress}</p></li>)}</ul><p className="mt-4 text-xs leading-5 text-muted">Progress and rewards are stored only in this browser. They are not synced, account-backed, or tamper-proof.</p></section>
        </div>
        <button type="button" className="mt-6 rounded-sm border border-line px-4 py-2 text-sm font-semibold text-muted focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" onClick={() => { if (window.confirm("Clear this browser's saved learning progress?")) reset(); }}>Reset local progress</button>
        <p className="mt-3 text-xs text-muted">This sample tracks {concepts.length} reviewed concepts from lesson {lessonId}; mastery applies only to these concepts.</p>
      </>}
    </section>
  );
}

export function useLessonProgress() {
  const { recordPractice, recordAssessment } = useProgress();
  return { recordPractice, recordAssessment };
}
