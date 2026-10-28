import unicodedata

from .practice_models import (
    Difficulty,
    InternalExercise,
    InternalFillBlankAnswer,
    InternalMatchingAnswer,
    InternalMultipleChoiceAnswer,
    MatchingAnswerPair,
    PracticeAnswer,
    PracticeCheckResponse,
    PracticeSet,
    PublicFillBlankExercise,
    PublicMatchingExercise,
    PublicMultipleChoiceExercise,
)

LESSON_ID = "german-a1-greetings"
EXERCISE_SET_ID = "german-a1-greetings-practice"
EXERCISE_SET_VERSION = "1.0.0"


class IncompatiblePracticeAnswer(Exception):
    pass


def _mc(
    exercise_id: str,
    concept_id: str,
    evidence_id: str,
    prompt: str,
    options: tuple[tuple[str, str], ...],
    answer_key: str,
    correct_feedback: str,
    incorrect_feedback: str,
    difficulty: Difficulty = "beginner",
) -> InternalMultipleChoiceAnswer:
    return InternalMultipleChoiceAnswer(
        exercise=PublicMultipleChoiceExercise(
            kind="multiple_choice",
            exercise_id=exercise_id,
            lesson_id=LESSON_ID,
            version="1.0.0",
            concept_id=concept_id,
            evidence_id=evidence_id,
            difficulty=difficulty,
            prompt=prompt,
            options=tuple({"option_id": option_id, "label": label} for option_id, label in options),
        ),
        answer_key=answer_key,
        correct_feedback=correct_feedback,
        incorrect_feedback=incorrect_feedback,
    )


def _matching() -> InternalMatchingAnswer:
    return InternalMatchingAnswer(
        exercise=PublicMatchingExercise(
            kind="matching",
            exercise_id="german-a1-match-greetings",
            lesson_id=LESSON_ID,
            version="1.0.0",
            concept_id="german-greetings",
            evidence_id="german-greetings-match-practice",
            difficulty="beginner",
            prompt="Match each German greeting to its English meaning.",
            left_items=(
                {"item_id": "guten-morgen", "label": "Guten Morgen"},
                {"item_id": "guten-tag", "label": "Guten Tag"},
                {"item_id": "tschuss", "label": "Tschüss"},
            ),
            right_items=(
                {"item_id": "good-morning", "label": "Good morning"},
                {"item_id": "good-day", "label": "Good day / hello"},
                {"item_id": "bye", "label": "Bye"},
            ),
        ),
        answer_key=(
            MatchingAnswerPair(left_id="guten-morgen", right_id="good-morning"),
            MatchingAnswerPair(left_id="guten-tag", right_id="good-day"),
            MatchingAnswerPair(left_id="tschuss", right_id="bye"),
        ),
        correct_feedback="Correct. These greetings match their reviewed translations.",
        incorrect_feedback="Not quite. Guten Morgen means good morning, Guten Tag means good day, and Tschüss means bye.",
    )


def _fill_blank(
    exercise_id: str,
    concept_id: str,
    evidence_id: str,
    prompt: str,
    sentence_template: str,
    accepted_answers: tuple[str, ...],
    correct_feedback: str,
    incorrect_feedback: str,
) -> InternalFillBlankAnswer:
    return InternalFillBlankAnswer(
        exercise=PublicFillBlankExercise(
            kind="fill_blank",
            exercise_id=exercise_id,
            lesson_id=LESSON_ID,
            version="1.0.0",
            concept_id=concept_id,
            evidence_id=evidence_id,
            difficulty="beginner",
            prompt=prompt,
            sentence_template=sentence_template,
            blank_label="Missing word",
        ),
        accepted_answers=accepted_answers,
        normalization="unicode_nfc_trim_collapse_lower",
        correct_feedback=correct_feedback,
        incorrect_feedback=incorrect_feedback,
    )


# Reviewed, stable exercise content. Retrieval and evaluation share these
# records, but only each record's explicit public model is returned by the API.
EXERCISES_BY_LESSON: dict[str, tuple[InternalExercise, ...]] = {
    LESSON_ID: (
        _mc(
            "german-a1-greeting-time",
            "german-greetings",
            "german-greetings-morning",
            "Which greeting is a natural choice in the morning?",
            (("option-a", "Guten Morgen"), ("option-b", "Guten Abend"), ("option-c", "Tschüss")),
            "option-a",
            "Correct. Guten Morgen is the morning greeting.",
            "Not quite. Guten Morgen is used in the morning; Guten Abend is for the evening.",
        ),
        _mc(
            "german-a1-introduce-name",
            "german-self-introduction",
            "german-name-introduction",
            "Choose the phrase that means ‘My name is Ada.’",
            (("option-a", "Ich heiße Ada."), ("option-b", "Wie geht es Ada?"), ("option-c", "Guten Tag, Ada.")),
            "option-a",
            "Correct. Ich heiße Ada means ‘My name is Ada.’",
            "Not quite. Use Ich heiße followed by the name to introduce yourself.",
        ),
        _mc(
            "german-a1-formal-name-question",
            "german-formal-address",
            "german-formal-name-question",
            "Which question uses formal address?",
            (("option-a", "Wie heißt du?"), ("option-b", "Wie heißen Sie?"), ("option-c", "Wie geht es dir?")),
            "option-b",
            "Correct. Sie is the formal form of address and uses heißen here.",
            "Not quite. Wie heißen Sie? is the formal question for someone’s name.",
        ),
        _matching(),
        _fill_blank(
            "german-a1-fill-name-verb",
            "german-self-introduction",
            "german-name-verb-introduction",
            "Complete the sentence with the verb form for ‘I am called’.",
            "Ich ___ Ada.",
            ("heiße", "heisse"),
            "Correct. Ich heiße Ada means ‘My name is Ada.’ The reviewed spelling variant heisse is also accepted.",
            "Not quite. The sentence is Ich heiße Ada.",
        ),
        _fill_blank(
            "german-a1-fill-formal-verb",
            "german-formal-address",
            "german-formal-name-verb",
            "Complete the formal question with the correct form of heißen.",
            "Wie ___ Sie?",
            ("heißen", "heissen"),
            "Correct. Formal Sie pairs with heißen in this question.",
            "Not quite. The formal question is Wie heißen Sie?",
        ),
        _fill_blank(
            "german-a1-fill-goodbye",
            "german-greetings",
            "german-informal-goodbye",
            "Complete the informal goodbye.",
            "___, bis morgen!",
            ("Tschüss",),
            "Correct. Tschüss is an informal way to say goodbye.",
            "Not quite. The informal goodbye is Tschüss, bis morgen!",
        ),
    ),
}


def get_practice_set(lesson_id: str) -> PracticeSet | None:
    exercises = EXERCISES_BY_LESSON.get(lesson_id)
    if exercises is None:
        return None

    public_exercises = tuple(item.exercise for item in exercises)
    return PracticeSet(
        lesson_id=lesson_id,
        exercise_set_id=EXERCISE_SET_ID,
        version=EXERCISE_SET_VERSION,
        exercises=public_exercises,
    )


def _normalize_fill_blank(answer: str) -> str:
    normalized = unicodedata.normalize("NFC", answer)
    return " ".join(normalized.split()).lower()


def check_practice_answer(
    lesson_id: str, exercise_id: str, answer: PracticeAnswer
) -> PracticeCheckResponse | None:
    for exercise in EXERCISES_BY_LESSON.get(lesson_id, ()):
        public = exercise.exercise
        if public.exercise_id != exercise_id:
            continue

        if isinstance(exercise, InternalMultipleChoiceAnswer):
            if not isinstance(answer, str):
                raise IncompatiblePracticeAnswer("This exercise expects one option ID.")
            option_ids = {option.option_id for option in public.options}
            if answer not in option_ids:
                raise ValueError("The selected option is not part of this exercise.")
            correct = answer == exercise.answer_key
        elif isinstance(exercise, InternalMatchingAnswer):
            if isinstance(answer, str):
                raise IncompatiblePracticeAnswer("This exercise expects a list of matching pairs.")
            left_ids = {item.item_id for item in public.left_items}
            right_ids = {item.item_id for item in public.right_items}
            left_answers = [pair.left_id for pair in answer]
            right_answers = [pair.right_id for pair in answer]
            if (
                len(answer) != len(exercise.answer_key)
                or set(left_answers) != left_ids
                or len(set(left_answers)) != len(left_answers)
                or not set(right_answers) <= right_ids
            ):
                raise ValueError("Provide one valid match for every item.")
            correct = {(pair.left_id, pair.right_id) for pair in answer} == {
                (pair.left_id, pair.right_id) for pair in exercise.answer_key
            }
        else:
            if not isinstance(answer, str):
                raise IncompatiblePracticeAnswer("This exercise expects a text answer.")
            accepted = {_normalize_fill_blank(value) for value in exercise.accepted_answers}
            correct = _normalize_fill_blank(answer) in accepted

        return PracticeCheckResponse(
            correct=correct,
            feedback=exercise.correct_feedback if correct else exercise.incorrect_feedback,
            concept_id=public.concept_id,
        )
    return None
