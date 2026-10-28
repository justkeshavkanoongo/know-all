from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class GuestIdentity(Base):
    __tablename__ = "guest_identities"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    adult_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class GuestSession(Base):
    __tablename__ = "guest_sessions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    identity_id: Mapped[UUID] = mapped_column(ForeignKey("guest_identities.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Quest(Base):
    __tablename__ = "quests"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    lesson_id: Mapped[str] = mapped_column(String(100), nullable=False)
    concept_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("state in ('awaiting_partner','preparing','collaborating','cancelled','expired')", name="ck_quests_state"),)


class QuestParticipant(Base):
    __tablename__ = "quest_participants"
    quest_id: Mapped[UUID] = mapped_column(ForeignKey("quests.id", ondelete="CASCADE"), primary_key=True)
    identity_id: Mapped[UUID] = mapped_column(ForeignKey("guest_identities.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    __table_args__ = (
        CheckConstraint("role in ('host','collaborator')", name="ck_quest_participants_role"),
        Index("uq_quest_one_host", "quest_id", unique=True, postgresql_where=text("role = 'host'")),
        Index("ix_quest_participants_limit", "quest_id"),
    )


class Invitation(Base):
    __tablename__ = "quest_invitations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    quest_id: Mapped[UUID] = mapped_column(ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeemed_by: Mapped[UUID | None] = mapped_column(ForeignKey("guest_identities.id", ondelete="SET NULL"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_key_hash: Mapped[str | None] = mapped_column(String(64))
    retry_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_session_hash: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        Index("uq_quest_active_invitation", "quest_id", unique=True,
              postgresql_where=text("redeemed_at is null and revoked_at is null")),
    )


class IdempotencyRecord(Base):
    __tablename__ = "quest_idempotency_records"
    identity_id: Mapped[UUID] = mapped_column(ForeignKey("guest_identities.id", ondelete="CASCADE"), primary_key=True)
    operation: Mapped[str] = mapped_column(String(64), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuestPreparationEvidence(Base):
    __tablename__ = "quest_preparation_evidence"
    quest_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    identity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    exercise_id: Mapped[str] = mapped_column(String(120), nullable=False)
    exercise_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["quest_id", "identity_id"],
            ["quest_participants.quest_id", "quest_participants.identity_id"],
            ondelete="CASCADE",
        ),
    )


class QuestArtifact(Base):
    __tablename__ = "quest_artifacts"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    quest_id: Mapped[UUID] = mapped_column(ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, unique=True)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("current_revision >= 0", name="ck_quest_artifact_revision_nonnegative"),
        UniqueConstraint("id", "quest_id", name="uq_quest_artifact_id_quest"),
    )


class QuestArtifactRevision(Base):
    __tablename__ = "quest_artifact_revisions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    artifact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quest_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    author_identity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    changed_section: Mapped[str | None] = mapped_column(String(40))
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["artifact_id", "quest_id"], ["quest_artifacts.id", "quest_artifacts.quest_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["quest_id", "author_identity_id"], ["quest_participants.quest_id", "quest_participants.identity_id"], ondelete="CASCADE"),
        CheckConstraint("revision_number >= 0", name="ck_artifact_revision_nonnegative"),
        CheckConstraint("(revision_number = 0 AND author_identity_id IS NULL) OR (revision_number > 0 AND author_identity_id IS NOT NULL)", name="ck_artifact_revision_author"),
        UniqueConstraint("artifact_id", "revision_number", name="uq_artifact_revision_number"),
        UniqueConstraint("artifact_id", "id", name="uq_artifact_revision_id"),
    )
    __table_args__ += (
        Index("uq_artifact_revision_idempotency", "artifact_id", "author_identity_id", "idempotency_key_hash", unique=True,
              postgresql_where=text("idempotency_key_hash IS NOT NULL")),
    )


QuestArtifact.__table__.append_constraint(ForeignKeyConstraint(
    ["id", "current_revision"],
    ["quest_artifact_revisions.artifact_id", "quest_artifact_revisions.revision_number"],
    name="fk_quest_artifact_current_revision", deferrable=True, initially="DEFERRED",
))
