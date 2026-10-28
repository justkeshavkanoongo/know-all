from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StrictStr

from .models import ApiModel

Difficulty = Literal["beginner", "elementary", "intermediate", "advanced"]


class ExerciseOption(ApiModel):
    option_id: str
    label: str


class MatchingItem(ApiModel):
    item_id: str
    label: str


class PublicExerciseBase(ApiModel):
    exercise_id: str
    lesson_id: str
    version: str
    concept_id: str
    evidence_id: str
    difficulty: Difficulty
    prompt: str


class PublicMultipleChoiceExercise(PublicExerciseBase):
    kind: Literal["multiple_choice"]
    options: tuple[ExerciseOption, ...]


class PublicMatchingExercise(PublicExerciseBase):
    kind: Literal["matching"]
    left_items: tuple[MatchingItem, ...]
    right_items: tuple[MatchingItem, ...]


class PublicFillBlankExercise(PublicExerciseBase):
    kind: Literal["fill_blank"]
    sentence_template: str
    blank_label: str


PublicExercise = Annotated[
    PublicMultipleChoiceExercise | PublicMatchingExercise | PublicFillBlankExercise,
    Field(discriminator="kind"),
]


class PracticeSet(ApiModel):
    lesson_id: str
    exercise_set_id: str
    version: str
    exercises: tuple[PublicExercise, ...]


class MatchingAnswerPair(ApiModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    left_id: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    right_id: Annotated[StrictStr, Field(min_length=1, max_length=120)]


PracticeAnswer = Annotated[
    StrictStr | Annotated[tuple[MatchingAnswerPair, ...], Field(max_length=50)],
    Field(union_mode="left_to_right"),
]


class PracticeCheckRequest(ApiModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    exercise_id: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    answer: Annotated[PracticeAnswer, Field(max_length=500)]


class PracticeCheckResponse(ApiModel):
    correct: bool
    feedback: str
    concept_id: str


class InternalMultipleChoiceAnswer(ApiModel):
    exercise: PublicMultipleChoiceExercise
    answer_key: str
    correct_feedback: str
    incorrect_feedback: str


class InternalMatchingAnswer(ApiModel):
    exercise: PublicMatchingExercise
    answer_key: tuple[MatchingAnswerPair, ...]
    correct_feedback: str
    incorrect_feedback: str


class InternalFillBlankAnswer(ApiModel):
    exercise: PublicFillBlankExercise
    accepted_answers: tuple[str, ...]
    normalization: Literal["unicode_nfc_trim_collapse_lower"]
    correct_feedback: str
    incorrect_feedback: str


InternalExercise = (
    InternalMultipleChoiceAnswer | InternalMatchingAnswer | InternalFillBlankAnswer
)
