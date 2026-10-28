export type CourseModule = {
  id: string;
  title: string;
  description: string;
};

export type CourseLevel = {
  id: string;
  label: string;
  title: string;
  description: string;
  modules: CourseModule[];
};

export type CourseSummary = {
  id: string;
  slug: string;
  title: string;
  description: string;
  learning_rationale: string;
  curriculum_note: string;
  level_count: number;
  module_count: number;
};

export type CourseDetail = CourseSummary & {
  levels: CourseLevel[];
};

export type LessonDetail = {
  lesson_id: string;
  course: { id: string; slug: string; title: string };
  level: { id: string; title: string };
  title: string;
  review_status: "reviewed";
  content_version: string;
  objectives: { id: string; description: string }[];
  vocabulary: { term: string; translation: string; example: string; example_translation: string; pronunciation_note: string | null }[];
  grammar: { id: string; title: string; explanation: string; examples: string[] }[];
  sections: { section_id: string; title: string; introduction: string; steps: { title: string; explanation: string; example: string }[] }[];
  dialogues: { dialogue_id: string; title: string; context: string; turns: { speaker: string; text: string; translation: string }[] }[];
  common_mistakes: { incorrect: string; correction: string; explanation: string }[];
  recap: string[];
  concepts: { id: string; title: string; description: string }[];
  concept_ids: string[];
};

export type ExerciseOption = { option_id: string; label: string };
export type MatchingItem = { item_id: string; label: string };
type PublicExerciseBase = {
  exercise_id: string;
  lesson_id: string;
  version: string;
  concept_id: string;
  evidence_id: string;
  difficulty: "beginner" | "elementary" | "intermediate" | "advanced";
  prompt: string;
};
export type MultipleChoiceExercise = PublicExerciseBase & {
  kind: "multiple_choice";
  options: ExerciseOption[];
};
export type MatchingExercise = PublicExerciseBase & {
  kind: "matching";
  left_items: MatchingItem[];
  right_items: MatchingItem[];
};
export type FillBlankExercise = PublicExerciseBase & {
  kind: "fill_blank";
  sentence_template: string;
  blank_label: string;
};
export type PracticeExercise = MultipleChoiceExercise | MatchingExercise | FillBlankExercise;
export type PracticeSet = {
  lesson_id: string;
  exercise_set_id: string;
  version: string;
  exercises: PracticeExercise[];
};
export type MatchingAnswerPair = { left_id: string; right_id: string };
export type PracticeAnswer = string | MatchingAnswerPair[];
export type PracticeCheckResult = {
  correct: boolean;
  feedback: string;
  concept_id: string;
};

type AssessmentQuestionBase = {
  question_id: string;
  concept_id: string;
  evidence_id: string;
  prompt: string;
  difficulty: "beginner" | "elementary" | "intermediate" | "advanced";
};
export type AssessmentMultipleChoiceQuestion = AssessmentQuestionBase & {
  kind: "multiple_choice";
  options: ExerciseOption[];
};
export type AssessmentMatchingQuestion = AssessmentQuestionBase & {
  kind: "matching";
  left_items: MatchingItem[];
  right_items: MatchingItem[];
};
export type AssessmentFillBlankQuestion = AssessmentQuestionBase & {
  kind: "fill_blank";
  sentence_template: string;
  blank_label: string;
};
export type AssessmentQuestion = AssessmentMultipleChoiceQuestion | AssessmentMatchingQuestion | AssessmentFillBlankQuestion;
export type AssessmentAttempt = {
  attempt_id: string;
  lesson_id: string;
  bank_version: string;
  question_count: 15;
  questions: AssessmentQuestion[];
};
export type AssessmentAnswerValue = string | MatchingAnswerPair[];
export type AssessmentSubmission = { question_id: string; value: AssessmentAnswerValue }[];
export type AssessmentConceptResult = {
  concept_id: string;
  correct_count: number;
  total_questions: number;
  score_percent: number;
  weak: boolean;
};
export type AssessmentQuestionReview = {
  question_id: string;
  correct: boolean;
  correct_answer: string | MatchingAnswerPair[];
  explanation: string;
};
export type AssessmentResult = {
  attempt_id: string;
  lesson_id: string;
  correct_count: number;
  total_questions: 15;
  score_percent: number;
  mastery_threshold_percent: number;
  mastery_achieved: boolean;
  concept_results: AssessmentConceptResult[];
  weak_concepts: string[];
  review: AssessmentQuestionReview[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isPublicExercise(value: unknown): value is PracticeExercise {
  if (!isRecord(value) || !isString(value.exercise_id) || !isString(value.lesson_id) ||
      !isString(value.version) || !isString(value.concept_id) || !isString(value.evidence_id) || !isString(value.prompt) ||
      !["beginner", "elementary", "intermediate", "advanced"].includes(String(value.difficulty))) {
    return false;
  }
  if (value.kind === "multiple_choice") {
    return Array.isArray(value.options) && value.options.every((item) =>
      isRecord(item) && isString(item.option_id) && isString(item.label));
  }
  if (value.kind === "matching") {
    const validItems = (items: unknown) => Array.isArray(items) && items.every((item) =>
      isRecord(item) && isString(item.item_id) && isString(item.label));
    return validItems(value.left_items) && validItems(value.right_items);
  }
  return value.kind === "fill_blank" && isString(value.sentence_template) && isString(value.blank_label);
}

export function isPracticeSet(value: unknown): value is PracticeSet {
  return isRecord(value) && isString(value.lesson_id) && isString(value.exercise_set_id) &&
    isString(value.version) && Array.isArray(value.exercises) && value.exercises.every(isPublicExercise);
}

export function isPracticeCheckResult(value: unknown): value is PracticeCheckResult {
  return isRecord(value) && typeof value.correct === "boolean" && isString(value.feedback) && isString(value.concept_id);
}

function isAssessmentQuestion(value: unknown): value is AssessmentQuestion {
  if (!isRecord(value) || !isString(value.question_id) || !isString(value.concept_id) || !isString(value.evidence_id) ||
      !isString(value.prompt) || !["beginner", "elementary", "intermediate", "advanced"].includes(String(value.difficulty))) return false;
  if (value.kind === "multiple_choice") {
    return Array.isArray(value.options) && value.options.every((item) =>
      isRecord(item) && isString(item.option_id) && isString(item.label));
  }
  if (value.kind === "matching") {
    const validItems = (items: unknown) => Array.isArray(items) && items.every((item) =>
      isRecord(item) && isString(item.item_id) && isString(item.label));
    return validItems(value.left_items) && validItems(value.right_items);
  }
  return value.kind === "fill_blank" && isString(value.sentence_template) && isString(value.blank_label);
}

export function isAssessmentAttempt(value: unknown): value is AssessmentAttempt {
  return isRecord(value) && isString(value.attempt_id) && isString(value.lesson_id) &&
    isString(value.bank_version) && value.question_count === 15 && Array.isArray(value.questions) &&
    value.questions.length === 15 && value.questions.every(isAssessmentQuestion);
}

export function isAssessmentResult(value: unknown): value is AssessmentResult {
  return isRecord(value) && isString(value.attempt_id) && isString(value.lesson_id) &&
    Number.isInteger(value.correct_count) && value.total_questions === 15 &&
    typeof value.score_percent === "number" && typeof value.mastery_threshold_percent === "number" &&
    typeof value.mastery_achieved === "boolean" && Array.isArray(value.weak_concepts) &&
    value.weak_concepts.every(isString) && Array.isArray(value.concept_results) &&
    value.concept_results.every((item) => isRecord(item) && isString(item.concept_id) &&
      Number.isInteger(item.correct_count) && Number.isInteger(item.total_questions) &&
      typeof item.score_percent === "number" && typeof item.weak === "boolean") &&
    Array.isArray(value.review) && value.review.length === 15 &&
    value.review.every((item) => isRecord(item) && isString(item.question_id) &&
      typeof item.correct === "boolean" &&
      (isString(item.correct_answer) || Array.isArray(item.correct_answer)) &&
      isString(item.explanation));
}

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

async function apiFetch(path: string): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
}

export async function getCourses(): Promise<CourseSummary[]> {
  const response = await apiFetch("/api/courses");
  if (!response.ok) {
    throw new Error(`Course catalog request failed (${response.status}).`);
  }
  return (await response.json()) as CourseSummary[];
}

export async function getCourse(slug: string): Promise<CourseDetail | null> {
  const response = await apiFetch(`/api/courses/${encodeURIComponent(slug)}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Course request failed (${response.status}).`);
  }
  return (await response.json()) as CourseDetail;
}

export async function getLesson(lessonId: string): Promise<LessonDetail | null> {
  const response = await apiFetch(`/api/lessons/${encodeURIComponent(lessonId)}`);
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Lesson request failed (${response.status}).`);
  }
  return (await response.json()) as LessonDetail;
}
