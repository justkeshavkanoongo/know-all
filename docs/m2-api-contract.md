# Milestone 2 API and browser-state contract

**Status:** Reconciled through Phase 4. The lesson route and German A1 content are implemented in Phase 1; practice retrieval/check in Phase 2; deterministic assessment attempts and scoring in Phase 3; browser-local progress and rewards in Phase 4. Tutor remains specified for a later phase. Existing course and health routes remain the Milestone 1 contract.

## Principles and boundaries

- The FastAPI service remains the source of truth for reviewed course and lesson content, exercise banks, assessment questions, and deterministic grading rules.
- Response models are explicit Pydantic schemas. IDs and slugs are stable across releases; content changes do not silently repurpose an existing ID.
- Lesson content is curated and reviewed. A tutor may explain that content but does not author or modify it.
- No user account, database, server-side progress, cross-device synchronization, RAG, or provider key is introduced in M2.
- FastAPI's generated `/docs`, `/redoc`, and `/openapi.json` describe registered API routes. They do not expose credentials.

## Retained Milestone 1 routes

| Method and path | Success response | Behavior |
| --- | --- | --- |
| `GET /health` | `HealthResponse` | Returns service health. |
| `GET /api/courses` | `CourseSummary[]` | Returns exactly the five catalog courses in stable order. |
| `GET /api/courses/{slug}` | `CourseDetail` | Returns one course; unknown slugs return 404. |
| `GET /api/lessons/{lesson_id}` | `LessonDetail` | Returns a reviewed lesson with typed course/level references, objectives, content sections, and concept definitions/IDs; unknown IDs return 404. |

The current course-not-found error shape is `{ "code": "course_not_found", "message": "Course not found" }`. M2 routes use the same flat domain-error shape for non-validation errors.

## M2 endpoint contract

The tutor endpoint remains planned for a later M2 phase. The lesson endpoint is implemented in Phase 1, practice endpoints in Phase 2, assessment endpoints in Phase 3, and local progress in Phase 4. Field names and enums below are normative unless a reviewed contract revision changes this document.

### Tutor availability

`GET /api/tutor/status`

Response `TutorStatus`:

```json
{ "provider": "grok", "configured": false, "model": null }
```

`configured` reports whether the server has the necessary provider configuration; it never returns the key or its value. `model` is the configured public model identifier or `null`. The browser uses this response to present tutor availability; it must not infer configuration from local environment state.

### Reviewed lesson content

`GET /api/lessons/{lesson_id}` returns `LessonDetail`:

```json
{
  "lesson_id": "german-a1-greetings",
  "course": {"id": "course-german", "slug": "german", "title": "German"},
  "level": {"id": "german-a1", "title": "A1 · Beginner"},
  "title": "Greetings and introducing yourself",
  "review_status": "reviewed",
  "content_version": "1.0.0",
  "objectives": [{"id": "introduce-yourself", "description": "Greet someone and introduce yourself."}],
  "vocabulary": [{"term": "Guten Tag", "translation": "Good day", "example": "Guten Tag, ich heiße Ada.", "example_translation": "Hello, my name is Ada.", "pronunciation_note": null}],
  "grammar": [{"id": "german-ich-heisse", "title": "A simple introduction", "explanation": "Use ich heiße to say your name.", "examples": ["Ich heiße Ada."]}],
  "sections": [{"section_id": "introduce-yourself", "title": "Introduce yourself", "introduction": "A short introduction.", "steps": [{"title": "Give your name", "explanation": "Use ich heiße and your name.", "example": "Ich heiße Ada."}]}],
  "dialogues": [{"dialogue_id": "meeting-ada", "title": "Meeting Ada", "context": "An informal first meeting.", "turns": [{"speaker": "Ada", "text": "Guten Tag.", "translation": "Hello."}]}],
  "common_mistakes": [{"incorrect": "Ich bin heiße Ada.", "correction": "Ich heiße Ada.", "explanation": "Do not combine these two constructions."}],
  "recap": ["Use Guten Tag as a polite greeting."],
  "concepts": [{"id": "german-greetings", "title": "Greetings and farewells", "description": "Choose suitable expressions."}],
  "concept_ids": ["german-greetings"]
}
```

Collections use reusable typed item models, including generic `LessonConcept` and step structures with no German-specific fields. `concept_ids` is derived from the stable concept definitions. The German A1 greetings lesson is reviewed, deterministic, and version-controlled. Unknown lesson IDs return 404.

### Lesson practice — implemented in Phase 2

`GET /api/lessons/{lesson_id}/practice` returns `PracticeSet`:

```json
{
  "lesson_id": "german-a1-greetings",
  "exercise_set_id": "german-a1-greetings-practice",
  "version": "1.0.0",
  "exercises": [
    {
      "kind": "multiple_choice",
      "exercise_id": "german-a1-greeting-time",
      "lesson_id": "german-a1-greetings",
      "version": "1.0.0",
      "concept_id": "german-greetings",
      "difficulty": "beginner",
      "prompt": "Which greeting is a natural choice in the morning?",
      "options": [{"option_id": "option-a", "label": "Guten Morgen"}]
    },
    {
      "kind": "matching",
      "exercise_id": "german-a1-match-greetings",
      "lesson_id": "german-a1-greetings",
      "version": "1.0.0",
      "concept_id": "german-greetings",
      "difficulty": "beginner",
      "prompt": "Match each German greeting to its English meaning.",
      "left_items": [{"item_id": "guten-morgen", "label": "Guten Morgen"}],
      "right_items": [{"item_id": "good-morning", "label": "Good morning"}]
    },
    {
      "kind": "fill_blank",
      "exercise_id": "german-a1-fill-name-verb",
      "lesson_id": "german-a1-greetings",
      "version": "1.0.0",
      "concept_id": "german-self-introduction",
      "difficulty": "beginner",
      "prompt": "Complete the sentence with the verb form for ‘I am called’.",
      "sentence_template": "Ich ___ Ada.",
      "blank_label": "Missing word"
    }
  ]
}
```

The list above illustrates all three discriminated payload types; retrieval returns the full reviewed bank. Every public item has a stable ID, lesson ID, version, concept ID, reviewed `evidence_id`, difficulty, and prompt. Cross-bank items that test the same reviewed evidence share an `evidence_id` so progress does not count them independently. Multiple-choice responses expose opaque option IDs and labels. Matching responses expose left and right item IDs and labels. Fill-blank responses expose a sentence template and label. Public models are distinct from internal evaluator models; answer keys, accepted-answer lists, and normalization configuration are never serialized.

`POST /api/lessons/{lesson_id}/practice/check` accepts `PracticeCheckRequest`. `answer` is either a string (multiple choice option ID or fill-blank text) or an array of matching pairs `{ "left_id": "...", "right_id": "..." }`.

Request examples:

```json
{ "exercise_id": "german-a1-greeting-time", "answer": "option-a" }
```

```json
{
  "exercise_id": "german-a1-match-greetings",
  "answer": [
    {"left_id": "guten-morgen", "right_id": "good-morning"},
    {"left_id": "guten-tag", "right_id": "good-day"},
    {"left_id": "tschuss", "right_id": "bye"}
  ]
}
```

Success response `PracticeCheckResponse` is exactly `{ "correct": true, "feedback": "...", "concept_id": "..." }`. Correctness and feedback are returned only after the server checks the submitted answer; no separate answer-key or score fields are returned. Incorrect but well-formed answers return HTTP 200 with `correct: false` and concept-linked corrective feedback. Practice checks are stateless and do not grant XP or persist learner data.

Multiple choice answers must be one of that exercise's public option IDs. Matching validation requires exactly one pair for every left item and rejects unknown or duplicate left IDs and unknown right IDs; pair order does not matter. Fill-blank comparison normalizes Unicode to NFC, trims and collapses whitespace, and compares lowercase strings. It preserves accents and umlaut distinctions; accepted alternatives such as `heisse` for `heiße` are explicitly reviewed. No fuzzy or semantic matching is used.

Unknown lesson and exercise IDs return structured 404 errors (`lesson_not_found`, `exercise_not_found`). Malformed request schemas return FastAPI's 422 validation response. A structurally valid answer with the wrong payload type or invalid option/pair data returns a structured 400 (`incompatible_practice_answer` or `invalid_practice_answer`).

### Tutor

`POST /api/lessons/{lesson_id}/tutor`

Request `TutorRequest`:

```json
{
  "conversation_id": "client-generated-opaque-id",
  "question": "Can you explain this more simply?",
  "intent": "simpler",
  "history": [{"role": "user", "content": "What does this phrase mean?"}]
}
```

`intent` is `question`, `simpler`, or `examples`; history roles are `user` or `assistant`. Request size, question length, and history length are bounded by schema validation. The response `TutorResponse` is `{ "conversation_id": "...", "answer": "..." }`.

The server supplies only the requested reviewed lesson context, applies provider timeouts, and validates the provider result before returning it. It does not expose system prompts, keys, raw provider bodies, stack traces, or internal configuration. Provider access is optional. Tests use a mock provider; Phase 0 makes no live provider call.

### Assessment attempts

`POST /api/lessons/{lesson_id}/assessment-attempts` accepts `AssessmentAttemptRequest` `{ "exclude_question_ids": ["..."] }`; the exclusion field may be omitted. It returns `AssessmentAttempt` with a unique `attempt_id`, `lesson_id`, `bank_version`, `question_count: 15`, and 15 questions. Question objects expose `question_id`, `kind`, `prompt`, difficulty, public choices/matching items, and concept mapping needed by the UI, but never the answer key. The current reviewed German A1 bank has exactly 15 distinct questions for the first attempt.

Question kinds are `multiple_choice`, `matching`, and `fill_blank`. Assessment questions and accepted answers are fixed version-controlled content, scored server-side. The current bank does **not** support a second non-overlapping set: after its first attempt is issued, another attempt returns 409 `assessment_bank_exhausted` until at least 15 additional distinct questions are reviewed and added. Explicit exclusions that leave fewer than 15 items also return this 409. Questions are not repeated or generated to fill the gap.

`POST /api/lessons/{lesson_id}/assessment-attempts/{attempt_id}/submit` accepts:

```json
{ "answers": [{ "question_id": "q-01", "value": "option-b" }] }
```

It returns `AssessmentResult` containing `attempt_id`, `lesson_id`, `correct_count`, `total_questions`, numeric `score_percent`, `mastery_threshold_percent`, `mastery_achieved`, per-concept results (`concept_id`, counts, percentage, and `weak`), `weak_concepts`, and a review list with each `question_id`, correctness, correct answer, and explanation. Results reveal answers only after submission. The browser UI saves the active attempt and answers in versioned `sessionStorage`, resumes it on refresh, and stores the completed result there so the immutable submission is not needlessly repeated. This is session-scoped convenience, not durable progress.

## Deterministic scoring and mastery

- Each attempt has 15 questions of equal weight. `score_percent = correct_count / 15 * 100`, rounded half-up to two decimal places and serialized as a JSON number. The mastery threshold is 80.00%, held in one server-side configuration constant; 12 of 15 correct achieves mastery.
- The answer key and grading function are deterministic and versioned with the reviewed question bank. Multiple-choice and matching values compare against their exact stable identifiers.
- Fill-blank normalization uses Unicode NFC, trims outer whitespace, collapses internal whitespace, and compares case-insensitively. Accents and umlauts remain significant. Additional accepted aliases must be explicit, reviewed data, not fuzzy matching.
- Concept scores aggregate correct and total mapped questions. A concept is initially marked weak below 80%; this cutoff is centralized alongside the mastery rule.
- Missing, duplicate, or unknown question IDs, or a submission that does not answer exactly the attempt's 15 questions, returns structured 422 `invalid_assessment_submission` and does not freeze the attempt. Malformed request bodies retain FastAPI's standard 422 validation response.

## Immutable attempts and idempotency

- An attempt is created with a unique opaque ID and a frozen set of question IDs and bank version. The current question bank has only enough reviewed material for one such attempt; retakes are blocked with 409 until more questions are authored.
- Its first valid submission freezes the normalized answers and computed result. Repeating that exact submission returns the cached identical result. Submitting a different payload to a submitted attempt returns 409 `attempt_already_submitted`.
- Unknown attempt IDs return 404. The attempt must belong to the lesson in the request path; a mismatch returns 404 to avoid leaking unrelated attempt state.
- The current API has no database. Any in-memory idempotency record is scoped to the running API process and is lost on restart. The browser stores an active attempt, answers, and completed result in session storage and avoids resubmitting after refresh. This is a documented durability limit, not durable server storage.

## Browser-local progress, mastery, and rewards — implemented in Phase 4

There is no `/api/progress` endpoint, account, database, server-authoritative XP balance, or cross-device synchronization. Learning progress is stored separately from appearance settings at `know-it-all:progress:v2` in browser `localStorage`. The typed schema stores stable practice outcomes, completed practice sets, assessment receipts/history, lesson completion, and a derived reward ledger. During the normal application flow, the API validates submitted practice answers and scores assessment submissions; the client does not send a score or XP amount. The browser reducer checks response structure and arithmetic consistency, attempt/question membership, per-concept totals, and mastery consistency. It does not possess a cryptographic signature, authenticated identity, or durable server receipt that binds a result to an attempt/submission. A user controlling browser code or localStorage can fabricate a structurally consistent result or edit progress. Therefore local outcomes cannot establish trusted identity, independent external assessment, or entitlement; future social, payment, and authorization decisions must use a separate server-authoritative design.

Lesson completion is derived after a complete practice set has received a server-checked outcome for every listed exercise or after an assessment receipt passes client consistency checks. Repeated practice updates the existing outcome for that stable exercise ID; it does not duplicate evidence or completion rewards. Assessment history uses the unique attempt ID and ignores an already-recorded receipt.

Mastery is an explainable local inference, not a claim of broad proficiency. For each stable lesson concept, the current rule requires at least five distinct checked items and at least 80% correct. Practice and assessment content expose a reviewed, stable `evidence_id`. The reducer deduplicates concept evidence by that shared ID across both banks and retains the latest checked outcome for a reused item; attempts remain individually recorded in history. Repeated attempts or changed answers for the same evidence item cannot increase the distinct-evidence count. A single correct answer is only observed performance, never mastery. Thresholds are centralized in `apps/web/lib/progress.ts` and may be changed as content evolves. Current claims apply only to the four reviewed concepts in the sample German A1 greetings lesson.

XP rules are centralized in `XP_RULES`: lesson completion is 10 XP, practice-set completion 15 XP, first assessment submission for a lesson 20 XP, and demonstrated assessment mastery 10 XP. Reward IDs are deterministic (`lesson-completed:{lesson_id}`, `practice-completed:{exercise_set_id}`, `assessment-first-submission:{lesson_id}`, `mastery-achieved:{lesson_id}`); the persisted ledger is validated against the learning events and rule values before it is accepted. Level 1 starts at 0 XP and each additional level requires 50 more XP. Achievements are derived from learning events and concept mastery rather than repeated page visits. These browser-local rewards are for motivation only. They are user-editable and are not tamper-proof, authoritative, or entitlements.

## Browser-local state boundary

- Versioned appearance preference: `know-it-all:appearance:v1`.
- Versioned learning progress and XP ledger: `know-it-all:progress:v2` (implemented in Phase 4; legacy v1 data is preserved and requires explicit reset).
- These values live in browser `localStorage`; they are not sent as identity or progress to the API. There is no account, server persistence, or cross-device sync.
- Tutor conversation context is ephemeral to the active tab/session (component state or `sessionStorage`); it is not part of persistent progress storage. Do not persist provider credentials or private API configuration in browser storage.
- Storage access may fail or be unavailable. The UI falls back to in-memory state and indicates that changes will not persist for that page session.
- Progress schema version 2 is validated on load. Version 1 progress is detected at its legacy storage key and reported as unsupported; it is preserved until the learner explicitly resets it because evidence identity cannot be safely reconstructed for arbitrary historical content. Malformed content is classified as corrupt; any unsupported schema version is classified as outdated. Neither is silently overwritten or migrated. The UI preserves it until the learner explicitly chooses “Reset local progress”; future versions may add explicit version-to-version migration functions.
- Assessment attempts and answers remain in session storage under their own lesson-scoped key to resume an active attempt. After the normal API submission flow, the completed result is stored in the persistent progress record only after client consistency checks against the public attempt and response shape; this does not authenticate the response or make local data authoritative.

## Error semantics

Domain errors use `{ "code": "stable_machine_code", "message": "safe human-readable summary" }`. Messages must not include secret values, stack traces, or raw upstream response bodies. FastAPI request validation retains its standard 422 `{ "detail": [...] }` schema unless a later explicit contract revision standardizes it.

| Status | Meaning and representative codes |
| --- | --- |
| 400 | Structurally valid but incompatible or invalid practice answer; `incompatible_practice_answer`, `invalid_practice_answer`. |
| 404 | Unknown course, lesson, exercise, or attempt; `course_not_found`, `lesson_not_found`, `exercise_not_found`, `attempt_not_found`. |
| 409 | State conflict or exhausted non-repeating question bank; `attempt_already_submitted`, `assessment_bank_exhausted`. |
| 422 | Request schema validation uses FastAPI's standard body; a well-formed but incomplete, duplicate, unknown, or otherwise invalid assessment answer set uses flat `invalid_assessment_submission`. |
| 413 | Request exceeds the configured body-size bound. |
| 429 | Provider rate limited; safe `tutor_rate_limited` response and, when known, `Retry-After`. |
| 502 | Provider failure or malformed provider response; safe `tutor_provider_error`. |
| 503 | Tutor is not configured; `tutor_unavailable`. |
| 504 | Provider request timed out; `tutor_timeout`. |

## Documentation and verification

FastAPI's built-in `/docs`, `/redoc`, and `/openapi.json` are enabled in local development. Registered M2 endpoints use request and response models so the OpenAPI document describes their schemas. Phase 0 verified these built-in endpoints; Phase 3 adds assessment routes and schemas. Phase 4 progress is intentionally browser-local and adds no API route. Tutor routes and future phases remain unimplemented.
