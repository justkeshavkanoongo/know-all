from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import ReviewableRevisionConflict


class QuestRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GuestSessionCreate(QuestRequestModel):
    confirm_adult: Literal[True]


class QuestCreate(QuestRequestModel):
    lesson_id: Literal["german-a1-greetings"]
    concept_ids: list[Literal["german-greetings"]] = Field(min_length=1, max_length=1)
    template_id: Literal["concept-guide-v1"]


class InvitationRedeem(QuestRequestModel):
    token: str = Field(min_length=30, max_length=200)
    confirm_adult: Literal[True]


class GuestSessionResponse(BaseModel):
    identity_id: UUID
    expires_at: datetime


class QuestResponse(BaseModel):
    quest_id: UUID
    state: Literal["awaiting_partner", "preparing", "collaborating", "cancelled", "expired"]
    lesson_id: str
    concept_ids: list[str]
    template_id: str
    participant_count: int
    allowed_actions: list[Literal["view", "invite", "prepare", "edit_artifact", "review"]]
    created_at: datetime
    expires_at: datetime
    version: int


class InvitationResponse(BaseModel):
    invitation_token: str | None
    expires_at: datetime
    status: Literal["issued", "already_issued"]


class ErrorResponse(BaseModel):
    code: str
    message: str
    current_revision: int | None = None
    current_reviewable_revision: ReviewableRevisionConflict | None = None


class PreparationMemberStatus(BaseModel):
    role: Literal["host", "collaborator"]
    checked_count: int = Field(ge=0, le=7)
    evidence_ids: list[str]
    required_count: Literal[7] = 7
    complete: bool


class PreparationStatus(BaseModel):
    quest_id: UUID
    current_role: Literal["host", "collaborator"]
    state: Literal["awaiting_partner", "preparing", "collaborating", "expired", "cancelled"]
    members: list[PreparationMemberStatus]


class PreparationCheckResponse(BaseModel):
    quest_id: UUID
    exercise_id: str
    evidence_id: str
    correct: bool
    feedback: str
    member_checked_count: int = Field(ge=0, le=7)
    required_count: Literal[7] = 7
    member_complete: bool
    quest_state: Literal["preparing", "collaborating"]


class MisconceptionCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    misconception: str = Field(max_length=1200)
    correction: str = Field(max_length=1200)


ArtifactSection = Literal["explanation", "example", "misconception_correction", "follow_up_question"]


class ArtifactSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    explanation: str = Field(max_length=2000)
    example: str = Field(max_length=2000)
    misconception_correction: MisconceptionCorrection
    follow_up_question: str = Field(max_length=1000)

    @model_validator(mode="after")
    def check_total_content(self):
        total = len(self.explanation) + len(self.example) + len(self.misconception_correction.misconception) + len(self.misconception_correction.correction) + len(self.follow_up_question)
        if total > 5000:
            raise ValueError("Artifact content must not exceed 5000 characters in total.")
        return self


class ArtifactSectionUpdate(QuestRequestModel):
    expected_revision: int = Field(ge=0)
    content: Annotated[
        Annotated[str, Field(max_length=2000)] | MisconceptionCorrection,
        Field(union_mode="left_to_right"),
    ]


class ArtifactRevisionResponse(BaseModel):
    revision_id: UUID
    revision_number: int
    changed_section: ArtifactSection | None
    author_role: Literal["host", "collaborator", "system"]
    created_at: datetime
    snapshot: ArtifactSnapshot


class ArtifactResponse(BaseModel):
    quest_id: UUID
    current_revision: int
    snapshot: ArtifactSnapshot
    revisions: list[ArtifactRevisionResponse]
    history_truncated: bool


ReviewRating = Literal["needs_work", "mostly_there", "clear"]


class PeerReviewRequest(QuestRequestModel):
    revision_id: UUID
    rubric_version: Literal["peer-review-v1"] = "peer-review-v1"
    conceptual_correctness: ReviewRating
    explanation_clarity: ReviewRating
    example_relevance: ReviewRating
    misconception_correction: ReviewRating
    follow_up_usefulness: ReviewRating
    strength: str = Field(min_length=1, max_length=500)
    improvement_suggestion: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=500)

    @field_validator("strength", "improvement_suggestion", "rationale")
    @classmethod
    def require_non_whitespace_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Feedback text must contain non-whitespace characters.")
        return value

    @model_validator(mode="after")
    def check_total_written_feedback(self):
        if len(self.strength) + len(self.improvement_suggestion) + len(self.rationale) > 1500:
            raise ValueError("Review text must not exceed 1500 characters in total.")
        return self


class ReviewRevisionSummary(BaseModel):
    revision_id: UUID
    revision_number: int
    author_role: Literal["host", "collaborator"]
    created_at: datetime
    snapshot: ArtifactSnapshot


class PeerReviewResponse(BaseModel):
    review_id: UUID
    review_round: Literal[1] = 1
    revision_id: UUID
    revision_number: int
    revision_is_current: bool
    snapshot: ArtifactSnapshot
    reviewer_role: Literal["host", "collaborator"]
    recipient_role: Literal["host", "collaborator"]
    rubric_version: Literal["peer-review-v1"]
    conceptual_correctness: ReviewRating
    explanation_clarity: ReviewRating
    example_relevance: ReviewRating
    misconception_correction: ReviewRating
    follow_up_usefulness: ReviewRating
    strength: str
    improvement_suggestion: str
    rationale: str
    created_at: datetime
    acknowledged_at: datetime | None = None
    response_text: str | None = None
    responded_at: datetime | None = None


class QuestReviewStatus(BaseModel):
    quest_id: UUID
    current_role: Literal["host", "collaborator"]
    state: Literal["awaiting_partner", "preparing", "collaborating", "expired", "cancelled"]
    eligible: bool
    submitted_by_you: bool
    submitted_by_partner: bool
    reviewable_revision: ReviewRevisionSummary | None = None
    review_given: PeerReviewResponse | None = None
    review_received: PeerReviewResponse | None = None


class ReviewAcknowledgementRequest(QuestRequestModel):
    pass


class ReviewResponseRequest(QuestRequestModel):
    response: str = Field(min_length=1, max_length=500)

    @field_validator("response")
    @classmethod
    def require_non_whitespace_response(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Response must contain non-whitespace characters.")
        return value


class ReviewRecipientResponse(BaseModel):
    review_id: UUID
    acknowledged_at: datetime
    response_text: str | None = None
    responded_at: datetime | None = None
