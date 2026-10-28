import type { AssessmentAttempt, AssessmentResult, PracticeSet } from "@/lib/api";

export const PROGRESS_SCHEMA_VERSION = 2 as const;
export const PROGRESS_STORAGE_KEY = "know-it-all:progress:v2";
export const LEGACY_PROGRESS_STORAGE_KEY = "know-it-all:progress:v1";

export const MASTERY_RULES = {
  minimumEvidence: 5,
  minimumCorrectPercent: 80,
  assessmentThresholdPercent: 80,
} as const;

export const XP_RULES = {
  lessonCompleted: 10,
  practiceCompleted: 15,
  assessmentSubmitted: 20,
  assessmentMastery: 10,
  xpPerLevel: 50,
} as const;

export type PracticeOutcomeEvent = {
  type: "practice_outcome";
  id: string;
  lesson_id: string;
  exercise_set_id: string;
  exercise_id: string;
  concept_id: string;
  evidence_id: string;
  correct: boolean;
};

export type PracticeCompletedEvent = {
  type: "practice_completed";
  id: string;
  lesson_id: string;
  exercise_set_id: string;
  exercise_ids: string[];
};

export type AssessmentSubmittedEvent = {
  type: "assessment_submitted";
  id: string;
  attempt_id: string;
  lesson_id: string;
  correct_count: number;
  total_questions: number;
  score_percent: number;
  mastery_threshold_percent: number;
  mastery_achieved: boolean;
  question_evidence: { question_id: string; concept_id: string; evidence_id: string; correct: boolean }[];
};

export type LessonCompletedEvent = {
  type: "lesson_completed";
  id: string;
  lesson_id: string;
  source: "practice" | "assessment";
};

export type ProgressEvent =
  | PracticeOutcomeEvent
  | PracticeCompletedEvent
  | AssessmentSubmittedEvent
  | LessonCompletedEvent;

export type ProgressState = {
  schema_version: typeof PROGRESS_SCHEMA_VERSION;
  events: ProgressEvent[];
  reward_ledger: Record<string, number>;
};

export type ConceptDefinition = { id: string; title: string; description?: string };
export type ConceptProgress = {
  concept_id: string;
  title: string;
  evidence_count: number;
  correct_count: number;
  correct_percent: number | null;
  status: "not_started" | "in_progress" | "mastered";
};

export type Achievement = {
  id: string;
  title: string;
  description: string;
  unlocked: boolean;
  progress: string;
};

export type ProgressView = {
  lesson_completed: boolean;
  completed_practice_sets: number;
  practice_outcomes: number;
  assessment_history: { attempt_id: string; score_percent: number; correct_count: number; total_questions: number; mastery_achieved: boolean }[];
  concepts: ConceptProgress[];
  total_xp: number;
  level: number;
  xp_in_level: number;
  xp_to_next_level: number;
  achievements: Achievement[];
};

export type ProgressLoadStatus = "empty" | "ready" | "corrupt" | "outdated" | "unavailable";
export type ProgressLoadResult = { status: ProgressLoadStatus; state: ProgressState };

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export function emptyProgress(): ProgressState {
  return { schema_version: PROGRESS_SCHEMA_VERSION, events: [], reward_ledger: {} };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 200;
}

function roundPercent(correct: number, total: number): number {
  return total === 0 ? 0 : Number(((correct / total) * 100).toFixed(2));
}

function isProgressEvent(value: unknown): value is ProgressEvent {
  if (!isRecord(value) || !isText(value.id) || typeof value.type !== "string") return false;
  if (value.type === "practice_outcome") {
    return value.id === `practice-outcome:${String(value.exercise_set_id)}:${String(value.exercise_id)}` &&
      isText(value.lesson_id) && isText(value.exercise_set_id) && isText(value.exercise_id) &&
      isText(value.concept_id) && isText(value.evidence_id) && typeof value.correct === "boolean";
  }
  if (value.type === "practice_completed") {
    return value.id === `practice-completed:${String(value.exercise_set_id)}` && isText(value.lesson_id) &&
      isText(value.exercise_set_id) && Array.isArray(value.exercise_ids) && value.exercise_ids.length > 0 &&
      value.exercise_ids.every(isText) && new Set(value.exercise_ids).size === value.exercise_ids.length;
  }
  if (value.type === "assessment_submitted") {
    return value.id === `assessment:${String(value.attempt_id)}` && isText(value.attempt_id) && isText(value.lesson_id) &&
      Number.isInteger(value.correct_count) && Number(value.correct_count) >= 0 &&
      Number.isInteger(value.total_questions) && Number(value.total_questions) > 0 &&
      Number(value.correct_count) <= Number(value.total_questions) &&
      typeof value.score_percent === "number" && value.score_percent === roundPercent(Number(value.correct_count), Number(value.total_questions)) &&
      value.mastery_threshold_percent === MASTERY_RULES.assessmentThresholdPercent &&
      typeof value.mastery_achieved === "boolean" && Array.isArray(value.question_evidence) &&
      value.question_evidence.length === value.total_questions && value.question_evidence.every((item) =>
        isRecord(item) && isText(item.question_id) && isText(item.concept_id) && isText(item.evidence_id) && typeof item.correct === "boolean") &&
      new Set(value.question_evidence.map((item) => (item as Record<string, unknown>).question_id)).size === value.question_evidence.length &&
      value.question_evidence.filter((item) => (item as Record<string, unknown>).correct === true).length === value.correct_count &&
      value.mastery_achieved === (Number(value.score_percent) >= value.mastery_threshold_percent);
  }
  if (value.type === "lesson_completed") {
    return value.id === `lesson-completed:${String(value.lesson_id)}` && isText(value.lesson_id) &&
      (value.source === "practice" || value.source === "assessment");
  }
  return false;
}

function rewardsForEvents(events: ProgressEvent[]): Record<string, number> {
  const rewards: Record<string, number> = {};
  const lessons = new Set<string>();
  const assessed = new Set<string>();
  const mastered = new Set<string>();
  for (const event of events) {
    if (event.type === "practice_completed") {
      rewards[`practice-completed:${event.exercise_set_id}`] = XP_RULES.practiceCompleted;
    } else if (event.type === "assessment_submitted") {
      assessed.add(event.lesson_id);
      if (event.mastery_achieved) mastered.add(event.lesson_id);
    } else if (event.type === "lesson_completed") {
      lessons.add(event.lesson_id);
    }
  }
  for (const lessonId of lessons) rewards[`lesson-completed:${lessonId}`] = XP_RULES.lessonCompleted;
  for (const lessonId of assessed) rewards[`assessment-first-submission:${lessonId}`] = XP_RULES.assessmentSubmitted;
  for (const lessonId of mastered) rewards[`mastery-achieved:${lessonId}`] = XP_RULES.assessmentMastery;
  return rewards;
}

function sameLedger(left: Record<string, number>, right: Record<string, number>): boolean {
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every((key) => left[key] === right[key]);
}

export function decodeProgress(raw: string | null): ProgressLoadResult {
  if (raw === null) return { status: "empty", state: emptyProgress() };
  let value: unknown;
  try { value = JSON.parse(raw); } catch { return { status: "corrupt", state: emptyProgress() }; }
  if (!isRecord(value) || !Number.isInteger(value.schema_version)) return { status: "corrupt", state: emptyProgress() };
  if (value.schema_version !== PROGRESS_SCHEMA_VERSION) return { status: "outdated", state: emptyProgress() };
  if (!Array.isArray(value.events) || !value.events.every(isProgressEvent) || !isRecord(value.reward_ledger)) {
    return { status: "corrupt", state: emptyProgress() };
  }
  const events = value.events as ProgressEvent[];
  if (new Set(events.map((event) => event.id)).size !== events.length) return { status: "corrupt", state: emptyProgress() };
  for (const event of events) {
    if (event.type === "practice_completed") {
      const outcomes = new Set(events.filter((candidate): candidate is PracticeOutcomeEvent => candidate.type === "practice_outcome" && candidate.exercise_set_id === event.exercise_set_id && candidate.lesson_id === event.lesson_id).map((candidate) => candidate.exercise_id));
      if (!event.exercise_ids.every((id) => outcomes.has(id))) return { status: "corrupt", state: emptyProgress() };
      if (!events.some((candidate) => candidate.type === "lesson_completed" && candidate.lesson_id === event.lesson_id)) return { status: "corrupt", state: emptyProgress() };
    } else if (event.type === "assessment_submitted") {
      if (!events.some((candidate) => candidate.type === "lesson_completed" && candidate.lesson_id === event.lesson_id)) return { status: "corrupt", state: emptyProgress() };
    } else if (event.type === "lesson_completed") {
      const hasEvidence = events.some((candidate) => candidate.type === "practice_completed" && candidate.lesson_id === event.lesson_id) || events.some((candidate) => candidate.type === "assessment_submitted" && candidate.lesson_id === event.lesson_id);
      if (!hasEvidence) return { status: "corrupt", state: emptyProgress() };
    }
  }
  const ledger = value.reward_ledger;
  if (Object.entries(ledger).some(([key, amount]) => !isText(key) || typeof amount !== "number" || amount < 0) || !sameLedger(ledger as Record<string, number>, rewardsForEvents(events))) {
    return { status: "corrupt", state: emptyProgress() };
  }
  return { status: "ready", state: { schema_version: PROGRESS_SCHEMA_VERSION, events, reward_ledger: ledger as Record<string, number> } };
}

export function loadProgress(storage: StorageLike, key = PROGRESS_STORAGE_KEY): ProgressLoadResult {
  try { return decodeProgress(storage.getItem(key)); }
  catch { return { status: "unavailable", state: emptyProgress() }; }
}

export function saveProgress(storage: StorageLike, state: ProgressState, key = PROGRESS_STORAGE_KEY): boolean {
  try {
    storage.setItem(key, JSON.stringify(state));
    return true;
  } catch { return false; }
}

export function resetProgress(storage: StorageLike, key = PROGRESS_STORAGE_KEY): boolean {
  try { storage.removeItem(key); return true; }
  catch { return false; }
}

function upsertEvent(state: ProgressState, event: ProgressEvent): ProgressState {
  const events = [...state.events.filter((current) => current.id !== event.id), event];
  return { schema_version: PROGRESS_SCHEMA_VERSION, events, reward_ledger: rewardsForEvents(events) };
}

function ensureLessonCompletion(state: ProgressState, lessonId: string, source: "practice" | "assessment"): ProgressState {
  if (state.events.some((event) => event.type === "lesson_completed" && event.lesson_id === lessonId)) return state;
  return upsertEvent(state, { type: "lesson_completed", id: `lesson-completed:${lessonId}`, lesson_id: lessonId, source });
}

export function recordPracticeOutcome(
  state: ProgressState,
  args: { lesson_id: string; practice: PracticeSet; exercise_id: string; concept_id: string; correct: boolean },
): ProgressState {
  const exerciseIds = args.practice.exercises.map((exercise) => exercise.exercise_id);
  if (typeof args.correct !== "boolean" || new Set(exerciseIds).size !== exerciseIds.length ||
      args.practice.lesson_id !== args.lesson_id || !exerciseIds.includes(args.exercise_id) ||
      !args.practice.exercises.some((exercise) => exercise.exercise_id === args.exercise_id && exercise.concept_id === args.concept_id && isText(exercise.evidence_id))) return state;
  const selectedExercise = args.practice.exercises.find((exercise) => exercise.exercise_id === args.exercise_id)!;
  const outcome: PracticeOutcomeEvent = {
    type: "practice_outcome", id: `practice-outcome:${args.practice.exercise_set_id}:${args.exercise_id}`,
    lesson_id: args.lesson_id, exercise_set_id: args.practice.exercise_set_id, exercise_id: args.exercise_id,
    concept_id: args.concept_id, evidence_id: selectedExercise.evidence_id, correct: args.correct,
  };
  let next = upsertEvent(state, outcome);
  const completed = exerciseIds.every((id) => next.events.some((event) => event.type === "practice_outcome" && event.lesson_id === args.lesson_id && event.exercise_set_id === args.practice.exercise_set_id && event.exercise_id === id));
  if (!completed) return next;
  next = upsertEvent(next, { type: "practice_completed", id: `practice-completed:${args.practice.exercise_set_id}`, lesson_id: args.lesson_id, exercise_set_id: args.practice.exercise_set_id, exercise_ids: exerciseIds });
  return ensureLessonCompletion(next, args.lesson_id, "practice");
}

function validAssessmentReceipt(attempt: AssessmentAttempt, result: AssessmentResult): boolean {
  if (attempt.lesson_id !== result.lesson_id || attempt.attempt_id !== result.attempt_id || attempt.questions.length !== 15 || result.total_questions !== 15 || result.review.length !== 15) return false;
  const questionIds = attempt.questions.map((question) => question.question_id);
  if (new Set(questionIds).size !== questionIds.length || new Set(result.review.map((review) => review.question_id)).size !== 15 || !questionIds.every((id) => result.review.some((review) => review.question_id === id)) || attempt.questions.some((question) => !isText(question.concept_id) || !isText(question.evidence_id))) return false;
  const correct = result.review.filter((review) => review.correct).length;
  const score = roundPercent(correct, 15);
  if (result.mastery_threshold_percent !== MASTERY_RULES.assessmentThresholdPercent || correct !== result.correct_count || score !== result.score_percent || result.mastery_achieved !== (score >= result.mastery_threshold_percent)) return false;
  const conceptTotals = new Map<string, { correct: number; total: number }>();
  for (const question of attempt.questions) {
    const review = result.review.find((item) => item.question_id === question.question_id);
    if (!review) return false;
    const count = conceptTotals.get(question.concept_id) ?? { correct: 0, total: 0 };
    count.total += 1;
    count.correct += Number(review.correct);
    conceptTotals.set(question.concept_id, count);
  }
  if (conceptTotals.size !== result.concept_results.length) return false;
  const expectedWeak = [...conceptTotals].filter(([, count]) => roundPercent(count.correct, count.total) < MASTERY_RULES.minimumCorrectPercent).map(([id]) => id).sort();
  if ([...result.weak_concepts].sort().join("|") !== expectedWeak.join("|")) return false;
  for (const question of attempt.questions) {
    const review = result.review.find((item) => item.question_id === question.question_id)!;
    if (question.kind === "multiple_choice" && (typeof review.correct_answer !== "string" || !question.options.some((option) => option.label === review.correct_answer))) return false;
    if (question.kind === "fill_blank" && typeof review.correct_answer !== "string") return false;
    if (question.kind === "matching") {
      if (!Array.isArray(review.correct_answer) || review.correct_answer.length !== question.left_items.length) return false;
      const pairs = review.correct_answer as { left_id: string; right_id: string }[];
      if (new Set(pairs.map((pair) => pair.left_id)).size !== pairs.length || new Set(pairs.map((pair) => pair.right_id)).size !== pairs.length ||
          !question.left_items.every((item) => pairs.some((pair) => pair.left_id === item.item_id)) ||
          pairs.some((pair) => !question.right_items.some((item) => item.item_id === pair.right_id))) return false;
    }
  }
  for (const [conceptId, count] of conceptTotals) {
    const returned = result.concept_results.find((item) => item.concept_id === conceptId);
    const percent = roundPercent(count.correct, count.total);
    if (!returned || returned.correct_count !== count.correct || returned.total_questions !== count.total || returned.score_percent !== percent || returned.weak !== (percent < MASTERY_RULES.minimumCorrectPercent)) return false;
  }
  return true;
}

export function recordAssessmentResult(state: ProgressState, attempt: AssessmentAttempt, result: AssessmentResult): ProgressState {
  if (!validAssessmentReceipt(attempt, result) || state.events.some((event) => event.type === "assessment_submitted" && event.attempt_id === attempt.attempt_id)) return state;
  const question_evidence = attempt.questions.map((question) => ({
    question_id: question.question_id,
    concept_id: question.concept_id,
    evidence_id: question.evidence_id,
    correct: result.review.find((review) => review.question_id === question.question_id)?.correct ?? false,
  }));
  const event: AssessmentSubmittedEvent = {
    type: "assessment_submitted", id: `assessment:${attempt.attempt_id}`, attempt_id: attempt.attempt_id,
    lesson_id: attempt.lesson_id, correct_count: result.correct_count, total_questions: result.total_questions,
    score_percent: result.score_percent, mastery_threshold_percent: result.mastery_threshold_percent,
    mastery_achieved: result.mastery_achieved, question_evidence,
  };
  return ensureLessonCompletion(upsertEvent(state, event), attempt.lesson_id, "assessment");
}

export function conceptProgress(state: ProgressState, concepts: ConceptDefinition[]): ConceptProgress[] {
  const evidenceById = new Map<string, { concept_id: string; correct: boolean }>();
  for (const event of state.events) {
    if (event.type === "practice_outcome") evidenceById.set(event.evidence_id, event);
    if (event.type === "assessment_submitted") {
      for (const item of event.question_evidence) evidenceById.set(item.evidence_id, item);
    }
  }
  return concepts.map((concept) => {
    const evidence = [...evidenceById.values()].filter((item) => item.concept_id === concept.id).map((item) => item.correct);
    const evidence_count = evidence.length;
    const correct_count = evidence.filter(Boolean).length;
    const correct_percent = evidence_count ? roundPercent(correct_count, evidence_count) : null;
    const mastered = evidence_count >= MASTERY_RULES.minimumEvidence && correct_percent !== null && correct_percent >= MASTERY_RULES.minimumCorrectPercent;
    return { concept_id: concept.id, title: concept.title, evidence_count, correct_count, correct_percent, status: mastered ? "mastered" : evidence_count ? "in_progress" : "not_started" };
  });
}

export function progressView(state: ProgressState, concepts: ConceptDefinition[], lessonId: string): ProgressView {
  const total_xp = Object.values(state.reward_ledger).reduce((sum, amount) => sum + amount, 0);
  const level = Math.floor(total_xp / XP_RULES.xpPerLevel) + 1;
  const xp_in_level = total_xp % XP_RULES.xpPerLevel;
  const masteredConcepts = conceptProgress(state, concepts).filter((concept) => concept.status === "mastered").length;
  const totalConcepts = concepts.length;
  const lessons = state.events.filter((event) => event.type === "lesson_completed");
  const practices = state.events.filter((event) => event.type === "practice_completed");
  const assessments = state.events.filter((event): event is AssessmentSubmittedEvent => event.type === "assessment_submitted");
  const achievements: Achievement[] = [
    { id: "first-lesson", title: "A thoughtful beginning", description: "Complete a lesson activity.", unlocked: lessons.length > 0, progress: lessons.length ? "1 of 1 lessons" : "0 of 1 lessons" },
    { id: "practice-finisher", title: "Practice, thoughtfully", description: "Complete a reviewed practice set.", unlocked: practices.length > 0, progress: `${Math.min(practices.length, 1)} of 1 practice sets` },
    { id: "assessment-mastery", title: "Concepts in focus", description: "Reach the assessment mastery threshold.", unlocked: assessments.some((event) => event.mastery_achieved), progress: assessments.some((event) => event.mastery_achieved) ? "Mastery demonstrated" : "Awaiting a mastered assessment" },
    { id: "concept-scholar", title: "A wider understanding", description: "Demonstrate mastery across every concept in this lesson.", unlocked: totalConcepts > 0 && masteredConcepts === totalConcepts, progress: `${masteredConcepts} of ${totalConcepts} concepts mastered` },
  ];
  return {
    lesson_completed: lessons.some((event) => event.lesson_id === lessonId),
    completed_practice_sets: practices.filter((event) => event.lesson_id === lessonId).length,
    practice_outcomes: new Set(state.events.filter((event): event is PracticeOutcomeEvent => event.type === "practice_outcome" && event.lesson_id === lessonId).map((event) => event.exercise_id)).size,
    assessment_history: assessments.filter((event) => event.lesson_id === lessonId).map((event) => ({ attempt_id: event.attempt_id, score_percent: event.score_percent, correct_count: event.correct_count, total_questions: event.total_questions, mastery_achieved: event.mastery_achieved })),
    concepts: conceptProgress(state, concepts), total_xp, level, xp_in_level,
    xp_to_next_level: XP_RULES.xpPerLevel - xp_in_level, achievements,
  };
}

export class BrowserProgressStorage {
  private readonly storage: StorageLike;
  private readonly key: string;

  constructor(storage: StorageLike, key = PROGRESS_STORAGE_KEY) {
    this.storage = storage;
    this.key = key;
  }
  load(): ProgressLoadResult {
    try {
      const current = this.storage.getItem(this.key);
      if (current !== null) return decodeProgress(current);
      if (this.key === PROGRESS_STORAGE_KEY) {
        const legacy = this.storage.getItem(LEGACY_PROGRESS_STORAGE_KEY);
        if (legacy !== null) return { status: "outdated", state: emptyProgress() };
      }
      return { status: "empty", state: emptyProgress() };
    } catch { return { status: "unavailable", state: emptyProgress() }; }
  }
  save(state: ProgressState): boolean { return saveProgress(this.storage, state, this.key); }
  reset(): boolean {
    try {
      this.storage.removeItem(this.key);
      if (this.key === PROGRESS_STORAGE_KEY) this.storage.removeItem(LEGACY_PROGRESS_STORAGE_KEY);
      return true;
    } catch { return false; }
  }
}

export function browserProgressStorage(): BrowserProgressStorage {
  return new BrowserProgressStorage(window.localStorage);
}
