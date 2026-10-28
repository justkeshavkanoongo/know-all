from decimal import Decimal
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StrictStr

from .models import ApiModel
from .practice_models import MatchingAnswerPair

ASSESSMENT_QUESTION_COUNT = 15
MASTERY_THRESHOLD_PERCENT = Decimal("80.00")
WEAK_CONCEPT_THRESHOLD_PERCENT = Decimal("80.00")


class AssessmentOption(ApiModel):
    option_id: str
    label: str


class AssessmentMatchingItem(ApiModel):
    item_id: str
    label: str


class AssessmentQuestionBase(ApiModel):
    question_id: str
    concept_id: str
    evidence_id: str
    prompt: str
    difficulty: Literal["beginner", "elementary", "intermediate", "advanced"]


class PublicMultipleChoiceQuestion(AssessmentQuestionBase):
    kind: Literal["multiple_choice"]
    options: tuple[AssessmentOption, ...]


class PublicMatchingQuestion(AssessmentQuestionBase):
    kind: Literal["matching"]
    left_items: tuple[AssessmentMatchingItem, ...]
    right_items: tuple[AssessmentMatchingItem, ...]


class PublicFillBlankQuestion(AssessmentQuestionBase):
    kind: Literal["fill_blank"]
    sentence_template: str
    blank_label: str


PublicAssessmentQuestion = Annotated[
    PublicMultipleChoiceQuestion | PublicMatchingQuestion | PublicFillBlankQuestion,
    Field(discriminator="kind"),
]


class AssessmentAttemptRequest(ApiModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    exclude_question_ids: tuple[Annotated[StrictStr, Field(min_length=1, max_length=120)], ...] = Field(
        default=(), max_length=100
    )


class PublicAssessmentAttempt(ApiModel):
    attempt_id: str
    lesson_id: str
    bank_version: str
    question_count: Literal[15]
    questions: tuple[PublicAssessmentQuestion, ...]


AssessmentAnswerValue = Annotated[
    StrictStr | Annotated[tuple[MatchingAnswerPair, ...], Field(max_length=50)],
    Field(union_mode="left_to_right"),
]


class AssessmentAnswer(ApiModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    value: Annotated[AssessmentAnswerValue, Field(max_length=500)]


class AssessmentSubmitRequest(ApiModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    answers: tuple[AssessmentAnswer, ...] = Field(min_length=1, max_length=15)


class AssessmentConceptResult(ApiModel):
    concept_id: str
    correct_count: int
    total_questions: int
    score_percent: float
    weak: bool


class AssessmentQuestionReview(ApiModel):
    question_id: str
    correct: bool
    correct_answer: StrictStr | tuple[MatchingAnswerPair, ...]
    explanation: str


class AssessmentResult(ApiModel):
    attempt_id: str
    lesson_id: str
    correct_count: int
    total_questions: Literal[15]
    score_percent: float
    mastery_threshold_percent: float
    mastery_achieved: bool
    concept_results: tuple[AssessmentConceptResult, ...]
    weak_concepts: tuple[str, ...]
    review: tuple[AssessmentQuestionReview, ...]


class InternalMultipleChoiceQuestion(ApiModel):
    public: PublicMultipleChoiceQuestion
    answer_key: str
    explanation: str


class InternalMatchingQuestion(ApiModel):
    public: PublicMatchingQuestion
    answer_key: tuple[MatchingAnswerPair, ...]
    explanation: str


class InternalFillBlankQuestion(ApiModel):
    public: PublicFillBlankQuestion
    accepted_answers: tuple[str, ...]
    normalization: Literal["unicode_nfc_trim_collapse_lower"]
    explanation: str


InternalAssessmentQuestion = (
    InternalMultipleChoiceQuestion
    | InternalMatchingQuestion
    | InternalFillBlankQuestion
)


class StoredAssessmentAttempt(ApiModel):
    attempt_id: str
    lesson_id: str
    bank_version: str
    questions: tuple[InternalAssessmentQuestion, ...]
    canonical_submission: str | None = None
    result: AssessmentResult | None = None
