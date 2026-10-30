"""PostgreSQL-backed guest identity and pair-quest foundation."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db_session
from .practice import IncompatiblePracticeAnswer, check_practice_answer, get_practice_set
from .practice_models import PracticeCheckRequest
from .quest_models import (
    ArtifactResponse, ArtifactRevisionResponse, ArtifactSection, ArtifactSectionUpdate,
    ArtifactSnapshot, ErrorResponse, GuestSessionCreate, GuestSessionResponse, MisconceptionCorrection,
    InvitationRedeem, InvitationResponse, PeerReviewRequest, PeerReviewResponse,
    PreparationCheckResponse, PreparationMemberStatus, PreparationStatus, QuestCreate,
    QuestResponse, QuestReviewStatus, ReviewAcknowledgementRequest,
    ReviewRecipientResponse, ReviewResponseRequest, ReviewRevisionSummary,
)
from .quest_tables import (
    GuestIdentity, GuestSession, IdempotencyRecord, Invitation, Quest,
    QuestArtifact, QuestArtifactRevision, QuestArtifactReview,
    QuestArtifactReviewResponse, QuestParticipant, QuestPreparationEvidence,
)

router = APIRouter(prefix="/api", tags=["guest quests"])
COOKIE_NAME = "know_all_guest"
SESSION_DAYS = 30
INVITATION_HOURS = int(os.environ.get("QUEST_INVITATION_TTL_HOURS", "72"))
QUEST_DAYS = int(os.environ.get("QUEST_TTL_DAYS", "30"))
REDEEM_RETRY_SECONDS = 120
if INVITATION_HOURS < 1 or QUEST_DAYS < 1:
    raise ValueError("Quest and invitation expiry settings must be positive integers")


def now() -> datetime:
    return datetime.now(timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def require_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    expected = os.environ.get("WEB_ORIGIN", "http://localhost:3000").rstrip("/")
    if origin is None or origin.rstrip("/") != expected:
        raise error(403, "origin_not_allowed", "Request origin is not allowed.")


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    secure_cookie = os.environ.get("ENVIRONMENT", os.environ.get("NODE_ENV", "")).lower() in {"production", "prod"}
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", secure=secure_cookie,
        path="/", expires=expires_at.astimezone(timezone.utc),
    )


def create_session(db: Session, identity_id: UUID, token: str | None = None) -> tuple[str, GuestSession]:
    token = token or secrets.token_urlsafe(48)
    created = now()
    session = GuestSession(id=uuid4(), identity_id=identity_id, token_hash=digest(token), created_at=created,
                           expires_at=created + timedelta(days=SESSION_DAYS))
    db.add(session)
    return token, session


def authenticate(db: Session, token: str | None) -> tuple[GuestSession, GuestIdentity]:
    if not token:
        raise error(401, "guest_session_required", "A valid guest session is required.")
    record = db.scalar(select(GuestSession).where(GuestSession.token_hash == digest(token)))
    if record is None or record.revoked_at is not None or record.expires_at <= now():
        raise error(401, "guest_session_required", "A valid guest session is required.")
    identity = db.get(GuestIdentity, record.identity_id)
    if identity is None:
        raise error(401, "guest_session_required", "A valid guest session is required.")
    return record, identity


def quest_response(db: Session, quest: Quest) -> QuestResponse:
    count = db.scalar(select(func.count()).select_from(QuestParticipant).where(QuestParticipant.quest_id == quest.id)) or 0
    state = "expired" if quest.expires_at <= now() and quest.state in {"awaiting_partner", "preparing", "collaborating"} else quest.state
    actions = {
        "awaiting_partner": ["view", "invite"],
        "preparing": ["view", "prepare"],
        "collaborating": ["view", "edit_artifact", "review"],
    }.get(state, [])
    return QuestResponse(quest_id=quest.id, state=state, lesson_id=quest.lesson_id,
                         concept_ids=quest.concept_ids, template_id=quest.template_id, participant_count=count,
                         allowed_actions=actions,
                         created_at=quest.created_at, expires_at=quest.expires_at, version=quest.version)


def member(db: Session, quest_id: UUID, identity_id: UUID, *, host_only: bool = False) -> tuple[Quest, QuestParticipant]:
    quest = db.get(Quest, quest_id)
    membership = db.get(QuestParticipant, (quest_id, identity_id))
    if quest is None or membership is None:
        raise error(404, "quest_not_found", "Quest was not found.")
    if host_only and membership.role != "host":
        raise error(404, "quest_not_found", "Quest was not found.")
    return quest, membership


@router.post("/guest-sessions", response_model=GuestSessionResponse, responses={403: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def start_guest_session(payload: GuestSessionCreate, request: Request, response: Response,
                        db: Session = Depends(get_db_session)) -> GuestSessionResponse:
    require_origin(request)
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        try:
            active, identity = authenticate(db, existing)
            return GuestSessionResponse(identity_id=identity.id, expires_at=active.expires_at)
        except HTTPException:
            pass
    created = now()
    identity = GuestIdentity(id=uuid4(), adult_confirmed_at=created, created_at=created)
    db.add(identity)
    token, session = create_session(db, identity.id)
    db.add(session)
    db.commit()
    set_session_cookie(response, token, session.expires_at)
    return GuestSessionResponse(identity_id=identity.id, expires_at=session.expires_at)


@router.post("/guest-sessions/rotate", response_model=GuestSessionResponse, responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def rotate_guest_session(request: Request, response: Response, db: Session = Depends(get_db_session)) -> GuestSessionResponse:
    require_origin(request)
    current, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    token, replacement = create_session(db, identity.id)
    # Keep the old token valid for a short overlap so concurrent browser requests don't race rotation.
    current.expires_at = min(current.expires_at, now() + timedelta(minutes=2))
    db.add(replacement)
    db.commit()
    set_session_cookie(response, token, replacement.expires_at)
    return GuestSessionResponse(identity_id=identity.id, expires_at=replacement.expires_at)


@router.delete("/guest-sessions/current", status_code=204, responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def revoke_guest_session(request: Request, response: Response, db: Session = Depends(get_db_session)) -> Response:
    require_origin(request)
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    db.execute(update(GuestSession).where(GuestSession.identity_id == identity.id,
        GuestSession.revoked_at.is_(None)).values(revoked_at=now()))
    db.commit()
    secure_cookie = os.environ.get("ENVIRONMENT", os.environ.get("NODE_ENV", "")).lower() in {"production", "prod"}
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=secure_cookie)
    response.status_code = 204
    return response


@router.post("/quests", response_model=QuestResponse, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def create_quest(payload: QuestCreate, request: Request, response: Response,
                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                 db: Session = Depends(get_db_session)) -> QuestResponse:
    require_origin(request)
    if not idempotency_key or len(idempotency_key) > 128:
        raise error(400, "idempotency_key_required", "A valid Idempotency-Key header is required.")
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    request_hash = digest(payload.model_dump_json())
    key_hash = digest(idempotency_key)
    existing = db.get(IdempotencyRecord, (identity.id, "create-quest", key_hash))
    if existing:
        if not hmac.compare_digest(existing.request_hash, request_hash):
            raise error(409, "idempotency_key_reused", "This idempotency key was used for a different request.")
        quest = db.get(Quest, existing.resource_id)
        if quest is None:
            raise error(409, "quest_unavailable", "The original quest is no longer available.")
        return quest_response(db, quest)
    created = now()
    quest = Quest(id=uuid4(), state="awaiting_partner", lesson_id=payload.lesson_id,
                  concept_ids=payload.concept_ids, template_id=payload.template_id, created_at=created,
                  expires_at=created + timedelta(days=QUEST_DAYS), version=1)
    db.add(quest)
    db.flush()
    db.add(QuestParticipant(quest_id=quest.id, identity_id=identity.id, role="host"))
    db.add(IdempotencyRecord(identity_id=identity.id, operation="create-quest", key_hash=key_hash,
                             request_hash=request_hash, resource_id=quest.id, created_at=created))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        prior_record = db.get(IdempotencyRecord, (identity.id, "create-quest", key_hash))
        if prior_record and hmac.compare_digest(prior_record.request_hash, request_hash):
            prior_quest = db.get(Quest, prior_record.resource_id)
            if prior_quest:
                return quest_response(db, prior_quest)
        raise error(409, "idempotency_conflict", "A matching request is already being processed; retry with the same key.") from exc
    return quest_response(db, quest)


@router.get("/quests/{quest_id}", response_model=QuestResponse, responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def get_quest(quest_id: UUID, request: Request, db: Session = Depends(get_db_session)) -> QuestResponse:
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, _ = member(db, quest_id, identity.id)
    return quest_response(db, quest)


@router.post("/quests/{quest_id}/invitations", response_model=InvitationResponse, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def issue_invitation(quest_id: UUID, request: Request,
                     idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                     db: Session = Depends(get_db_session)) -> InvitationResponse:
    require_origin(request)
    if not idempotency_key or len(idempotency_key) > 128:
        raise error(400, "idempotency_key_required", "A valid Idempotency-Key header is required.")
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, _ = member(db, quest_id, identity.id, host_only=True)
    quest = db.scalar(select(Quest).where(Quest.id == quest_id).with_for_update())
    assert quest is not None
    if quest.state != "awaiting_partner" or quest.expires_at <= now():
        raise error(409, "quest_not_invitable", "This quest cannot accept an invitation.")
    key_hash = digest(idempotency_key)
    existing = db.scalar(select(Invitation).where(Invitation.quest_id == quest.id,
        Invitation.retry_key_hash == key_hash))
    if existing:
        return InvitationResponse(invitation_token=None, expires_at=existing.expires_at, status="already_issued")
    active = db.scalar(select(Invitation).where(Invitation.quest_id == quest.id,
        Invitation.redeemed_at.is_(None), Invitation.revoked_at.is_(None)).with_for_update())
    if active:
        active.revoked_at = now()
    token = secrets.token_urlsafe(48)
    created = now()
    invitation = Invitation(id=uuid4(), quest_id=quest.id, token_hash=digest(token), created_at=created,
                            expires_at=min(quest.expires_at, created + timedelta(hours=INVITATION_HOURS)),
                            retry_key_hash=key_hash)
    db.add(invitation)
    db.commit()
    return InvitationResponse(invitation_token=token, expires_at=invitation.expires_at, status="issued")


@router.delete("/quests/{quest_id}/invitations", status_code=204, responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def revoke_invitation(quest_id: UUID, request: Request, db: Session = Depends(get_db_session)) -> Response:
    require_origin(request)
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, _ = member(db, quest_id, identity.id, host_only=True)
    active = db.scalar(select(Invitation).where(Invitation.quest_id == quest.id,
        Invitation.redeemed_at.is_(None), Invitation.revoked_at.is_(None)).with_for_update())
    if active:
        active.revoked_at = now()
        db.commit()
    return Response(status_code=204)


@router.post("/quest-invitations/redeem", response_model=QuestResponse, responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def redeem_invitation(payload: InvitationRedeem, request: Request, response: Response,
                      idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                      db: Session = Depends(get_db_session)) -> QuestResponse:
    require_origin(request)
    if not idempotency_key or len(idempotency_key) > 128:
        raise error(400, "idempotency_key_required", "A valid Idempotency-Key header is required.")
    invite_hash, key_hash = digest(payload.token), digest(idempotency_key)
    invite = db.scalar(select(Invitation).where(Invitation.token_hash == invite_hash))
    current = now()
    if invite is None:
        raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.")
    if invite.redeemed_at is not None:
        if (invite.retry_key_hash == key_hash and invite.retry_until and invite.retry_until > current
                and invite.retry_session_hash and invite.redeemed_by):
            # Token regeneration is only possible with the configured secret and original invite credential.
            secret = os.environ.get("QUEST_SESSION_SECRET", "")
            if len(secret) < 32:
                raise error(503, "quest_service_unavailable", "Guest session configuration is unavailable.")
            derived = hmac.new(secret.encode(), f"{invite.id}:{payload.token}:{idempotency_key}".encode(), hashlib.sha256).hexdigest()
            retry_token = derived
            if not hmac.compare_digest(digest(retry_token), invite.retry_session_hash):
                raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.")
            session = db.scalar(select(GuestSession).where(GuestSession.token_hash == invite.retry_session_hash))
            if session and session.expires_at > current and not session.revoked_at:
                quest = db.get(Quest, invite.quest_id)
                if quest is None:
                    raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.")
                set_session_cookie(response, retry_token, session.expires_at)
                return quest_response(db, quest)
        raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.")
    # Lock in a consistent quest -> invitation order, matching issuance/revocation and avoiding deadlocks.
    quest = db.scalar(select(Quest).where(Quest.id == invite.quest_id).with_for_update())
    invite = db.scalar(select(Invitation).where(Invitation.id == invite.id).with_for_update().execution_options(populate_existing=True))
    if invite is None or invite.revoked_at is not None or invite.redeemed_at is not None or invite.expires_at <= current:
        raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.")
    if quest is None or quest.expires_at <= current or quest.state != "awaiting_partner":
        raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.")
    count = db.scalar(select(func.count()).select_from(QuestParticipant).where(QuestParticipant.quest_id == quest.id)) or 0
    if count >= 2:
        raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.")
    secret = os.environ.get("QUEST_SESSION_SECRET", "")
    if len(secret) < 32:
        raise error(503, "quest_service_unavailable", "Guest session configuration is unavailable.")
    identity = GuestIdentity(id=uuid4(), adult_confirmed_at=current, created_at=current)
    db.add(identity)
    derived = hmac.new(secret.encode(), f"{invite.id}:{payload.token}:{idempotency_key}".encode(), hashlib.sha256).hexdigest()
    invite.redeemed_at = current
    invite.redeemed_by = identity.id
    invite.retry_key_hash = key_hash
    invite.retry_until = current + timedelta(seconds=REDEEM_RETRY_SECONDS)
    invite.retry_session_hash = digest(derived)
    quest.state = "preparing"
    quest.version += 1
    db.add(QuestParticipant(quest_id=quest.id, identity_id=identity.id, role="collaborator"))
    _, session = create_session(db, identity.id, derived)
    db.add(session)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise error(404, "invitation_unavailable", "This invitation is invalid, expired, revoked, or already used.") from exc
    set_session_cookie(response, derived, session.expires_at)
    return quest_response(db, quest)


PREPARATION_REQUIRED_COUNT = 7
ARTIFACT_HISTORY_LIMIT = 50


def _locked_member_quest(
    db: Session, quest_id: UUID, identity_id: UUID, *, allow_expired: bool = False,
) -> tuple[Quest, QuestParticipant]:
    quest = db.scalar(select(Quest).where(Quest.id == quest_id).with_for_update())
    participant = db.get(QuestParticipant, (quest_id, identity_id))
    if quest is None or participant is None:
        raise error(404, "quest_not_found", "Quest was not found.")
    if not allow_expired:
        _reject_expired_quest(quest)
    return quest, participant


def _reject_expired_quest(quest: Quest) -> None:
    if quest.expires_at <= now() and quest.state not in {"expired", "cancelled"}:
        raise error(409, "quest_expired", "This quest has expired.")


def _member_preparation_count(db: Session, quest_id: UUID, identity_id: UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(QuestPreparationEvidence).where(
            QuestPreparationEvidence.quest_id == quest_id,
            QuestPreparationEvidence.identity_id == identity_id,
        )
    ) or 0


def _preparation_status(db: Session, quest: Quest, current_identity_id: UUID) -> PreparationStatus:
    participants = db.scalars(
        select(QuestParticipant).where(QuestParticipant.quest_id == quest.id).order_by(QuestParticipant.role)
    ).all()
    members = []
    for participant in participants:
        evidence_ids = list(db.scalars(select(QuestPreparationEvidence.evidence_id).where(
            QuestPreparationEvidence.quest_id == quest.id,
            QuestPreparationEvidence.identity_id == participant.identity_id,
        ).order_by(QuestPreparationEvidence.evidence_id)))
        members.append(PreparationMemberStatus(
            role=participant.role, checked_count=len(evidence_ids), evidence_ids=evidence_ids,
            complete=len(evidence_ids) >= PREPARATION_REQUIRED_COUNT,
        ))
    state = "expired" if quest.expires_at <= now() and quest.state not in {"cancelled", "expired"} else quest.state
    current_participant = next((item for item in participants if item.identity_id == current_identity_id), None)
    assert current_participant is not None
    return PreparationStatus(quest_id=quest.id, current_role=current_participant.role, state=state, members=members)


def _artifact_snapshot_dict(snapshot: ArtifactSnapshot) -> dict:
    return snapshot.model_dump(mode="json")


def _artifact_response(db: Session, quest: Quest, artifact: QuestArtifact) -> ArtifactResponse:
    total = db.scalar(
        select(func.count()).select_from(QuestArtifactRevision).where(QuestArtifactRevision.artifact_id == artifact.id)
    ) or 0
    revisions = db.scalars(
        select(QuestArtifactRevision).where(QuestArtifactRevision.artifact_id == artifact.id)
        .order_by(QuestArtifactRevision.revision_number.desc()).limit(ARTIFACT_HISTORY_LIMIT)
    ).all()
    author_ids = {revision.author_identity_id for revision in revisions if revision.author_identity_id is not None}
    roles = {
        identity_id: role
        for identity_id, role in db.execute(
            select(QuestParticipant.identity_id, QuestParticipant.role).where(
                QuestParticipant.quest_id == quest.id,
                QuestParticipant.identity_id.in_(author_ids or {UUID(int=0)}),
            )
        )
    }
    revision_models = [
        ArtifactRevisionResponse(
            revision_id=revision.id, revision_number=revision.revision_number,
            changed_section=revision.changed_section,
            author_role="system" if revision.author_identity_id is None else roles[revision.author_identity_id],
            created_at=revision.created_at,
            snapshot=ArtifactSnapshot.model_validate(revision.snapshot),
        )
        for revision in reversed(revisions)
    ]
    current = db.scalar(
        select(QuestArtifactRevision).where(
            QuestArtifactRevision.artifact_id == artifact.id,
            QuestArtifactRevision.revision_number == artifact.current_revision,
        )
    )
    if current is None:
        raise error(503, "artifact_unavailable", "The shared artifact is temporarily unavailable.")
    return ArtifactResponse(
        quest_id=quest.id, current_revision=artifact.current_revision,
        snapshot=ArtifactSnapshot.model_validate(current.snapshot),
        revisions=revision_models, history_truncated=total > ARTIFACT_HISTORY_LIMIT,
    )


@router.get(
    "/quests/{quest_id}/preparation", response_model=PreparationStatus,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_quest_preparation(quest_id: UUID, request: Request, db: Session = Depends(get_db_session)) -> PreparationStatus:
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, _ = member(db, quest_id, identity.id)
    return _preparation_status(db, quest, identity.id)


@router.post(
    "/quests/{quest_id}/preparation/check", response_model=PreparationCheckResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def check_quest_preparation(
    quest_id: UUID, payload: PracticeCheckRequest, request: Request,
    db: Session = Depends(get_db_session),
) -> PreparationCheckResponse:
    require_origin(request)
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, participant = _locked_member_quest(db, quest_id, identity.id)
    if quest.state not in {"preparing", "collaborating"}:
        raise error(409, "preparation_unavailable", "Preparation is not available for this quest.")
    practice_set = get_practice_set(quest.lesson_id)
    exercise = next((item for item in practice_set.exercises if item.exercise_id == payload.exercise_id), None) if practice_set else None
    if exercise is None:
        raise error(404, "exercise_not_found", "Exercise was not found for this lesson.")
    try:
        result = check_practice_answer(quest.lesson_id, payload.exercise_id, payload.answer)
    except IncompatiblePracticeAnswer as exc:
        raise error(400, "incompatible_practice_answer", str(exc)) from exc
    except ValueError as exc:
        raise error(400, "invalid_practice_answer", str(exc)) from exc
    if result is None:
        raise error(404, "exercise_not_found", "Exercise was not found for this lesson.")

    if result.correct:
        db.execute(
            pg_insert(QuestPreparationEvidence)
            .values(quest_id=quest.id, identity_id=identity.id, evidence_id=exercise.evidence_id,
                    exercise_id=exercise.exercise_id, exercise_version=exercise.version, checked_at=now())
            .on_conflict_do_nothing(index_elements=["quest_id", "identity_id", "evidence_id"])
        )
    own_count = _member_preparation_count(db, quest.id, identity.id)
    members = db.scalars(select(QuestParticipant).where(QuestParticipant.quest_id == quest.id)).all()
    both_ready = len(members) == 2 and all(
        _member_preparation_count(db, quest.id, item.identity_id) >= PREPARATION_REQUIRED_COUNT
        for item in members
    )
    if both_ready and quest.state == "preparing":
        quest.state = "collaborating"
        quest.version += 1
        artifact = QuestArtifact(id=uuid4(), quest_id=quest.id, current_revision=0, created_at=now())
        db.add(artifact)
        db.flush()
        initial_snapshot = ArtifactSnapshot(
            explanation="", example="",
            misconception_correction={"misconception": "", "correction": ""},
            follow_up_question="",
        )
        db.add(QuestArtifactRevision(
            id=uuid4(), artifact_id=artifact.id, quest_id=quest.id, revision_number=0,
            author_identity_id=None, changed_section=None, snapshot=_artifact_snapshot_dict(initial_snapshot),
            created_at=now(),
        ))
    db.commit()
    return PreparationCheckResponse(
        quest_id=quest.id, exercise_id=exercise.exercise_id, evidence_id=exercise.evidence_id,
        correct=result.correct, feedback=result.feedback, member_checked_count=own_count,
        member_complete=own_count >= PREPARATION_REQUIRED_COUNT,
        quest_state="collaborating" if quest.state == "collaborating" else "preparing",
    )


@router.get(
    "/quests/{quest_id}/artifact", response_model=ArtifactResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def get_quest_artifact(quest_id: UUID, request: Request, db: Session = Depends(get_db_session)) -> ArtifactResponse:
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, _ = member(db, quest_id, identity.id)
    if quest.expires_at <= now() or quest.state != "collaborating":
        raise error(409, "artifact_unavailable", "The shared artifact is not available yet.")
    artifact = db.scalar(select(QuestArtifact).where(QuestArtifact.quest_id == quest.id))
    if artifact is None:
        raise error(409, "artifact_unavailable", "The shared artifact is not available yet.")
    return _artifact_response(db, quest, artifact)


@router.patch(
    "/quests/{quest_id}/artifact/sections/{section_id}", response_model=ArtifactRevisionResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def update_quest_artifact_section(
    quest_id: UUID, section_id: ArtifactSection, payload: ArtifactSectionUpdate, request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db_session),
) -> ArtifactRevisionResponse:
    require_origin(request)
    if not idempotency_key or len(idempotency_key) > 128:
        raise error(400, "idempotency_key_required", "A valid Idempotency-Key header is required.")
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, participant = _locked_member_quest(db, quest_id, identity.id)
    if quest.state != "collaborating":
        raise error(409, "artifact_unavailable", "The shared artifact is not available yet.")
    if section_id == "misconception_correction":
        if not isinstance(payload.content, MisconceptionCorrection):
            raise error(400, "invalid_artifact_section", "This section requires a misconception and correction.")
        section_value = payload.content
        if not section_value.misconception.strip() or not section_value.correction.strip():
            raise error(400, "invalid_artifact_section", "Both misconception and correction must contain text.")
        content_value = section_value.model_dump(mode="json")
    else:
        if not isinstance(payload.content, str):
            raise error(400, "invalid_artifact_section", "This section requires plain text.")
        if not payload.content.strip():
            raise error(400, "invalid_artifact_section", "Section content must contain text.")
        if section_id == "follow_up_question" and len(payload.content) > 1000:
            raise error(400, "invalid_artifact_section", "The follow-up question must not exceed 1000 characters.")
        content_value = payload.content

    artifact = db.scalar(select(QuestArtifact).where(QuestArtifact.quest_id == quest.id).with_for_update())
    if artifact is None:
        raise error(409, "artifact_unavailable", "The shared artifact is not available yet.")
    key_hash = digest(idempotency_key)
    request_hash = digest(f"{section_id}:{payload.model_dump_json()}")
    prior = db.scalar(select(QuestArtifactRevision).where(
        QuestArtifactRevision.artifact_id == artifact.id,
        QuestArtifactRevision.author_identity_id == identity.id,
        QuestArtifactRevision.idempotency_key_hash == key_hash,
    ))
    if prior is not None:
        if not hmac.compare_digest(prior.request_hash or "", request_hash):
            raise error(409, "idempotency_key_reused", "This idempotency key was used for a different artifact update.")
        return ArtifactRevisionResponse(
            revision_id=prior.id, revision_number=prior.revision_number, changed_section=prior.changed_section,
            author_role=participant.role, created_at=prior.created_at,
            snapshot=ArtifactSnapshot.model_validate(prior.snapshot),
        )
    if payload.expected_revision != artifact.current_revision:
        raise HTTPException(status_code=409, detail={
            "code": "artifact_revision_conflict",
            "message": "The artifact changed since it was loaded. Refresh the current snapshot before reconciling.",
            "current_revision": artifact.current_revision,
        })

    current = db.scalar(select(QuestArtifactRevision).where(
        QuestArtifactRevision.artifact_id == artifact.id,
        QuestArtifactRevision.revision_number == artifact.current_revision,
    ))
    if current is None:
        raise error(503, "artifact_unavailable", "The shared artifact is temporarily unavailable.")
    snapshot_data = dict(current.snapshot)
    snapshot_data[section_id] = content_value
    try:
        updated_snapshot = ArtifactSnapshot.model_validate(snapshot_data)
    except Exception as exc:
        raise error(400, "invalid_artifact_section", "The update exceeds the artifact content limits.") from exc
    revision_number = artifact.current_revision + 1
    revision = QuestArtifactRevision(
        id=uuid4(), artifact_id=artifact.id, quest_id=quest.id,
        revision_number=revision_number, author_identity_id=identity.id,
        changed_section=section_id, snapshot=_artifact_snapshot_dict(updated_snapshot),
        idempotency_key_hash=key_hash, request_hash=request_hash, created_at=now(),
    )
    db.add(revision)
    db.flush()
    artifact.current_revision = revision_number
    db.commit()
    return ArtifactRevisionResponse(
        revision_id=revision.id, revision_number=revision_number, changed_section=section_id,
        author_role=participant.role, created_at=revision.created_at, snapshot=updated_snapshot,
    )


def _peer_review_response(db: Session, quest: Quest, review: QuestArtifactReview) -> PeerReviewResponse:
    revision = db.get(QuestArtifactRevision, review.artifact_revision_id)
    reviewer = db.get(QuestParticipant, (quest.id, review.reviewer_identity_id))
    recipient = db.get(QuestParticipant, (quest.id, review.recipient_identity_id))
    if revision is None or reviewer is None or recipient is None:
        raise error(503, "review_unavailable", "Peer feedback is temporarily unavailable.")
    artifact = db.scalar(select(QuestArtifact).where(QuestArtifact.quest_id == quest.id))
    interaction = db.get(QuestArtifactReviewResponse, review.id)
    return PeerReviewResponse(
        review_id=review.id, revision_id=revision.id, revision_number=revision.revision_number,
        revision_is_current=artifact is not None and artifact.current_revision == revision.revision_number,
        snapshot=ArtifactSnapshot.model_validate(revision.snapshot),
        reviewer_role=reviewer.role, recipient_role=recipient.role, rubric_version=review.rubric_version,
        conceptual_correctness=review.conceptual_correctness, explanation_clarity=review.explanation_clarity,
        example_relevance=review.example_relevance, misconception_correction=review.misconception_correction,
        follow_up_usefulness=review.follow_up_usefulness, strength=review.strength,
        improvement_suggestion=review.improvement_suggestion, rationale=review.rationale,
        created_at=review.created_at,
        acknowledged_at=interaction.acknowledged_at if interaction else None,
        response_text=interaction.response_text if interaction else None,
        responded_at=interaction.responded_at if interaction else None,
    )


def _review_status(db: Session, quest: Quest, participant: QuestParticipant) -> QuestReviewStatus:
    participants = db.scalars(select(QuestParticipant).where(QuestParticipant.quest_id == quest.id)).all()
    partner = next((row for row in participants if row.identity_id != participant.identity_id), None)
    state = "expired" if quest.expires_at <= now() and quest.state not in {"expired", "cancelled"} else quest.state
    given = db.scalar(select(QuestArtifactReview).where(
        QuestArtifactReview.quest_id == quest.id,
        QuestArtifactReview.reviewer_identity_id == participant.identity_id,
    ))
    received = db.scalar(select(QuestArtifactReview).where(
        QuestArtifactReview.quest_id == quest.id,
        QuestArtifactReview.recipient_identity_id == participant.identity_id,
    ))
    authored = set(db.scalars(select(QuestArtifactRevision.author_identity_id).where(
        QuestArtifactRevision.quest_id == quest.id,
        QuestArtifactRevision.author_identity_id.is_not(None),
    ))) if quest.state == "collaborating" else set()
    eligible = quest.state == "collaborating" and quest.expires_at > now() and len(authored) == 2
    reviewable: ReviewRevisionSummary | None = None
    if eligible and given is None and partner is not None:
        revision = db.scalar(select(QuestArtifactRevision).where(
            QuestArtifactRevision.quest_id == quest.id,
            QuestArtifactRevision.author_identity_id == partner.identity_id,
        ).order_by(QuestArtifactRevision.revision_number.desc()).limit(1))
        if revision is not None:
            reviewable = ReviewRevisionSummary(
                revision_id=revision.id, revision_number=revision.revision_number,
                author_role=partner.role, created_at=revision.created_at,
                snapshot=ArtifactSnapshot.model_validate(revision.snapshot),
            )
    return QuestReviewStatus(
        quest_id=quest.id, current_role=participant.role, state=state,
        eligible=eligible, submitted_by_you=given is not None,
        submitted_by_partner=partner is not None and db.scalar(select(QuestArtifactReview.id).where(
            QuestArtifactReview.quest_id == quest.id,
            QuestArtifactReview.reviewer_identity_id == partner.identity_id,
        )) is not None,
        reviewable_revision=reviewable,
        review_given=_peer_review_response(db, quest, given) if given else None,
        review_received=_peer_review_response(db, quest, received) if received else None,
    )


def _review_idempotency_key(key: str | None) -> tuple[str, str]:
    if not key or not key.strip() or len(key) > 128:
        raise error(400, "idempotency_key_required", "A valid Idempotency-Key header is required.")
    return key, digest(key)


@router.get(
    "/quests/{quest_id}/reviews", response_model=QuestReviewStatus,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_quest_reviews(quest_id: UUID, request: Request, db: Session = Depends(get_db_session)) -> QuestReviewStatus:
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, participant = member(db, quest_id, identity.id)
    return _review_status(db, quest, participant)


@router.post(
    "/quests/{quest_id}/reviews", response_model=PeerReviewResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def submit_quest_review(
    quest_id: UUID, payload: PeerReviewRequest, request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db_session),
) -> PeerReviewResponse:
    require_origin(request)
    _, key_hash = _review_idempotency_key(idempotency_key)
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, participant = _locked_member_quest(db, quest_id, identity.id, allow_expired=True)
    if quest.state != "collaborating":
        raise error(409, "review_not_available", "Peer feedback is available after collaboration begins.")
    body_hash = digest(payload.model_dump_json())
    previous = db.scalar(select(QuestArtifactReview).where(
        QuestArtifactReview.quest_id == quest.id,
        QuestArtifactReview.reviewer_identity_id == identity.id,
        QuestArtifactReview.idempotency_key_hash == key_hash,
    ))
    if previous is not None:
        if not hmac.compare_digest(previous.request_hash, body_hash):
            raise error(409, "idempotency_key_reused", "This idempotency key was used for a different review.")
        return _peer_review_response(db, quest, previous)
    _reject_expired_quest(quest)
    if db.scalar(select(QuestArtifactReview.id).where(
        QuestArtifactReview.quest_id == quest.id,
        QuestArtifactReview.reviewer_identity_id == identity.id,
    )) is not None:
        raise error(409, "review_already_submitted", "Your first-round review has already been submitted.")

    requested_revision = db.get(QuestArtifactRevision, payload.revision_id)
    if requested_revision is not None and requested_revision.quest_id == quest.id and requested_revision.author_identity_id == identity.id:
        raise error(409, "self_review_not_allowed", "You can only review your partner’s contribution.")

    partner = db.scalar(select(QuestParticipant).where(
        QuestParticipant.quest_id == quest.id,
        QuestParticipant.identity_id != identity.id,
    ))
    artifact = db.scalar(select(QuestArtifact).where(QuestArtifact.quest_id == quest.id))
    if partner is None or artifact is None:
        raise error(409, "review_not_available", "Both participants must contribute before peer review begins.")
    authors = set(db.scalars(select(QuestArtifactRevision.author_identity_id).where(
        QuestArtifactRevision.quest_id == quest.id,
        QuestArtifactRevision.author_identity_id.is_not(None),
    )))
    if len(authors) != 2:
        raise error(409, "review_not_available", "Both participants must contribute before peer review begins.")
    target = db.scalar(select(QuestArtifactRevision).where(
        QuestArtifactRevision.quest_id == quest.id,
        QuestArtifactRevision.author_identity_id == partner.identity_id,
    ).order_by(QuestArtifactRevision.revision_number.desc()).limit(1))
    if target is None:
        raise error(409, "review_not_available", "Your partner has no eligible artifact revision to review.")
    if payload.revision_id != target.id:
        raise HTTPException(status_code=409, detail={
            "code": "review_target_changed",
            "message": "Your partner’s latest contribution changed. Refresh the review before submitting.",
            "current_reviewable_revision": {
                "revision_id": str(target.id),
                "revision_number": target.revision_number,
            },
        })

    review = QuestArtifactReview(
        id=uuid4(), quest_id=quest.id, artifact_id=artifact.id, artifact_revision_id=target.id,
        reviewer_identity_id=identity.id, recipient_identity_id=target.author_identity_id,
        rubric_version=payload.rubric_version,
        conceptual_correctness=payload.conceptual_correctness,
        explanation_clarity=payload.explanation_clarity, example_relevance=payload.example_relevance,
        misconception_correction=payload.misconception_correction,
        follow_up_usefulness=payload.follow_up_usefulness,
        strength=payload.strength, improvement_suggestion=payload.improvement_suggestion,
        rationale=payload.rationale, idempotency_key_hash=key_hash, request_hash=body_hash, created_at=now(),
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise error(409, "review_already_submitted", "A review already exists for this contribution.") from exc
    return _peer_review_response(db, quest, review)


def _review_recipient(db: Session, quest_id: UUID, review_id: UUID, identity_id: UUID) -> tuple[Quest, QuestArtifactReview]:
    quest, _ = _locked_member_quest(db, quest_id, identity_id, allow_expired=True)
    review = db.scalar(select(QuestArtifactReview).where(
        QuestArtifactReview.id == review_id,
        QuestArtifactReview.quest_id == quest.id,
        QuestArtifactReview.recipient_identity_id == identity_id,
    ).with_for_update())
    if review is None:
        raise error(404, "review_not_found", "Peer feedback was not found.")
    if quest.state != "collaborating":
        raise error(409, "review_not_available", "Review responses are available during collaboration.")
    return quest, review


def _recipient_response(review_id: UUID, row: QuestArtifactReviewResponse) -> ReviewRecipientResponse:
    return ReviewRecipientResponse(
        review_id=review_id, acknowledged_at=row.acknowledged_at,
        response_text=row.response_text, responded_at=row.responded_at,
    )


@router.post(
    "/quests/{quest_id}/reviews/{review_id}/acknowledgement", response_model=ReviewRecipientResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def acknowledge_quest_review(
    quest_id: UUID, review_id: UUID, payload: ReviewAcknowledgementRequest, request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db_session),
) -> ReviewRecipientResponse:
    require_origin(request)
    _, key_hash = _review_idempotency_key(idempotency_key)
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, review = _review_recipient(db, quest_id, review_id, identity.id)
    request_hash = digest(payload.model_dump_json())
    collision = db.scalar(select(QuestArtifactReviewResponse).where(
        QuestArtifactReviewResponse.quest_id == quest.id,
        QuestArtifactReviewResponse.identity_id == identity.id,
        QuestArtifactReviewResponse.acknowledgement_key_hash == key_hash,
    ))
    if collision is not None:
        if collision.review_id != review.id or not hmac.compare_digest(collision.acknowledgement_request_hash, request_hash):
            raise error(409, "idempotency_key_reused", "This idempotency key was used for a different action.")
        return _recipient_response(review.id, collision)
    _reject_expired_quest(quest)
    existing = db.get(QuestArtifactReviewResponse, review.id)
    if existing is not None:
        raise error(409, "review_already_acknowledged", "This feedback has already been acknowledged.")
    row = QuestArtifactReviewResponse(
        review_id=review.id, quest_id=quest.id, identity_id=identity.id,
        acknowledgement_key_hash=key_hash, acknowledgement_request_hash=request_hash,
        acknowledged_at=now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise error(409, "idempotency_key_reused", "This idempotency key was already used.") from exc
    return _recipient_response(review.id, row)


@router.post(
    "/quests/{quest_id}/reviews/{review_id}/response", response_model=ReviewRecipientResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def respond_to_quest_review(
    quest_id: UUID, review_id: UUID, payload: ReviewResponseRequest, request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db_session),
) -> ReviewRecipientResponse:
    require_origin(request)
    _, key_hash = _review_idempotency_key(idempotency_key)
    _, identity = authenticate(db, request.cookies.get(COOKIE_NAME))
    quest, review = _review_recipient(db, quest_id, review_id, identity.id)
    row = db.get(QuestArtifactReviewResponse, review.id)
    if row is None:
        raise error(409, "review_acknowledgement_required", "Acknowledge the feedback before responding.")
    request_hash = digest(payload.model_dump_json())
    collision = db.scalar(select(QuestArtifactReviewResponse).where(
        QuestArtifactReviewResponse.quest_id == quest.id,
        QuestArtifactReviewResponse.identity_id == identity.id,
        QuestArtifactReviewResponse.response_key_hash == key_hash,
    ))
    if collision is not None:
        if collision.review_id != review.id or not hmac.compare_digest(collision.response_request_hash or "", request_hash):
            raise error(409, "idempotency_key_reused", "This idempotency key was used for a different action.")
        return _recipient_response(review.id, collision)
    _reject_expired_quest(quest)
    if row.response_text is not None:
        raise error(409, "review_response_already_submitted", "A response to this feedback has already been submitted.")
    row.response_text = payload.response
    row.response_key_hash = key_hash
    row.response_request_hash = request_hash
    row.responded_at = now()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise error(409, "idempotency_key_reused", "This idempotency key was already used.") from exc
    return _recipient_response(review.id, row)
