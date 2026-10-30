"""Index recipient history and write-once action idempotency keys."""
from alembic import op
import sqlalchemy as sa

revision = "20261030_05"
down_revision = "20261030_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_quest_reviews_recipient", "quest_artifact_reviews",
        ["quest_id", "recipient_identity_id"],
    )
    op.create_index(
        "uq_review_ack_idempotency", "quest_artifact_review_responses",
        ["quest_id", "identity_id", "acknowledgement_key_hash"], unique=True,
    )
    op.create_index(
        "uq_review_reply_idempotency", "quest_artifact_review_responses",
        ["quest_id", "identity_id", "response_key_hash"], unique=True,
        postgresql_where=sa.text("response_key_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_review_reply_idempotency", table_name="quest_artifact_review_responses")
    op.drop_index("uq_review_ack_idempotency", table_name="quest_artifact_review_responses")
    op.drop_index("ix_quest_reviews_recipient", table_name="quest_artifact_reviews")
