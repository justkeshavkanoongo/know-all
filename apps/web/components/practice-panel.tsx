"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  isPracticeCheckResult,
  isPracticeSet,
  type MatchingAnswerPair,
  type PracticeAnswer,
  type PracticeExercise,
  type PracticeSet,
} from "@/lib/api";

type PracticePanelProps = {
  lessonId: string;
  onValidatedOutcome?: (practice: PracticeSet, exercise: PracticeExercise, correct: boolean) => void;
};

async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const value: unknown = await response.json();
    if (typeof value === "object" && value !== null && "message" in value &&
        typeof value.message === "string") return value.message;
  } catch {
    // Use the safe local fallback for non-JSON proxy or network responses.
  }
  return fallback;
}

async function requestPracticeSet(lessonId: string) {
  const response = await fetch(`/api/lessons/${encodeURIComponent(lessonId)}/practice`, { cache: "no-store" });
  if (!response.ok) throw new Error(await errorMessage(response, "Practice could not be loaded."));
  const payload: unknown = await response.json();
  if (!isPracticeSet(payload) || payload.lesson_id !== lessonId) {
    throw new Error("The practice response was not in the expected format.");
  }
  return payload;
}

function isAnswerComplete(exercise: PracticeExercise, answer: PracticeAnswer | null): boolean {
  if (exercise.kind === "matching") {
    return Array.isArray(answer) && answer.length === exercise.left_items.length &&
      answer.every((pair) => Boolean(pair.left_id && pair.right_id));
  }
  return typeof answer === "string" && answer.trim().length > 0;
}

export function PracticePanel({ lessonId, onValidatedOutcome }: PracticePanelProps) {
  const [practice, setPractice] = useState<PracticeSet | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState<PracticeAnswer | null>(null);
  const [feedback, setFeedback] = useState<{ correct: boolean; message: string } | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    requestPracticeSet(lessonId)
      .then((payload) => { if (!cancelled) setPractice(payload); })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : "Practice could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [lessonId]);

  const exercises = practice?.exercises ?? [];
  const exercise = exercises[index];
  const complete = useMemo(
    () => exercise ? isAnswerComplete(exercise, answer) : false,
    [exercise, answer],
  );

  function resetCurrentExercise(nextIndex: number) {
    setIndex(nextIndex);
    setAnswer(null);
    setFeedback(null);
    setCheckError(null);
    submittingRef.current = false;
    setSubmitting(false);
  }

  function setMatchingAnswer(leftId: string, rightId: string) {
    const existing = Array.isArray(answer) ? answer : [];
    const next: MatchingAnswerPair[] = existing.filter((pair) => pair.left_id !== leftId);
    if (rightId) next.push({ left_id: leftId, right_id: rightId });
    setAnswer(next);
  }

  async function submitAnswer(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!exercise || !complete || feedback || submittingRef.current || answer === null) return;
    submittingRef.current = true;
    setSubmitting(true);
    setCheckError(null);
    try {
      const response = await fetch(`/api/lessons/${encodeURIComponent(lessonId)}/practice/check`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ exercise_id: exercise.exercise_id, answer }),
      });
      if (!response.ok) {
        setCheckError(await errorMessage(response, "Your answer could not be checked. Please try again."));
        return;
      }
      const payload: unknown = await response.json();
      if (!isPracticeCheckResult(payload) || payload.concept_id !== exercise.concept_id) {
        setCheckError("The answer check response was not in the expected format.");
        return;
      }
      if (practice) onValidatedOutcome?.(practice, exercise, payload.correct);
      setFeedback({ correct: payload.correct, message: payload.feedback });
    } catch {
      setCheckError("We couldn’t reach the practice service. Check your connection and try again.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  return (
    <section id="practice" aria-labelledby="practice-heading" className="border-t border-line py-10 sm:py-12">
      <p className="eyebrow">Try what you learned</p>
      <h2 id="practice-heading" className="mt-2 font-display text-3xl font-medium text-ink">Practice</h2>
      {loading && (
        <p className="mt-5 rounded-xl border border-line bg-surface p-5 text-sm text-muted" role="status" aria-live="polite">
          Loading reviewed exercises…
        </p>
      )}
      {!loading && loadError && (
        <div className="mt-5 rounded-xl border border-line bg-surface p-5" role="alert">
          <p className="text-sm leading-6 text-muted">{loadError}</p>
          <button className="mt-4 rounded-sm bg-navy px-4 py-2 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" onClick={() => {
            setLoading(true);
            setLoadError(null);
            requestPracticeSet(lessonId)
              .then((payload) => setPractice(payload))
              .catch((error: unknown) => setLoadError(error instanceof Error ? error.message : "Practice could not be loaded."))
              .finally(() => setLoading(false));
          }} type="button">Try loading again</button>
        </div>
      )}
      {!loading && !loadError && practice && practice.exercises.length === 0 && (
        <p className="mt-5 rounded-xl border border-line bg-surface p-5 text-sm text-muted" role="status">There are no reviewed exercises for this lesson yet.</p>
      )}
      {!loading && !loadError && exercise && (
        <div className="mt-5 rounded-2xl border border-line bg-surface p-5 sm:p-7">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
            Exercise {index + 1} of {exercises.length} · {exercise.difficulty}
          </p>
          <form className="mt-4" onSubmit={submitAnswer}>
            {exercise.kind === "multiple_choice" && (
              <fieldset disabled={Boolean(feedback) || submitting}>
                <legend className="font-display text-xl font-medium leading-7 text-ink">{exercise.prompt}</legend>
                <div className="mt-4 space-y-2">
                  {exercise.options.map((option) => (
                    <label key={option.option_id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 text-sm leading-6 text-ink hover:border-sage focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-sage">
                      <input className="mt-1 size-4 accent-sage" type="radio" name={exercise.exercise_id} value={option.option_id} checked={answer === option.option_id} onChange={() => setAnswer(option.option_id)} />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            {exercise.kind === "matching" && (
              <fieldset disabled={Boolean(feedback) || submitting}>
                <legend className="font-display text-xl font-medium leading-7 text-ink">{exercise.prompt}</legend>
                <div className="mt-4 space-y-3">
                  {exercise.left_items.map((left) => {
                    const selected = Array.isArray(answer) ? answer.find((pair) => pair.left_id === left.item_id)?.right_id ?? "" : "";
                    return (
                      <div key={left.item_id} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:items-center">
                        <label className="text-sm font-semibold text-ink" htmlFor={`${exercise.exercise_id}-${left.item_id}`}>{left.label}</label>
                        <select id={`${exercise.exercise_id}-${left.item_id}`} className="min-h-11 rounded-lg border border-line bg-white px-3 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" value={selected} onChange={(event) => setMatchingAnswer(left.item_id, event.target.value)}>
                          <option value="">Choose a meaning</option>
                          {exercise.right_items.map((right) => <option key={right.item_id} value={right.item_id}>{right.label}</option>)}
                        </select>
                      </div>
                    );
                  })}
                </div>
              </fieldset>
            )}
            {exercise.kind === "fill_blank" && (
              <div>
                <label className="block font-display text-xl font-medium leading-7 text-ink" htmlFor={`${exercise.exercise_id}-answer`}>{exercise.prompt}</label>
                <p className="mt-4 rounded-lg bg-paper px-4 py-3 font-display text-xl text-navy">{exercise.sentence_template}</p>
                <label className="mt-4 block text-sm font-semibold text-ink" htmlFor={`${exercise.exercise_id}-answer`}>{exercise.blank_label}</label>
                <input id={`${exercise.exercise_id}-answer`} autoComplete="off" className="mt-2 min-h-11 w-full rounded-lg border border-line bg-white px-3 text-base text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage sm:max-w-sm" disabled={Boolean(feedback) || submitting} value={typeof answer === "string" ? answer : ""} onChange={(event) => setAnswer(event.target.value)} />
              </div>
            )}
            {!feedback && (
              <button className="mt-5 rounded-sm bg-navy px-5 py-3 text-sm font-semibold text-white hover:bg-navy/90 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:cursor-not-allowed disabled:opacity-50" disabled={!complete || submitting} type="submit">
                {submitting ? "Checking…" : "Check answer"}
              </button>
            )}
          </form>
          {checkError && <p className="mt-4 text-sm leading-6 text-ink" role="alert">{checkError}</p>}
          {feedback && (
            <div className="mt-5 rounded-xl border border-line bg-paper p-4" role={feedback.correct ? "status" : "alert"} aria-live="polite">
              <p className="font-semibold text-ink">{feedback.correct ? "Correct" : "Not quite"}</p>
              <p className="mt-1 text-sm leading-6 text-muted">{feedback.message}</p>
              <button className="mt-4 rounded-sm bg-navy px-4 py-2.5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" onClick={() => resetCurrentExercise(index + 1)} type="button">
                {index + 1 === exercises.length ? "Finish practice" : "Next exercise"}
              </button>
            </div>
          )}
        </div>
      )}
      {!loading && !loadError && practice && index >= practice.exercises.length && practice.exercises.length > 0 && (
        <div className="mt-5 rounded-2xl border border-line bg-surface p-5 sm:p-7" role="status">
          <h3 className="font-display text-2xl font-medium text-ink">Practice complete</h3>
          <p className="mt-2 text-sm leading-6 text-muted">You’ve reached the end of this reviewed practice set.</p>
          <button className="mt-4 rounded-sm border border-line px-4 py-2.5 text-sm font-semibold text-navy hover:border-sage focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage" onClick={() => resetCurrentExercise(0)} type="button">Practice again</button>
        </div>
      )}
    </section>
  );
}
