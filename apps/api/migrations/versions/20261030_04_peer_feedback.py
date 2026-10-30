"""Add immutable, revision-bound peer feedback and recipient responses."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261030_04"
down_revision = "20261028_03"
branch_labels = None
depends_on = None


RATINGS = "('needs_work','mostly_there','clear')"


def upgrade() -> None:
    # This unique key lets the review FK prove that the recipient authored the
    # exact immutable revision being reviewed.
    op.create_unique_constraint(
        "uq_artifact_revision_author_binding", "quest_artifact_revisions",
        ["id", "quest_id", "author_identity_id"],
    )
    op.create_table(
        "quest_artifact_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rubric_version", sa.String(32), nullable=False),
        sa.Column("conceptual_correctness", sa.String(20), nullable=False),
        sa.Column("explanation_clarity", sa.String(20), nullable=False),
        sa.Column("example_relevance", sa.String(20), nullable=False),
        sa.Column("misconception_correction", sa.String(20), nullable=False),
        sa.Column("follow_up_usefulness", sa.String(20), nullable=False),
        sa.Column("strength", sa.Text(), nullable=False),
        sa.Column("improvement_suggestion", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reviewer_identity_id <> recipient_identity_id", name="ck_review_no_self_review"),
        sa.CheckConstraint("rubric_version = 'peer-review-v1'", name="ck_review_rubric_version"),
        *[
            sa.CheckConstraint(f"{column} in {RATINGS}", name=f"ck_review_{column}")
            for column in (
                "conceptual_correctness", "explanation_clarity", "example_relevance",
                "misconception_correction", "follow_up_usefulness",
            )
        ],
        sa.CheckConstraint("length(btrim(strength)) between 1 and 500", name="ck_review_strength_length"),
        sa.CheckConstraint("length(btrim(improvement_suggestion)) between 1 and 500", name="ck_review_suggestion_length"),
        sa.CheckConstraint("length(btrim(rationale)) between 1 and 500", name="ck_review_rationale_length"),
        sa.CheckConstraint("length(strength) + length(improvement_suggestion) + length(rationale) <= 1500", name="ck_review_total_text_length"),
        sa.ForeignKeyConstraint(["artifact_id", "quest_id"], ["quest_artifacts.id", "quest_artifacts.quest_id"], ondelete="CASCADE", name="fk_review_artifact_quest"),
        sa.ForeignKeyConstraint(
            ["artifact_revision_id", "quest_id", "recipient_identity_id"],
            ["quest_artifact_revisions.id", "quest_artifact_revisions.quest_id", "quest_artifact_revisions.author_identity_id"],
            ondelete="CASCADE", name="fk_review_revision_author",
        ),
        sa.ForeignKeyConstraint(["quest_id", "reviewer_identity_id"], ["quest_participants.quest_id", "quest_participants.identity_id"], ondelete="CASCADE", name="fk_review_reviewer_member"),
        sa.PrimaryKeyConstraint("id", name="pk_quest_artifact_reviews"),
        sa.UniqueConstraint("artifact_revision_id", "reviewer_identity_id", name="uq_review_revision_reviewer"),
        sa.UniqueConstraint("quest_id", "reviewer_identity_id", name="uq_review_one_round_per_reviewer"),
        sa.UniqueConstraint("quest_id", "reviewer_identity_id", "idempotency_key_hash", name="uq_review_idempotency_key"),
        sa.UniqueConstraint("id", "quest_id", "recipient_identity_id", name="uq_review_recipient_binding"),
    )
    op.create_table(
        "quest_artifact_review_responses",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acknowledgement_key_hash", sa.String(64), nullable=False),
        sa.Column("acknowledgement_request_hash", sa.String(64), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("response_key_hash", sa.String(64), nullable=True),
        sa.Column("response_request_hash", sa.String(64), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(response_text IS NULL AND response_key_hash IS NULL AND response_request_hash IS NULL AND responded_at IS NULL) OR "
            "(response_text IS NOT NULL AND response_key_hash IS NOT NULL AND response_request_hash IS NOT NULL AND responded_at IS NOT NULL)",
            name="ck_review_response_all_or_none",
        ),
        sa.CheckConstraint("response_text IS NULL OR length(btrim(response_text)) between 1 and 500", name="ck_review_response_length"),
        sa.ForeignKeyConstraint(
            ["review_id", "quest_id", "identity_id"],
            ["quest_artifact_reviews.id", "quest_artifact_reviews.quest_id", "quest_artifact_reviews.recipient_identity_id"],
            ondelete="CASCADE", name="fk_review_response_recipient",
        ),
        sa.PrimaryKeyConstraint("review_id", name="pk_quest_artifact_review_responses"),
    )
    op.execute("""
    CREATE FUNCTION protect_quest_artifact_review() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' AND NOT EXISTS (SELECT 1 FROM quests WHERE id = OLD.quest_id) THEN
        RETURN OLD;
      END IF;
      RAISE EXCEPTION 'peer reviews are immutable' USING ERRCODE = '55000';
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER quest_artifact_review_immutable
    BEFORE UPDATE OR DELETE ON quest_artifact_reviews
    FOR EACH ROW EXECUTE FUNCTION protect_quest_artifact_review()
    """)
    op.execute("""
    CREATE FUNCTION protect_quest_artifact_review_response() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' AND NOT EXISTS (SELECT 1 FROM quests WHERE id = OLD.quest_id) THEN
        RETURN OLD;
      END IF;
      IF TG_OP = 'UPDATE'
         AND NEW.review_id = OLD.review_id
         AND NEW.quest_id = OLD.quest_id
         AND NEW.identity_id = OLD.identity_id
         AND NEW.acknowledgement_key_hash = OLD.acknowledgement_key_hash
         AND NEW.acknowledgement_request_hash = OLD.acknowledgement_request_hash
         AND NEW.acknowledged_at = OLD.acknowledged_at
         AND OLD.response_text IS NULL
         AND NEW.response_text IS NOT NULL
         AND NEW.response_key_hash IS NOT NULL
         AND NEW.response_request_hash IS NOT NULL
         AND NEW.responded_at IS NOT NULL THEN
        RETURN NEW;
      END IF;
      RAISE EXCEPTION 'review acknowledgement and response are write-once' USING ERRCODE = '55000';
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER quest_artifact_review_response_write_once
    BEFORE UPDATE OR DELETE ON quest_artifact_review_responses
    FOR EACH ROW EXECUTE FUNCTION protect_quest_artifact_review_response()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS quest_artifact_review_response_write_once ON quest_artifact_review_responses")
    op.execute("DROP FUNCTION IF EXISTS protect_quest_artifact_review_response()")
    op.execute("DROP TRIGGER IF EXISTS quest_artifact_review_immutable ON quest_artifact_reviews")
    op.execute("DROP FUNCTION IF EXISTS protect_quest_artifact_review()")
    op.drop_table("quest_artifact_review_responses")
    op.drop_table("quest_artifact_reviews")
    op.drop_constraint("uq_artifact_revision_author_binding", "quest_artifact_revisions", type_="unique")
