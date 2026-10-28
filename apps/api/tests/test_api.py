from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.main import app

client = TestClient(app)
EXPECTED_COURSES = {
    "german": "German",
    "french": "French",
    "literature": "Literature",
    "psychology": "Psychology",
    "philosophy": "Philosophy",
}


@pytest.fixture(autouse=True)
def reset_ephemeral_assessment_attempts():
    from app.assessments import clear_assessment_attempts

    clear_assessment_attempts()
    yield
    clear_assessment_attempts()


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "know-all-api"}


def test_catalog_contains_exactly_the_five_approved_courses() -> None:
    response = client.get("/api/courses")

    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 5
    assert {course["slug"]: course["title"] for course in courses} == EXPECTED_COURSES
    assert all(course["id"] and course["description"] for course in courses)
    assert all(course["level_count"] > 0 and course["module_count"] > 0 for course in courses)


def test_each_course_has_a_detail_and_representative_modules() -> None:
    summaries = client.get("/api/courses").json()

    for summary in summaries:
        response = client.get(f"/api/courses/{summary['slug']}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["id"] == summary["id"]
        assert detail["slug"] == summary["slug"]
        assert detail["learning_rationale"]
        assert "representative" in detail["curriculum_note"].lower()
        assert detail["levels"]
        assert all(level["modules"] for level in detail["levels"])


def test_german_and_french_show_cefr_pathway_without_claiming_completion() -> None:
    for slug in ("german", "french"):
        detail = client.get(f"/api/courses/{slug}").json()
        assert [level["label"] for level in detail["levels"]] == [
            "A1", "A2", "B1", "B2", "C1", "C2"
        ]
        assert "representative" in detail["curriculum_note"].lower()


def test_unknown_course_slug_returns_predictable_404() -> None:
    response = client.get("/api/courses/not-a-course")

    assert response.status_code == 404
    assert response.json() == {
        "code": "course_not_found",
        "message": "No course was found for slug 'not-a-course'.",
    }


def test_german_a1_greetings_lesson_is_complete_and_stable() -> None:
    response = client.get("/api/lessons/german-a1-greetings")

    assert response.status_code == 200
    lesson = response.json()
    assert lesson["lesson_id"] == "german-a1-greetings"
    assert lesson["course"] == {"id": "course-german", "slug": "german", "title": "German"}
    assert lesson["level"] == {"id": "german-a1", "title": "A1 · Beginner"}
    assert lesson["review_status"] == "reviewed"
    assert lesson["content_version"] == "1.0.0"
    assert len(lesson["objectives"]) >= 3
    assert all({"term", "translation", "example", "example_translation"} <= item.keys() for item in lesson["vocabulary"])
    assert all({"title", "explanation", "examples"} <= item.keys() for item in lesson["grammar"])
    assert all(section["steps"] and section["introduction"] for section in lesson["sections"])
    assert all(dialogue["turns"] and dialogue["context"] for dialogue in lesson["dialogues"])
    assert lesson["common_mistakes"] and lesson["recap"]
    assert lesson["concept_ids"] == [
        "german-greetings",
        "german-self-introduction",
        "german-formal-address",
        "german-wie-gehts",
    ]
    assert [concept["id"] for concept in lesson["concepts"]] == lesson["concept_ids"]


def test_unknown_lesson_returns_predictable_404() -> None:
    response = client.get("/api/lessons/not-a-real-lesson")

    assert response.status_code == 404
    assert response.json() == {
        "code": "lesson_not_found",
        "message": "No lesson was found for ID 'not-a-real-lesson'.",
    }


def test_lesson_model_validates_and_openapi_documents_response_schemas() -> None:
    from app.lesson_models import LessonDetail

    payload = client.get("/api/lessons/german-a1-greetings").json()
    validated = LessonDetail.model_validate(payload)
    assert validated.title == "Greetings and introducing yourself"
    assert validated.vocabulary[0].term == "Hallo"
    assert validated.sections[0].steps[0].title == "Notice the time"
    malformed_payload = {**payload, "course": None}
    with pytest.raises(ValidationError):
        LessonDetail.model_validate(malformed_payload)

    operation = app.openapi()["paths"]["/api/lessons/{lesson_id}"]["get"]
    assert operation["parameters"][0]["name"] == "lesson_id"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("LessonDetail")
    assert operation["responses"]["404"]["content"]["application/json"]["schema"]["$ref"].endswith("ApiError")
    schemas = app.openapi()["components"]["schemas"]
    assert "LessonDetail" in schemas
    assert "LessonConcept" in schemas
    assert "LessonStep" in schemas


PRACTICE_URL = "/api/lessons/german-a1-greetings/practice"


def test_practice_retrieval_is_typed_and_does_not_leak_answer_keys() -> None:
    from app.practice_models import PracticeSet

    response = client.get(PRACTICE_URL)

    assert response.status_code == 200
    practice = PracticeSet.model_validate(response.json())
    assert practice.lesson_id == "german-a1-greetings"
    assert practice.exercise_set_id == "german-a1-greetings-practice"
    assert len(practice.exercises) == 7
    assert {exercise.kind for exercise in practice.exercises} == {
        "multiple_choice", "matching", "fill_blank"
    }
    assert all(exercise.lesson_id == practice.lesson_id for exercise in practice.exercises)
    assert all(exercise.version and exercise.concept_id and exercise.evidence_id and exercise.difficulty for exercise in practice.exercises)
    body = response.text
    for private_field in (
        "answer_key", "accepted_answers", "normalization",
        "correct_feedback", "incorrect_feedback",
    ):
        assert private_field not in body
    assert "answer_key" not in body
    assert "heisse" not in body  # configured spelling alias


@pytest.mark.parametrize(
    ("exercise_id", "answer", "concept_id"),
    [
        ("german-a1-greeting-time", "option-a", "german-greetings"),
        ("german-a1-introduce-name", "option-a", "german-self-introduction"),
        ("german-a1-formal-name-question", "option-b", "german-formal-address"),
        (
            "german-a1-match-greetings",
            [
                {"left_id": "guten-morgen", "right_id": "good-morning"},
                {"left_id": "guten-tag", "right_id": "good-day"},
                {"left_id": "tschuss", "right_id": "bye"},
            ],
            "german-greetings",
        ),
        ("german-a1-fill-name-verb", "heiße", "german-self-introduction"),
        ("german-a1-fill-formal-verb", "heißen", "german-formal-address"),
    ],
)
def test_each_practice_type_accepts_a_correct_answer(
    exercise_id: str, answer: object, concept_id: str
) -> None:
    response = client.post(
        f"{PRACTICE_URL}/check", json={"exercise_id": exercise_id, "answer": answer}
    )

    assert response.status_code == 200
    assert response.json() == {
        "correct": True,
        "feedback": response.json()["feedback"],
        "concept_id": concept_id,
    }
    assert set(response.json()) == {"correct", "feedback", "concept_id"}


@pytest.mark.parametrize(
    ("exercise_id", "answer", "concept_id"),
    [
        ("german-a1-greeting-time", "option-b", "german-greetings"),
        ("german-a1-introduce-name", "option-b", "german-self-introduction"),
        (
            "german-a1-match-greetings",
            [
                {"left_id": "guten-morgen", "right_id": "good-day"},
                {"left_id": "guten-tag", "right_id": "good-morning"},
                {"left_id": "tschuss", "right_id": "bye"},
            ],
            "german-greetings",
        ),
        ("german-a1-fill-name-verb", "bin", "german-self-introduction"),
    ],
)
def test_incorrect_practice_answers_return_concept_linked_feedback(
    exercise_id: str, answer: object, concept_id: str
) -> None:
    response = client.post(
        f"{PRACTICE_URL}/check", json={"exercise_id": exercise_id, "answer": answer}
    )

    assert response.status_code == 200
    assert response.json()["correct"] is False
    assert response.json()["concept_id"] == concept_id
    assert response.json()["feedback"]


@pytest.mark.parametrize(
    ("exercise_id", "answer"),
    [
        ("german-a1-fill-name-verb", "heiße"),
        ("german-a1-fill-name-verb", "heisse"),
        ("german-a1-fill-name-verb", "  HEISSE  "),
        ("german-a1-fill-goodbye", "Tschüss"),
        ("german-a1-fill-goodbye", "  TSCHÜSS  "),
        ("german-a1-fill-goodbye", "Tschu\u0308ss"),
    ],
)
def test_fill_blank_accepts_explicit_variants_with_unicode_normalization(
    exercise_id: str, answer: str
) -> None:
    response = client.post(
        f"{PRACTICE_URL}/check",
        json={"exercise_id": exercise_id, "answer": answer},
    )

    assert response.status_code == 200
    assert response.json()["correct"] is True


def test_matching_requires_a_complete_valid_set_of_pairs() -> None:
    response = client.post(
        f"{PRACTICE_URL}/check",
        json={
            "exercise_id": "german-a1-match-greetings",
            "answer": [{"left_id": "guten-morgen", "right_id": "unknown"}],
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_practice_answer"


@pytest.mark.parametrize(
    "payload",
    [
        {"exercise_id": "german-a1-greeting-time"},
        {"exercise_id": "german-a1-greeting-time", "answer": 12},
        {"exercise_id": "german-a1-greeting-time", "answer": "morning", "extra": True},
        {"exercise_id": "german-a1-match-greetings", "answer": ["not-a-pair"]},
    ],
)
def test_malformed_practice_answers_are_rejected(payload: dict[str, object]) -> None:
    response = client.post(f"{PRACTICE_URL}/check", json=payload)

    assert response.status_code == 422


def test_incompatible_answer_type_is_rejected_without_checking_correctness() -> None:
    response = client.post(
        f"{PRACTICE_URL}/check",
        json={
            "exercise_id": "german-a1-greeting-time",
            "answer": [{"left_id": "x", "right_id": "y"}],
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "incompatible_practice_answer"


def test_unknown_practice_lesson_and_exercise_return_structured_404s() -> None:
    unknown_lesson = client.get("/api/lessons/not-a-lesson/practice")
    assert unknown_lesson.status_code == 404
    assert unknown_lesson.json()["code"] == "lesson_not_found"

    unknown_exercise = client.post(
        f"{PRACTICE_URL}/check", json={"exercise_id": "missing", "answer": "anything"}
    )
    assert unknown_exercise.status_code == 404
    assert unknown_exercise.json()["code"] == "exercise_not_found"

    unknown_lesson_check = client.post(
        "/api/lessons/not-a-lesson/practice/check",
        json={"exercise_id": "german-a1-greeting-time", "answer": "option-a"},
    )
    assert unknown_lesson_check.status_code == 404
    assert unknown_lesson_check.json()["code"] == "lesson_not_found"


def test_practice_openapi_documents_retrieval_and_check_schemas() -> None:
    schema = app.openapi()
    get_operation = schema["paths"]["/api/lessons/{lesson_id}/practice"]["get"]
    post_operation = schema["paths"]["/api/lessons/{lesson_id}/practice/check"]["post"]

    assert get_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("PracticeSet")
    assert post_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("PracticeCheckRequest")
    assert post_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("PracticeCheckResponse")
    assert post_operation["responses"]["400"]["content"]["application/json"]["schema"]["$ref"].endswith("ApiError")
    assert post_operation["responses"]["404"]["content"]["application/json"]["schema"]["$ref"].endswith("ApiError")
    public_schemas = schema["components"]["schemas"]
    assert "PublicMultipleChoiceExercise" in public_schemas
    assert "PublicMatchingExercise" in public_schemas
    assert "PublicFillBlankExercise" in public_schemas
    assert "InternalMultipleChoiceAnswer" not in public_schemas
    assert "InternalMatchingAnswer" not in public_schemas
    assert "InternalFillBlankAnswer" not in public_schemas


ASSESSMENT_URL = "/api/lessons/german-a1-greetings/assessment-attempts"


def create_assessment() -> dict[str, object]:
    response = client.post(ASSESSMENT_URL, json={})
    assert response.status_code == 200
    return response.json()


def correct_assessment_answers() -> list[dict[str, object]]:
    from app.assessments import GERMAN_A1_ASSESSMENT_QUESTIONS
    from app.assessment_models import (
        InternalFillBlankQuestion,
        InternalMatchingQuestion,
        InternalMultipleChoiceQuestion,
    )

    answers: list[dict[str, object]] = []
    for question in GERMAN_A1_ASSESSMENT_QUESTIONS:
        if isinstance(question, InternalMultipleChoiceQuestion):
            value: object = question.answer_key
        elif isinstance(question, InternalMatchingQuestion):
            value = [pair.model_dump() for pair in question.answer_key]
        elif isinstance(question, InternalFillBlankQuestion):
            value = question.accepted_answers[0]
        else:  # pragma: no cover - protects new bank types from silent test omissions
            raise AssertionError("Unhandled assessment question type")
        answers.append({"question_id": question.public.question_id, "value": value})
    return answers


def submit_assessment(attempt_id: str, answers: list[dict[str, object]]):
    return client.post(
        f"{ASSESSMENT_URL}/{attempt_id}/submit", json={"answers": answers}
    )


def test_assessment_attempt_contains_fifteen_unique_public_questions() -> None:
    from app.assessment_models import PublicAssessmentAttempt

    response = client.post(ASSESSMENT_URL, json={})
    assert response.status_code == 200
    attempt = PublicAssessmentAttempt.model_validate(response.json())
    assert attempt.lesson_id == "german-a1-greetings"
    assert attempt.question_count == 15
    assert len(attempt.questions) == 15
    assert len({question.question_id for question in attempt.questions}) == 15
    assert len({question.prompt for question in attempt.questions}) == 15
    assert {question.kind for question in attempt.questions} == {
        "multiple_choice", "matching", "fill_blank"
    }
    lesson_concepts = set(client.get("/api/lessons/german-a1-greetings").json()["concept_ids"])
    assert all(question.concept_id in lesson_concepts and question.evidence_id for question in attempt.questions)
    serialized = response.text
    for private_field in ("answer_key", "accepted_answers", "normalization", "explanation"):
        assert private_field not in serialized
    schemas = app.openapi()["components"]["schemas"]
    assert "InternalMultipleChoiceQuestion" not in schemas
    assert "InternalMatchingQuestion" not in schemas
    assert "InternalFillBlankQuestion" not in schemas



def test_reviewed_cross_bank_evidence_ids_identify_repeated_learning_items() -> None:
    practice = client.get(PRACTICE_URL).json()["exercises"]
    attempt = client.post(ASSESSMENT_URL, json={}).json()["questions"]
    practice_by_id = {item["exercise_id"]: item["evidence_id"] for item in practice}
    assessment_by_id = {item["question_id"]: item["evidence_id"] for item in attempt}
    assert practice_by_id["german-a1-greeting-time"] == assessment_by_id["german-a1-assess-greeting-morning"]
    assert practice_by_id["german-a1-introduce-name"] == assessment_by_id["german-a1-assess-name-meaning"]
    assert practice_by_id["german-a1-formal-name-question"] == assessment_by_id["german-a1-assess-formal-name-question"]
    assert practice_by_id["german-a1-fill-name-verb"] == assessment_by_id["german-a1-assess-name-verb"]
    assert practice_by_id["german-a1-fill-goodbye"] == assessment_by_id["german-a1-assess-informal-goodbye"]

def test_assessment_bank_does_not_repeat_questions_when_fresh_set_is_exhausted() -> None:
    attempt = create_assessment()
    response = client.post(ASSESSMENT_URL, json={})

    assert response.status_code == 409
    assert response.json() == {
        "code": "assessment_bank_exhausted",
        "message": "A fresh set of 15 distinct reviewed questions is not available yet.",
    }
    assert len(attempt["questions"]) == 15


def test_assessment_exclusions_do_not_return_partial_or_repeated_sets() -> None:
    excluded = [question["question_id"] for question in create_assessment()["questions"]]
    response = client.post(
        ASSESSMENT_URL, json={"exclude_question_ids": excluded}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "assessment_bank_exhausted"


def test_all_correct_assessment_is_scored_deterministically() -> None:
    attempt = create_assessment()
    response = submit_assessment(str(attempt["attempt_id"]), correct_assessment_answers())

    assert response.status_code == 200
    result = response.json()
    assert result["correct_count"] == 15
    assert result["total_questions"] == 15
    assert result["score_percent"] == 100.0
    assert result["mastery_threshold_percent"] == 80.0
    assert result["mastery_achieved"] is True
    assert result["weak_concepts"] == []
    assert len(result["review"]) == 15
    assert all(item["correct"] for item in result["review"])
    assert all(item["explanation"] and item["correct_answer"] for item in result["review"])


def test_eighty_percent_achieves_mastery_and_reports_weak_concept() -> None:
    attempt = create_assessment()
    answers = correct_assessment_answers()
    wellbeing_ids = {
        "german-a1-assess-informal-wellbeing",
        "german-a1-assess-formal-wellbeing",
        "german-a1-assess-wellbeing-answer",
    }
    for answer in answers:
        if answer["question_id"] == "german-a1-assess-informal-wellbeing":
            answer["value"] = "b"
        elif answer["question_id"] == "german-a1-assess-formal-wellbeing":
            answer["value"] = "a"
        elif answer["question_id"] == "german-a1-assess-wellbeing-answer":
            answer["value"] = "bitte"

    result = submit_assessment(str(attempt["attempt_id"]), answers).json()
    wellbeing = next(
        item for item in result["concept_results"]
        if item["concept_id"] == "german-wie-gehts"
    )
    assert result["correct_count"] == 12
    assert result["score_percent"] == 80.0
    assert result["mastery_achieved"] is True
    assert wellbeing == {
        "concept_id": "german-wie-gehts",
        "correct_count": 0,
        "total_questions": 3,
        "score_percent": 0.0,
        "weak": True,
    }
    assert "german-wie-gehts" in result["weak_concepts"]


def test_matching_and_fill_blank_answers_use_explicit_normalization() -> None:
    attempt = create_assessment()
    answers = correct_assessment_answers()
    match = next(
        item for item in answers
        if item["question_id"] == "german-a1-assess-match-greetings"
    )
    match["value"].reverse()
    fill = next(
        item for item in answers
        if item["question_id"] == "german-a1-assess-name-verb"
    )
    fill["value"] = "  HEISSE  "
    result = submit_assessment(str(attempt["attempt_id"]), answers)

    assert result.status_code == 200
    assert result.json()["correct_count"] == 15


def test_same_submission_is_idempotent_and_changed_submission_is_conflict() -> None:
    attempt = create_assessment()
    answers = correct_assessment_answers()
    first = submit_assessment(str(attempt["attempt_id"]), answers)
    retry = submit_assessment(str(attempt["attempt_id"]), list(reversed(answers)))

    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()

    changed = correct_assessment_answers()
    changed[0]["value"] = "b"
    conflict = submit_assessment(str(attempt["attempt_id"]), changed)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "attempt_already_submitted"


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown"])
def test_incomplete_duplicate_and_unknown_assessment_answers_are_rejected(change: str) -> None:
    attempt = create_assessment()
    answers = correct_assessment_answers()
    if change == "missing":
        answers.pop()
    elif change == "duplicate":
        answers[-1] = dict(answers[0])
    else:
        answers[-1] = {"question_id": "unknown-question", "value": "a"}

    rejected = submit_assessment(str(attempt["attempt_id"]), answers)
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "invalid_assessment_submission"
    # Invalid submissions do not freeze an attempt.
    accepted = submit_assessment(str(attempt["attempt_id"]), correct_assessment_answers())
    assert accepted.status_code == 200


def test_attempt_unknown_id_and_wrong_lesson_are_not_found() -> None:
    unknown = submit_assessment("missing-attempt", correct_assessment_answers())
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "attempt_not_found"

    attempt = create_assessment()
    mismatched = client.post(
        f"/api/lessons/not-a-lesson/assessment-attempts/{attempt['attempt_id']}/submit",
        json={"answers": correct_assessment_answers()},
    )
    assert mismatched.status_code == 404
    assert mismatched.json()["code"] == "attempt_not_found"


def test_unknown_assessment_lesson_returns_structured_404() -> None:
    response = client.post("/api/lessons/not-a-lesson/assessment-attempts", json={})

    assert response.status_code == 404
    assert response.json()["code"] == "lesson_not_found"


def test_assessment_openapi_documents_public_attempt_and_submit_schemas() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    create = paths["/api/lessons/{lesson_id}/assessment-attempts"]["post"]
    submit = paths[
        "/api/lessons/{lesson_id}/assessment-attempts/{attempt_id}/submit"
    ]["post"]

    assert create["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("AssessmentAttemptRequest")
    assert create["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("PublicAssessmentAttempt")
    assert create["responses"]["409"]["content"]["application/json"]["schema"]["$ref"].endswith("ApiError")
    assert submit["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("AssessmentSubmitRequest")
    assert submit["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("AssessmentResult")
    assert submit["responses"]["409"]["content"]["application/json"]["schema"]["$ref"].endswith("ApiError")
    schemas = schema["components"]["schemas"]
    assert "PublicMultipleChoiceQuestion" in schemas
    assert "PublicMatchingQuestion" in schemas
    assert "PublicFillBlankQuestion" in schemas
    assert "InternalMultipleChoiceQuestion" not in schemas
    assert "InternalMatchingQuestion" not in schemas
    assert "InternalFillBlankQuestion" not in schemas
