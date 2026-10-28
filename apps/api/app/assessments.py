import json
import threading
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from .assessment_models import (
    ASSESSMENT_QUESTION_COUNT,
    MASTERY_THRESHOLD_PERCENT,
    WEAK_CONCEPT_THRESHOLD_PERCENT,
    AssessmentAnswer,
    AssessmentConceptResult,
    AssessmentQuestionReview,
    AssessmentResult,
    InternalAssessmentQuestion,
    InternalFillBlankQuestion,
    InternalMatchingQuestion,
    InternalMultipleChoiceQuestion,
    PublicAssessmentAttempt,
    PublicFillBlankQuestion,
    PublicMatchingQuestion,
    PublicMultipleChoiceQuestion,
    StoredAssessmentAttempt,
)
from .lesson_models import LessonDetail
from .lessons import get_lesson
from .practice_models import MatchingAnswerPair

ASSESSMENT_BANK_VERSION = "german-a1-greetings-assessment-1.0.0"
_ATTEMPTS: dict[str, StoredAssessmentAttempt] = {}
_ATTEMPT_LOCK = threading.RLock()


class AssessmentBankExhausted(Exception):
    pass


class AssessmentAttemptNotFound(Exception):
    pass


class AssessmentAttemptAlreadySubmitted(Exception):
    pass


class InvalidAssessmentAnswer(Exception):
    pass


def _mc(
    question_id: str,
    concept_id: str,
    evidence_id: str,
    prompt: str,
    options: tuple[tuple[str, str], ...],
    answer_key: str,
    explanation: str,
) -> InternalMultipleChoiceQuestion:
    return InternalMultipleChoiceQuestion(
        public=PublicMultipleChoiceQuestion(
            kind="multiple_choice",
            question_id=question_id,
            concept_id=concept_id,
            evidence_id=evidence_id,
            prompt=prompt,
            difficulty="beginner",
            options=tuple(
                {"option_id": option_id, "label": label}
                for option_id, label in options
            ),
        ),
        answer_key=answer_key,
        explanation=explanation,
    )


def _matching() -> InternalMatchingQuestion:
    return InternalMatchingQuestion(
        public=PublicMatchingQuestion(
            kind="matching",
            question_id="german-a1-assess-match-greetings",
            concept_id="german-greetings",
            evidence_id="german-assessment-match-greetings",
            prompt="Match each expression to its meaning.",
            difficulty="beginner",
            left_items=(
                {"item_id": "hallo", "label": "Hallo"},
                {"item_id": "guten-tag", "label": "Guten Tag"},
                {"item_id": "auf-wiedersehen", "label": "Auf Wiedersehen"},
            ),
            right_items=(
                {"item_id": "hello", "label": "Hello"},
                {"item_id": "good-day", "label": "Good day / hello"},
                {"item_id": "goodbye", "label": "Goodbye"},
            ),
        ),
        answer_key=(
            MatchingAnswerPair(left_id="hallo", right_id="hello"),
            MatchingAnswerPair(left_id="guten-tag", right_id="good-day"),
            MatchingAnswerPair(left_id="auf-wiedersehen", right_id="goodbye"),
        ),
        explanation="Hallo means hello, Guten Tag is a polite daytime greeting, and Auf Wiedersehen means goodbye.",
    )


def _fill_blank(
    question_id: str,
    concept_id: str,
    evidence_id: str,
    prompt: str,
    sentence_template: str,
    accepted_answers: tuple[str, ...],
    explanation: str,
) -> InternalFillBlankQuestion:
    return InternalFillBlankQuestion(
        public=PublicFillBlankQuestion(
            kind="fill_blank",
            question_id=question_id,
            concept_id=concept_id,
            evidence_id=evidence_id,
            prompt=prompt,
            difficulty="beginner",
            sentence_template=sentence_template,
            blank_label="Missing word",
        ),
        accepted_answers=accepted_answers,
        normalization="unicode_nfc_trim_collapse_lower",
        explanation=explanation,
    )


# Fifteen distinct, fixed questions based only on the reviewed German A1 lesson.
# This bank intentionally contains one attempt set; a second non-overlapping set
# is not fabricated from paraphrases or runtime-generated material.
GERMAN_A1_ASSESSMENT_QUESTIONS: tuple[InternalAssessmentQuestion, ...] = (
    _mc(
        "german-a1-assess-greeting-morning",
        "german-greetings",
        "german-greetings-morning",
        "Which greeting is used in the morning?",
        (("a", "Guten Morgen"), ("b", "Guten Abend"), ("c", "Tschüss")),
        "a",
        "Guten Morgen is the morning greeting.",
    ),
    _mc(
        "german-a1-assess-greeting-evening",
        "german-greetings",
        "german-greetings-evening",
        "Which greeting fits the evening?",
        (("a", "Guten Tag"), ("b", "Guten Abend"), ("c", "Auf Wiedersehen")),
        "b",
        "Guten Abend is used in the evening.",
    ),
    _mc(
        "german-a1-assess-greeting-daytime",
        "german-greetings",
        "german-greetings-daytime",
        "Which is a polite daytime greeting?",
        (("a", "Guten Tag"), ("b", "Tschüss"), ("c", "Danke")),
        "a",
        "Guten Tag is a useful polite daytime greeting.",
    ),
    _mc(
        "german-a1-assess-informal-opening",
        "german-greetings",
        "german-greetings-informal-opening",
        "You meet a friend for the first time. Which relaxed greeting fits?",
        (("a", "Auf Wiedersehen"), ("b", "Hallo"), ("c", "Guten Abend")),
        "b",
        "Hallo is relaxed and widely understood in an informal exchange.",
    ),
    _mc(
        "german-a1-assess-informal-goodbye",
        "german-greetings",
        "german-informal-goodbye",
        "You are saying goodbye to a friend and will meet tomorrow. Which phrase fits?",
        (("a", "Tschüss, bis morgen!"), ("b", "Guten Morgen!"), ("c", "Wie heißen Sie?")),
        "a",
        "Tschüss is informal, and bis morgen means see you tomorrow.",
    ),
    _matching(),
    _mc(
        "german-a1-assess-polite-goodbye",
        "german-greetings",
        "german-formal-goodbye",
        "Which goodbye is the polite choice when leaving Frau Weber?",
        (("a", "Tschüss, Frau Weber!"), ("b", "Auf Wiedersehen, Frau Weber."), ("c", "Hallo, Frau Weber.")),
        "b",
        "Auf Wiedersehen is a polite goodbye.",
    ),
    _fill_blank(
        "german-a1-assess-name-verb",
        "german-self-introduction",
        "german-name-verb-introduction",
        "Complete the sentence used to give your name.",
        "Ich ___ Ada.",
        ("heiße", "heisse"),
        "Use ich heiße followed by your name. The reviewed spelling variant heisse is accepted.",
    ),
    _mc(
        "german-a1-assess-name-meaning",
        "german-self-introduction",
        "german-name-introduction",
        "Which phrase means ‘My name is Ada’?",
        (("a", "Ich heiße Ada."), ("b", "Wie heißt du?"), ("c", "Gut, danke.")),
        "a",
        "Ich heiße Ada means ‘My name is Ada.’",
    ),
    _mc(
        "german-a1-assess-informal-name-question",
        "german-self-introduction",
        "german-informal-name-question",
        "How do you ask a friend what their name is?",
        (("a", "Wie heißen Sie?"), ("b", "Wie heißt du?"), ("c", "Wie geht es Ihnen?")),
        "b",
        "Wie heißt du? is the informal question for someone’s name.",
    ),
    _mc(
        "german-a1-assess-formal-name-question",
        "german-formal-address",
        "german-formal-name-question",
        "Which question uses formal address to ask a person’s name?",
        (("a", "Wie heißt du?"), ("b", "Wie heißen Sie?"), ("c", "Und dir?")),
        "b",
        "Formal Sie pairs with heißen in Wie heißen Sie?",
    ),
    _mc(
        "german-a1-assess-du-conjugation",
        "german-formal-address",
        "german-du-conjugation",
        "Correct the informal question ‘Wie heißen du?’",
        (("a", "Wie heißt du?"), ("b", "Wie heißen Sie?"), ("c", "Wie geht es dir?")),
        "a",
        "With du, heißen changes to heißt: Wie heißt du?",
    ),
    _mc(
        "german-a1-assess-informal-wellbeing",
        "german-wie-gehts",
        "german-informal-wellbeing-question",
        "Which question asks an informal person how they are?",
        (("a", "Wie geht es dir?"), ("b", "Wie geht es Ihnen?"), ("c", "Wie heißen Sie?")),
        "a",
        "Use dir in the informal question Wie geht es dir?",
    ),
    _mc(
        "german-a1-assess-formal-wellbeing",
        "german-wie-gehts",
        "german-formal-wellbeing-question",
        "Which question asks formally how someone is?",
        (("a", "Wie heißt du?"), ("b", "Wie geht es Ihnen?"), ("c", "Und dir?")),
        "b",
        "Use Ihnen in the formal question Wie geht es Ihnen?",
    ),
    _fill_blank(
        "german-a1-assess-wellbeing-answer",
        "german-wie-gehts",
        "german-wellbeing-answer",
        "Complete a brief answer to ‘Wie geht es dir?’",
        "Gut, ___.",
        ("danke",),
        "Gut, danke is a common short response.",
    ),
)


def _question_id(question: InternalAssessmentQuestion) -> str:
    return question.public.question_id


def _to_public_attempt(attempt: StoredAssessmentAttempt) -> PublicAssessmentAttempt:
    return PublicAssessmentAttempt(
        attempt_id=attempt.attempt_id,
        lesson_id=attempt.lesson_id,
        bank_version=attempt.bank_version,
        question_count=ASSESSMENT_QUESTION_COUNT,
        questions=tuple(question.public for question in attempt.questions),
    )


def create_assessment_attempt(
    lesson_id: str, excluded_question_ids: tuple[str, ...] = ()
) -> PublicAssessmentAttempt:
    lesson: LessonDetail | None = get_lesson(lesson_id)
    if lesson is None:
        raise AssessmentAttemptNotFound

    with _ATTEMPT_LOCK:
        already_issued = {
            _question_id(question)
            for prior in _ATTEMPTS.values()
            if prior.lesson_id == lesson_id
            for question in prior.questions
        }
        excluded = already_issued | set(excluded_question_ids)
        eligible = tuple(
            question
            for question in GERMAN_A1_ASSESSMENT_QUESTIONS
            if _question_id(question) not in excluded
        )
        if len(eligible) < ASSESSMENT_QUESTION_COUNT:
            raise AssessmentBankExhausted

        questions = eligible[:ASSESSMENT_QUESTION_COUNT]
        attempt = StoredAssessmentAttempt(
            attempt_id=str(uuid4()),
            lesson_id=lesson_id,
            bank_version=ASSESSMENT_BANK_VERSION,
            questions=questions,
        )
        _ATTEMPTS[attempt.attempt_id] = attempt
        return _to_public_attempt(attempt)


def _normalize_fill_blank(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.split()).lower()


def _canonical_value(
    question: InternalAssessmentQuestion, answer: AssessmentAnswer
) -> str:
    value = answer.value
    if isinstance(question, InternalMultipleChoiceQuestion):
        if not isinstance(value, str):
            raise InvalidAssessmentAnswer("This question expects one option ID.")
        option_ids = {option.option_id for option in question.public.options}
        if value not in option_ids:
            raise InvalidAssessmentAnswer("The selected option is not part of this question.")
        canonical: object = value
    elif isinstance(question, InternalMatchingQuestion):
        if isinstance(value, str):
            raise InvalidAssessmentAnswer("This question expects matching pairs.")
        left_ids = {item.item_id for item in question.public.left_items}
        right_ids = {item.item_id for item in question.public.right_items}
        submitted_left = [pair.left_id for pair in value]
        if (
            len(value) != len(question.answer_key)
            or set(submitted_left) != left_ids
            or len(set(submitted_left)) != len(submitted_left)
            or not {pair.right_id for pair in value} <= right_ids
        ):
            raise InvalidAssessmentAnswer("Provide one valid match for every item.")
        canonical = sorted((pair.left_id, pair.right_id) for pair in value)
    else:
        if not isinstance(value, str):
            raise InvalidAssessmentAnswer("This question expects a text answer.")
        canonical = _normalize_fill_blank(value)
    return json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))


def _correct_answer(
    question: InternalAssessmentQuestion,
) -> str | tuple[MatchingAnswerPair, ...]:
    if isinstance(question, InternalMultipleChoiceQuestion):
        return next(
            option.label
            for option in question.public.options
            if option.option_id == question.answer_key
        )
    if isinstance(question, InternalMatchingQuestion):
        return question.answer_key
    return question.accepted_answers[0]


def _score_percent(correct: int, total: int) -> Decimal:
    return (Decimal(correct) * Decimal("100") / Decimal(total)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _grade(
    attempt: StoredAssessmentAttempt,
    answers_by_id: dict[str, AssessmentAnswer],
    canonical_by_id: dict[str, str],
) -> AssessmentResult:
    correct_by_concept: dict[str, int] = {}
    count_by_concept: dict[str, int] = {}
    review: list[AssessmentQuestionReview] = []
    correct_count = 0

    for question in attempt.questions:
        question_id = _question_id(question)
        answer = answers_by_id[question_id]
        canonical = canonical_by_id[question_id]
        if isinstance(question, InternalMultipleChoiceQuestion):
            correct = answer.value == question.answer_key
        elif isinstance(question, InternalMatchingQuestion):
            correct = canonical == json.dumps(
                sorted((pair.left_id, pair.right_id) for pair in question.answer_key),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            accepted = {_normalize_fill_blank(value) for value in question.accepted_answers}
            correct = json.loads(canonical) in accepted

        concept_id = question.public.concept_id
        count_by_concept[concept_id] = count_by_concept.get(concept_id, 0) + 1
        correct_by_concept[concept_id] = correct_by_concept.get(concept_id, 0) + int(correct)
        correct_count += int(correct)
        review.append(
            AssessmentQuestionReview(
                question_id=question_id,
                correct=correct,
                correct_answer=_correct_answer(question),
                explanation=question.explanation,
            )
        )

    concept_results = tuple(
        AssessmentConceptResult(
            concept_id=concept_id,
            correct_count=correct_by_concept.get(concept_id, 0),
            total_questions=total,
            score_percent=float(_score_percent(correct_by_concept.get(concept_id, 0), total)),
            weak=_score_percent(correct_by_concept.get(concept_id, 0), total)
            < WEAK_CONCEPT_THRESHOLD_PERCENT,
        )
        for concept_id, total in count_by_concept.items()
    )
    percent = _score_percent(correct_count, len(attempt.questions))
    weak_concepts = tuple(
        item.concept_id for item in concept_results if item.weak
    )
    return AssessmentResult(
        attempt_id=attempt.attempt_id,
        lesson_id=attempt.lesson_id,
        correct_count=correct_count,
        total_questions=ASSESSMENT_QUESTION_COUNT,
        score_percent=float(percent),
        mastery_threshold_percent=float(MASTERY_THRESHOLD_PERCENT),
        mastery_achieved=percent >= MASTERY_THRESHOLD_PERCENT,
        concept_results=concept_results,
        weak_concepts=weak_concepts,
        review=tuple(review),
    )


def submit_assessment(
    lesson_id: str, attempt_id: str, answers: tuple[AssessmentAnswer, ...]
) -> AssessmentResult:
    with _ATTEMPT_LOCK:
        attempt = _ATTEMPTS.get(attempt_id)
        if attempt is None or attempt.lesson_id != lesson_id:
            raise AssessmentAttemptNotFound

        expected_ids = {_question_id(question) for question in attempt.questions}
        submitted_ids = [answer.question_id for answer in answers]
        if (
            len(submitted_ids) != ASSESSMENT_QUESTION_COUNT
            or len(set(submitted_ids)) != len(submitted_ids)
            or set(submitted_ids) != expected_ids
        ):
            raise InvalidAssessmentAnswer(
                "Submit exactly one answer for each question in this attempt."
            )

        questions_by_id = {
            _question_id(question): question for question in attempt.questions
        }
        answers_by_id = {answer.question_id: answer for answer in answers}
        canonical_by_id = {
            answer.question_id: _canonical_value(
                questions_by_id[answer.question_id], answer
            )
            for answer in answers
        }
        canonical_submission = json.dumps(
            canonical_by_id, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

        if attempt.result is not None:
            if canonical_submission != attempt.canonical_submission:
                raise AssessmentAttemptAlreadySubmitted
            return attempt.result

        result = _grade(attempt, answers_by_id, canonical_by_id)
        _ATTEMPTS[attempt_id] = attempt.model_copy(
            update={"canonical_submission": canonical_submission, "result": result}
        )
        return result


def clear_assessment_attempts() -> None:
    """Reset ephemeral state for isolated tests; never called by request handling."""
    with _ATTEMPT_LOCK:
        _ATTEMPTS.clear()
