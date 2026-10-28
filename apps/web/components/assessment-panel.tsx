"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  isAssessmentAttempt,
  isAssessmentResult,
  type AssessmentAnswerValue,
  type AssessmentAttempt,
  type AssessmentQuestion,
  type AssessmentResult,
  type MatchingAnswerPair,
} from "@/lib/api";

type SavedAssessment = { attempt: AssessmentAttempt; answers: Record<string, AssessmentAnswerValue>; result: AssessmentResult | null };

async function messageFrom(response: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "message" in body && typeof body.message === "string") return body.message;
  } catch { /* Keep the local safe fallback. */ }
  return fallback;
}

function isSavedAssessment(value: unknown, lessonId: string): value is SavedAssessment {
  if (typeof value !== "object" || value === null || !("attempt" in value) || !("answers" in value) || !("result" in value)) return false;
  const saved = value as { attempt: unknown; answers: unknown; result: unknown };
  return isAssessmentAttempt(saved.attempt) && saved.attempt.lesson_id === lessonId &&
    typeof saved.answers === "object" && saved.answers !== null &&
    (saved.result === null || (isAssessmentResult(saved.result) && saved.result.attempt_id === saved.attempt.attempt_id));
}

function isComplete(question: AssessmentQuestion, value: AssessmentAnswerValue | undefined): boolean {
  if (question.kind === "matching") return Array.isArray(value) && value.length === question.left_items.length && value.every((pair) => pair.left_id && pair.right_id);
  return typeof value === "string" && value.trim().length > 0;
}

function matchingValue(value: AssessmentAnswerValue | undefined): MatchingAnswerPair[] {
  return Array.isArray(value) ? value : [];
}

function answerLabel(question: AssessmentQuestion, answer: string | MatchingAnswerPair[]): string {
  if (typeof answer === "string") {
    if (question.kind === "multiple_choice") return question.options.find((option) => option.option_id === answer)?.label ?? answer;
    return answer;
  }
  if (question.kind !== "matching") return answer.map((pair) => `${pair.left_id} → ${pair.right_id}`).join(", ");
  return answer.map((pair) => {
    const left = question.left_items.find((item) => item.item_id === pair.left_id)?.label ?? pair.left_id;
    const right = question.right_items.find((item) => item.item_id === pair.right_id)?.label ?? pair.right_id;
    return `${left} → ${right}`;
  }).join("; ");
}

export function AssessmentPanel({ lessonId, onValidatedResult }: { lessonId: string; onValidatedResult?: (attempt: AssessmentAttempt, result: AssessmentResult) => void }) {
  const [saved, setSaved] = useState<SavedAssessment | null>(null);
  const [restored, setRestored] = useState(false);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [storageAvailable, setStorageAvailable] = useState(true);
  const busyRef = useRef(false);
  const storageKey = `know-it-all:assessment:${lessonId}:v1`;

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(storageKey);
      if (raw) {
        const parsed: unknown = JSON.parse(raw);
        if (isSavedAssessment(parsed, lessonId)) setSaved(parsed);
        else window.sessionStorage.removeItem(storageKey);
      }
    } catch {
      setStorageAvailable(false);
    } finally {
      setRestored(true);
    }
  }, [lessonId, storageKey]);

  useEffect(() => {
    if (!restored) return;
    try {
      if (saved) window.sessionStorage.setItem(storageKey, JSON.stringify(saved));
      else window.sessionStorage.removeItem(storageKey);
    } catch { setStorageAvailable(false); }
  }, [saved, restored, storageKey]);

  const attempt = saved?.attempt ?? null;
  const question = attempt?.questions[index];
  const answers = saved?.answers ?? {};
  const answeredCount = useMemo(() => attempt?.questions.filter((item) => isComplete(item, answers[item.question_id])).length ?? 0, [attempt, answers]);

  async function createAttempt() {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/lessons/${encodeURIComponent(lessonId)}/assessment-attempts`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error(await messageFrom(response, "The assessment could not be started."));
      const payload: unknown = await response.json();
      if (!isAssessmentAttempt(payload) || payload.lesson_id !== lessonId) throw new Error("The assessment response was not in the expected format.");
      setIndex(0);
      setSaved({ attempt: payload, answers: {}, result: null });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The assessment could not be started. Check that the learning service is running.");
    } finally { busyRef.current = false; setBusy(false); }
  }

  function saveAnswer(questionId: string, value: AssessmentAnswerValue) {
    setSaved((current) => current ? { ...current, answers: { ...current.answers, [questionId]: value } } : current);
  }

  async function submitAttempt() {
    if (!saved || answeredCount !== saved.attempt.questions.length || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/lessons/${encodeURIComponent(lessonId)}/assessment-attempts/${encodeURIComponent(saved.attempt.attempt_id)}/submit`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ answers: saved.attempt.questions.map((item) => ({ question_id: item.question_id, value: saved.answers[item.question_id] })) }),
      });
      if (!response.ok) throw new Error(await messageFrom(response, "Your assessment could not be submitted."));
      const payload: unknown = await response.json();
      if (!isAssessmentResult(payload) || payload.attempt_id !== saved.attempt.attempt_id) throw new Error("The assessment result was not in the expected format.");
      onValidatedResult?.(saved.attempt, payload);
      setSaved((current) => current ? { ...current, result: payload } : current);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Your assessment could not be submitted. Please try again.");
    } finally { busyRef.current = false; setBusy(false); }
  }

  function setPair(leftId: string, rightId: string) {
    if (!question || question.kind !== "matching") return;
    const pairs = matchingValue(answers[question.question_id]).filter((pair) => pair.left_id !== leftId);
    if (rightId) pairs.push({ left_id: leftId, right_id: rightId });
    saveAnswer(question.question_id, pairs);
  }

  return (
    <section id="assessment" aria-labelledby="assessment-heading" className="border-t border-line py-10 sm:py-12">
      <p className="eyebrow">Check your understanding</p>
      <h2 id="assessment-heading" className="mt-2 font-display text-3xl font-medium text-ink">Lesson assessment</h2>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">A fixed set of 15 reviewed questions checks the lesson concepts. Your answers are scored by the learning service after submission.</p>
      {!storageAvailable && <p className="mt-3 text-sm text-muted" role="status">Session storage is unavailable; this attempt will remain only in this page until you leave.</p>}
      {error && <p className="mt-4 rounded-xl border border-line bg-surface p-4 text-sm text-ink" role="alert">{error}</p>}
      {!restored && <p className="mt-5 text-sm text-muted" role="status">Restoring your assessment…</p>}
      {restored && !attempt && (
        <div className="mt-5 rounded-2xl border border-line bg-surface p-5 sm:p-7">
          <p className="text-sm leading-6 text-muted">The question bank currently supports one distinct attempt. Fresh retakes will become available when more reviewed questions are authored.</p>
          <button className="mt-5 rounded-sm bg-navy px-5 py-3 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-60" type="button" disabled={busy} onClick={createAttempt}>{busy ? "Starting…" : "Begin assessment"}</button>
        </div>
      )}
      {attempt && !saved?.result && question && (
        <div className="mt-5 rounded-2xl border border-line bg-surface p-5 sm:p-7">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
            <span>Question {index + 1} of {attempt.question_count}</span><span>{answeredCount} answered</span>
          </div>
          <form className="mt-5" onSubmit={(event) => { event.preventDefault(); if (index === attempt.questions.length - 1) void submitAttempt(); else setIndex((current) => Math.min(current + 1, attempt.questions.length - 1)); }}>
            <fieldset disabled={busy}>
              <legend className="font-display text-xl font-medium leading-7 text-ink">{question.prompt}</legend>
              {question.kind === "multiple_choice" && <div className="mt-4 space-y-2">{question.options.map((option) => <label key={option.option_id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 text-sm leading-6 text-ink hover:border-sage focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-sage"><input className="mt-1 accent-[#6F806F]" type="radio" name={question.question_id} value={option.option_id} checked={answers[question.question_id] === option.option_id} onChange={() => saveAnswer(question.question_id, option.option_id)} />{option.label}</label>)}</div>}
              {question.kind === "matching" && <div className="mt-4 space-y-3">{question.left_items.map((item) => { const value = matchingValue(answers[question.question_id]).find((pair) => pair.left_id === item.item_id)?.right_id ?? ""; return <label key={item.item_id} className="grid gap-2 text-sm font-medium text-ink sm:grid-cols-2 sm:items-center"><span>{item.label}</span><select aria-label={`Meaning for ${item.label}`} className="rounded-lg border border-line bg-paper px-3 py-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" value={value} onChange={(event) => setPair(item.item_id, event.target.value)}><option value="">Choose a meaning</option>{question.right_items.map((right) => <option key={right.item_id} value={right.item_id}>{right.label}</option>)}</select></label>; })}</div>}
              {question.kind === "fill_blank" && <div className="mt-4"><p className="font-medium text-navy">{question.sentence_template}</p><label className="mt-3 block text-sm font-medium text-ink" htmlFor={`answer-${question.question_id}`}>{question.blank_label}</label><input id={`answer-${question.question_id}`} className="mt-2 w-full max-w-md rounded-lg border border-line bg-paper px-3 py-3 text-base text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage" autoComplete="off" value={typeof answers[question.question_id] === "string" ? answers[question.question_id] as string : ""} onChange={(event) => saveAnswer(question.question_id, event.target.value)} /></div>}
            </fieldset>
            <div className="mt-6 flex flex-wrap justify-between gap-3">
              <button className="rounded-sm border border-line px-4 py-2 text-sm font-semibold text-navy focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50" type="button" disabled={index === 0 || busy} onClick={() => setIndex((current) => Math.max(current - 1, 0))}>Previous</button>
              {index < attempt.questions.length - 1 ? <button className="rounded-sm bg-navy px-4 py-2 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50" type="submit" disabled={busy}>Next question</button> : <button className="rounded-sm bg-navy px-4 py-2 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage disabled:opacity-50" type="submit" disabled={busy || answeredCount !== attempt.questions.length}>{busy ? "Scoring…" : "Submit assessment"}</button>}
            </div>
            {index === attempt.questions.length - 1 && answeredCount !== attempt.questions.length && <p className="mt-3 text-sm text-muted" role="status">Answer all 15 questions before submitting.</p>}
          </form>
        </div>
      )}
      {saved?.result && (
        <div className="mt-5 space-y-5">
          <section aria-labelledby="assessment-result-heading" className="rounded-2xl border border-line bg-surface p-5 sm:p-7">
            <p className="eyebrow">Assessment result</p>
            <h3 id="assessment-result-heading" className="mt-2 font-display text-2xl font-medium text-ink">{saved.result.mastery_achieved ? "Mastery achieved" : "Keep building your understanding"}</h3>
            <p className="mt-2 text-muted">{saved.result.correct_count} of {saved.result.total_questions} correct · {saved.result.score_percent}% · mastery threshold {saved.result.mastery_threshold_percent}%</p>
            <h4 className="mt-6 font-semibold text-ink">Concept feedback</h4>
            <ul className="mt-3 space-y-2">{saved.result.concept_results.map((concept) => <li key={concept.concept_id} className="flex flex-wrap justify-between gap-2 rounded-lg border border-line p-3 text-sm"><span className="font-medium text-ink">{concept.concept_id.replaceAll("-", " ")}{concept.weak ? " · needs review" : ""}</span><span className="text-muted">{concept.correct_count}/{concept.total_questions} · {concept.score_percent}%</span></li>)}</ul>
          </section>
          <section aria-labelledby="assessment-review-heading" className="rounded-2xl border border-line bg-surface p-5 sm:p-7">
            <h3 id="assessment-review-heading" className="font-display text-2xl font-medium text-ink">Answer review</h3>
            <ol className="mt-4 space-y-4">{saved.attempt.questions.map((item) => { const review = saved.result?.review.find((entry) => entry.question_id === item.question_id); if (!review) return null; return <li key={item.question_id} className="border-t border-line pt-4"><h4 className="font-semibold text-ink">{review.correct ? "Correct" : "Review"}: {item.prompt}</h4><p className="mt-2 text-sm text-muted">Your answer: {answerLabel(item, saved.answers[item.question_id] as string | MatchingAnswerPair[])}</p><p className="mt-1 text-sm text-navy">Answer: {answerLabel(item, review.correct_answer)}</p><p className="mt-2 text-sm leading-6 text-muted">{review.explanation}</p></li>; })}</ol>
          </section>
          <p className="text-sm text-muted">{storageAvailable ? "This result is saved for this browser session." : "Session storage is unavailable; this result will remain only in this page until you leave."} A fresh retake requires additional distinct reviewed questions.</p>
        </div>
      )}
    </section>
  );
}
