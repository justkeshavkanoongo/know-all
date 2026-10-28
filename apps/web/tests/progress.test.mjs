import test from "node:test";
import assert from "node:assert/strict";
import {
  BrowserProgressStorage,
  decodeProgress,
  PROGRESS_SCHEMA_VERSION,
  PROGRESS_STORAGE_KEY,
  LEGACY_PROGRESS_STORAGE_KEY,
  emptyProgress,
  progressView,
  recordAssessmentResult,
  recordPracticeOutcome,
  XP_RULES,
} from "../lib/progress.ts";

const lessonId = "german-a1-greetings";
const concepts = [
  { id: "german-greetings", title: "Greetings" },
  { id: "german-self-introduction", title: "Introductions" },
  { id: "german-formal-address", title: "Formality" },
  { id: "german-wie-gehts", title: "Wellbeing" },
];

class MemoryStorage {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, value); }
  removeItem(key) { this.values.delete(key); }
}

function practiceSet(count = 5) {
  return {
    lesson_id: lessonId,
    exercise_set_id: "german-a1-greetings-practice",
    version: "1.0.0",
    exercises: Array.from({ length: count }, (_, index) => ({
      exercise_id: `exercise-${index + 1}`,
      concept_id: "german-greetings",
      evidence_id: `evidence-${index + 1}`,
    })),
  };
}

function assessmentReceipt({ attemptId = "attempt-1", correctQuestionIds } = {}) {
  const conceptByIndex = [
    ...Array(7).fill("german-greetings"),
    ...Array(3).fill("german-self-introduction"),
    ...Array(2).fill("german-formal-address"),
    ...Array(3).fill("german-wie-gehts"),
  ];
  const questions = conceptByIndex.map((concept_id, index) => {
    const question_id = `q-${index + 1}`;
    if (index === 5) return { question_id, concept_id, evidence_id: `assessment-evidence-${index + 1}`, kind: "matching", left_items: [{ item_id: "left-1" }, { item_id: "left-2" }], right_items: [{ item_id: "right-1" }, { item_id: "right-2" }] };
    if (index === 7 || index === 14) return { question_id, concept_id, evidence_id: `assessment-evidence-${index + 1}`, kind: "fill_blank" };
    return { question_id, concept_id, evidence_id: `assessment-evidence-${index + 1}`, kind: "multiple_choice", options: [{ option_id: "a", label: "answer" }, { option_id: "b", label: "other" }] };
  });
  const correctIds = correctQuestionIds ?? new Set(questions.map((question) => question.question_id));
  const review = questions.map((question) => ({
    question_id: question.question_id,
    correct: correctIds.has(question.question_id),
    correct_answer: questions.find((item) => item.question_id === question.question_id)?.kind === "matching" ? [{ left_id: "left-1", right_id: "right-1" }, { left_id: "left-2", right_id: "right-2" }] : "answer",
    explanation: "Reviewed reason.",
  }));
  const concept_results = concepts.map((concept) => {
    const items = questions.filter((question) => question.concept_id === concept.id);
    const correct_count = items.filter((question) => correctIds.has(question.question_id)).length;
    const score_percent = Number(((correct_count / items.length) * 100).toFixed(2));
    return { concept_id: concept.id, correct_count, total_questions: items.length, score_percent, weak: score_percent < 80 };
  });
  const correct_count = review.filter((item) => item.correct).length;
  const score_percent = Number(((correct_count / 15) * 100).toFixed(2));
  return {
    attempt: { attempt_id: attemptId, lesson_id: lessonId, bank_version: "1.0.0", question_count: 15, questions },
    result: {
      attempt_id: attemptId,
      lesson_id: lessonId,
      correct_count,
      total_questions: 15,
      score_percent,
      mastery_threshold_percent: 80,
      mastery_achieved: score_percent >= 80,
      concept_results,
      weak_concepts: concept_results.filter((item) => item.weak).map((item) => item.concept_id),
      review,
    },
  };
}

test("empty, corrupt, and outdated progress versions load safely", () => {
  assert.equal(decodeProgress(null).status, "empty");
  assert.equal(decodeProgress("not-json").status, "corrupt");
  assert.equal(decodeProgress(JSON.stringify({ schema_version: 0, events: [], reward_ledger: {} })).status, "outdated");
  assert.equal(decodeProgress(JSON.stringify({ schema_version: 3, events: [], reward_ledger: {} })).status, "outdated");
});

test("schema validation rejects malformed events and inflated reward ledgers", () => {
  assert.equal(decodeProgress(JSON.stringify({ schema_version: PROGRESS_SCHEMA_VERSION, events: [{ type: "lesson_completed" }], reward_ledger: {} })).status, "corrupt");
  assert.equal(decodeProgress(JSON.stringify({ schema_version: PROGRESS_SCHEMA_VERSION, events: [], reward_ledger: { "lesson-completed:made-up": 999 } })).status, "corrupt");
});

test("storage round trips across repository instances and reset is explicit", () => {
  const rawStorage = new MemoryStorage();
  const first = new BrowserProgressStorage(rawStorage);
  const assessment = assessmentReceipt();
  const next = recordAssessmentResult(emptyProgress(), assessment.attempt, assessment.result);
  assert.equal(first.save(next), true);
  const second = new BrowserProgressStorage(rawStorage);
  assert.equal(second.load().status, "ready");
  assert.equal(second.load().state.events.length, 2);
  assert.equal(second.reset(), true);
  assert.equal(first.load().status, "empty");
});

test("unavailable storage degrades to a safe empty in-memory state", async () => {
  const { loadProgress } = await import("../lib/progress.ts");
  const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } };
  assert.equal(loadProgress(broken).status, "unavailable");
});

test("unsupported stored data is reported without overwriting the original", () => {
  const rawStorage = new MemoryStorage();
  rawStorage.setItem(PROGRESS_STORAGE_KEY, JSON.stringify({ schema_version: 0, events: [], reward_ledger: {} }));
  const repository = new BrowserProgressStorage(rawStorage);
  assert.equal(repository.load().status, "outdated");
  assert.equal(JSON.parse(rawStorage.getItem(PROGRESS_STORAGE_KEY)).schema_version, 0);
  const future = JSON.stringify({ schema_version: 3, events: [], reward_ledger: {} });
  rawStorage.setItem(PROGRESS_STORAGE_KEY, future);
  assert.equal(repository.load().status, "outdated");
  assert.equal(rawStorage.getItem(PROGRESS_STORAGE_KEY), future);
});

test("concept mastery requires five distinct checked evidence items and 80 percent", () => {
  const set = practiceSet();
  let state = emptyProgress();
  state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: set, exercise_id: "exercise-1", concept_id: "german-greetings", correct: true });
  assert.equal(progressView(state, concepts, lessonId).concepts[0].status, "in_progress");
  for (const exercise of set.exercises.slice(1)) {
    state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: set, exercise_id: exercise.exercise_id, concept_id: exercise.concept_id, correct: exercise.exercise_id !== "exercise-5" });
  }
  const view = progressView(state, concepts, lessonId);
  assert.equal(view.concepts[0].evidence_count, 5);
  assert.equal(view.concepts[0].correct_percent, 80);
  assert.equal(view.concepts[0].status, "mastered");
  const reusedStableExercise = { ...set, exercise_set_id: "practice-v2", exercises: [set.exercises[0]] };
  state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: reusedStableExercise, exercise_id: "exercise-1", concept_id: "german-greetings", correct: true });
  assert.equal(progressView(state, concepts, lessonId).concepts[0].evidence_count, 5);
  const sixthEvidence = { ...set, exercises: [{ exercise_id: "exercise-6", concept_id: "german-greetings", evidence_id: "evidence-6" }] };
  state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: sixthEvidence, exercise_id: "exercise-6", concept_id: "german-greetings", correct: false });
  assert.equal(progressView(state, concepts, lessonId).concepts[0].evidence_count, 6);
  assert.equal(progressView(state, concepts, lessonId).concepts[0].status, "in_progress");
});

test("practice completion rewards are idempotent while later checked outcomes can improve evidence", () => {
  const set = practiceSet();
  let state = emptyProgress();
  for (const exercise of set.exercises) {
    state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: set, exercise_id: exercise.exercise_id, concept_id: exercise.concept_id, correct: true });
  }
  const complete = progressView(state, concepts, lessonId);
  assert.equal(complete.lesson_completed, true);
  assert.equal(complete.completed_practice_sets, 1);
  assert.equal(complete.total_xp, XP_RULES.lessonCompleted + XP_RULES.practiceCompleted);
  const once = JSON.stringify(state);
  state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: set, exercise_id: "exercise-1", concept_id: "german-greetings", correct: true });
  assert.equal(progressView(state, concepts, lessonId).total_xp, complete.total_xp);
  assert.equal(state.events.filter((event) => event.type === "practice_outcome").length, 5);
  assert.equal(once.includes("practice-completed:german-a1-greetings-practice"), true);
});

test("assessment score data is derived and verified, attempts deduplicate, and mastery unlocks", () => {
  const assessment = assessmentReceipt();
  let state = recordAssessmentResult(emptyProgress(), assessment.attempt, assessment.result);
  state = recordAssessmentResult(state, assessment.attempt, assessment.result);
  assert.equal(progressView(state, concepts, lessonId).achievements.find((item) => item.id === "concept-scholar").unlocked, false);
  const supplementary = {
    lesson_id: lessonId,
    exercise_set_id: "supplementary-reviewed-practice",
    version: "1.0.0",
    exercises: [
      { exercise_id: "intro-4", concept_id: "german-self-introduction", evidence_id: "intro-4" },
      { exercise_id: "intro-5", concept_id: "german-self-introduction", evidence_id: "intro-5" },
      { exercise_id: "formal-3", concept_id: "german-formal-address", evidence_id: "formal-3" },
      { exercise_id: "formal-4", concept_id: "german-formal-address", evidence_id: "formal-4" },
      { exercise_id: "formal-5", concept_id: "german-formal-address", evidence_id: "formal-5" },
      { exercise_id: "wellbeing-4", concept_id: "german-wie-gehts", evidence_id: "wellbeing-4" },
      { exercise_id: "wellbeing-5", concept_id: "german-wie-gehts", evidence_id: "wellbeing-5" },
    ],
  };
  for (const exercise of supplementary.exercises) state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: supplementary, exercise_id: exercise.exercise_id, concept_id: exercise.concept_id, correct: true });
  const view = progressView(state, concepts, lessonId);
  assert.equal(view.assessment_history.length, 1);
  assert.equal(view.assessment_history[0].score_percent, 100);
  assert.equal(view.achievements.find((item) => item.id === "assessment-mastery").unlocked, true);
  assert.equal(view.achievements.find((item) => item.id === "concept-scholar").unlocked, true);
  assert.equal(view.total_xp, XP_RULES.lessonCompleted + XP_RULES.assessmentSubmitted + XP_RULES.assessmentMastery + XP_RULES.practiceCompleted);

  const forged = { ...assessment.result, score_percent: 0, correct_count: 0, mastery_achieved: false };
  const rejected = recordAssessmentResult(emptyProgress(), assessment.attempt, forged);
  assert.equal(rejected.events.length, 0);
  assert.equal(progressView(rejected, concepts, lessonId).total_xp, 0);
  const forgedWeakSummary = { ...assessment.result, weak_concepts: ["german-greetings"] };
  assert.equal(recordAssessmentResult(emptyProgress(), assessment.attempt, forgedWeakSummary).events.length, 0);
});

test("XP level thresholds and achievements reflect actual learning events", () => {
  const xpState = (xp) => ({ ...emptyProgress(), reward_ledger: { threshold: xp } });
  assert.equal(progressView(xpState(0), concepts, lessonId).level, 1);
  assert.equal(progressView(xpState(49), concepts, lessonId).level, 1);
  assert.equal(progressView(xpState(50), concepts, lessonId).level, 2);
  assert.equal(progressView(xpState(100), concepts, lessonId).level, 3);
  const assessment = assessmentReceipt();
  let state = recordAssessmentResult(emptyProgress(), assessment.attempt, assessment.result);
  const set = practiceSet();
  for (const exercise of set.exercises) state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: set, exercise_id: exercise.exercise_id, concept_id: exercise.concept_id, correct: true });
  const view = progressView(state, concepts, lessonId);
  assert.equal(view.total_xp, 55);
  assert.equal(view.level, 2);
  assert.equal(view.xp_in_level, 5);
  assert.equal(view.xp_to_next_level, 45);
  assert.equal(view.achievements.find((item) => item.id === "first-lesson").unlocked, true);
  assert.equal(view.achievements.find((item) => item.id === "practice-finisher").unlocked, true);
});


test("same reviewed evidence across practice and assessment counts once", () => {
  const assessment = assessmentReceipt();
  const sharedSet = { ...practiceSet(), exercises: practiceSet().exercises.map((exercise, index) => ({ ...exercise, evidence_id: assessment.attempt.questions[index].evidence_id })) };
  let state = recordAssessmentResult(emptyProgress(), assessment.attempt, assessment.result);
  for (const exercise of sharedSet.exercises) {
    state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: sharedSet, exercise_id: exercise.exercise_id, concept_id: exercise.concept_id, correct: true });
  }
  const greeting = progressView(state, concepts, lessonId).concepts[0];
  assert.equal(greeting.evidence_count, 7);
  assert.equal(greeting.status, "mastered");
});

test("a failed persistence write leaves only an explicitly in-memory update", () => {
  const storage = new BrowserProgressStorage({ getItem() { return null; }, setItem() { throw new Error("quota"); }, removeItem() {} });
  const receipt = assessmentReceipt();
  const inMemory = recordAssessmentResult(emptyProgress(), receipt.attempt, receipt.result);
  assert.equal(storage.save(inMemory), false);
  assert.equal(progressView(inMemory, concepts, lessonId).total_xp, 40);
  assert.equal(storage.load().status, "empty");
});

test("level calculation changes exactly at each 50 XP boundary", () => {
  const receipt = assessmentReceipt();
  const state = recordAssessmentResult(emptyProgress(), receipt.attempt, receipt.result);
  const atForty = state.reward_ledger;
  assert.equal(progressView({ ...state, reward_ledger: { ...atForty, extra: 10 } }, concepts, lessonId).level, 2);
  assert.equal(progressView({ ...state, reward_ledger: { ...atForty, extra: 60 } }, concepts, lessonId).level, 3);
});


test("existing version-one storage is preserved and exposed as unsupported until explicit reset", () => {
  const rawStorage = new MemoryStorage();
  const original = JSON.stringify({ schema_version: 1, events: [], reward_ledger: {} });
  rawStorage.setItem(LEGACY_PROGRESS_STORAGE_KEY, original);
  const repository = new BrowserProgressStorage(rawStorage);
  assert.equal(repository.load().status, "outdated");
  assert.equal(rawStorage.getItem(LEGACY_PROGRESS_STORAGE_KEY), original);
  assert.equal(repository.reset(), true);
  assert.equal(rawStorage.getItem(LEGACY_PROGRESS_STORAGE_KEY), null);
});

test("failed storage reset reports failure and retains the stored record", () => {
  const original = JSON.stringify({ schema_version: 3, events: [], reward_ledger: {} });
  const repository = new BrowserProgressStorage({ getItem() { return original; }, setItem() {}, removeItem() { throw new Error("blocked"); } });
  assert.equal(repository.load().status, "outdated");
  assert.equal(repository.reset(), false);
  assert.equal(repository.load().status, "outdated");
});


test("changed answers replace the same evidence outcome instead of increasing evidence", () => {
  const set = practiceSet(1);
  let state = recordPracticeOutcome(emptyProgress(), { lesson_id: lessonId, practice: set, exercise_id: "exercise-1", concept_id: "german-greetings", correct: true });
  state = recordPracticeOutcome(state, { lesson_id: lessonId, practice: set, exercise_id: "exercise-1", concept_id: "german-greetings", correct: false });
  const concept = progressView(state, concepts, lessonId).concepts[0];
  assert.equal(concept.evidence_count, 1);
  assert.equal(concept.correct_count, 0);
  assert.equal(concept.correct_percent, 0);
  assert.equal(concept.status, "in_progress");
});

test("malformed stored JSON remains untouched until explicit reset", () => {
  const rawStorage = new MemoryStorage();
  rawStorage.setItem(PROGRESS_STORAGE_KEY, "{broken");
  const repository = new BrowserProgressStorage(rawStorage);
  assert.equal(repository.load().status, "corrupt");
  assert.equal(rawStorage.getItem(PROGRESS_STORAGE_KEY), "{broken");
  assert.equal(repository.reset(), true);
  assert.equal(rawStorage.getItem(PROGRESS_STORAGE_KEY), null);
});


test("new attempts retain history without repeating per-lesson XP or achievements", () => {
  const first = assessmentReceipt({ attemptId: "attempt-first" });
  const second = assessmentReceipt({ attemptId: "attempt-second" });
  let state = recordAssessmentResult(emptyProgress(), first.attempt, first.result);
  const firstXp = progressView(state, concepts, lessonId).total_xp;
  state = recordAssessmentResult(state, second.attempt, second.result);
  const view = progressView(state, concepts, lessonId);
  assert.equal(view.assessment_history.length, 2);
  assert.equal(view.total_xp, firstXp);
  assert.equal(view.achievements.filter((item) => item.unlocked).length, 2);
});
