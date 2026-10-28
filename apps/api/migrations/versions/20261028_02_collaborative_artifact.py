"""Persist quest preparation evidence and immutable shared artifact revisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261028_02"
down_revision = "20261028_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_quests_state", "quests", type_="check")
    op.create_check_constraint(
        "ck_quests_state", "quests",
        "state in ('awaiting_partner','preparing','collaborating','cancelled','expired')",
    )

    op.create_table(
        "quest_preparation_evidence",
        sa.Column("quest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", sa.String(120), nullable=False),
        sa.Column("exercise_id", sa.String(120), nullable=False),
        sa.Column("exercise_version", sa.String(32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("quest_id", "identity_id", "evidence_id", name="pk_quest_preparation_evidence"),
        sa.ForeignKeyConstraint(
            ["quest_id", "identity_id"],
            ["quest_participants.quest_id", "quest_participants.identity_id"],
            ondelete="CASCADE", name="fk_preparation_evidence_membership",
        ),
    )

    op.create_table(
        "quest_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("current_revision >= 0", name="ck_quest_artifact_revision_nonnegative"),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quest_id", name="uq_quest_artifacts_quest"),
        sa.UniqueConstraint("id", "quest_id", name="uq_quest_artifact_id_quest"),
    )
    op.create_table(
        "quest_artifact_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("author_identity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_section", sa.String(40), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision_number >= 0", name="ck_artifact_revision_nonnegative"),
        sa.CheckConstraint(
            "(revision_number = 0 AND author_identity_id IS NULL) OR (revision_number > 0 AND author_identity_id IS NOT NULL)",
            name="ck_artifact_revision_author",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id", "quest_id"], ["quest_artifacts.id", "quest_artifacts.quest_id"],
            ondelete="CASCADE", name="fk_artifact_revision_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["quest_id", "author_identity_id"], ["quest_participants.quest_id", "quest_participants.identity_id"],
            ondelete="CASCADE", name="fk_artifact_revision_author_membership",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id", "revision_number", name="uq_artifact_revision_number"),
        sa.UniqueConstraint("artifact_id", "id", name="uq_artifact_revision_id"),
    )
    op.create_index(
        "uq_artifact_revision_idempotency", "quest_artifact_revisions",
        ["artifact_id", "author_identity_id", "idempotency_key_hash"], unique=True,
        postgresql_where=sa.text("idempotency_key_hash IS NOT NULL"),
    )
    op.create_foreign_key(
        "fk_quest_artifact_current_revision", "quest_artifacts", "quest_artifact_revisions",
        ["id", "current_revision"], ["artifact_id", "revision_number"],
        deferrable=True, initially="DEFERRED",
    )
    op.execute("""
    CREATE FUNCTION prevent_artifact_revision_update() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'artifact revisions are immutable' USING ERRCODE = '55000';
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER quest_artifact_revision_immutable
    BEFORE UPDATE ON quest_artifact_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_artifact_revision_update()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS quest_artifact_revision_immutable ON quest_artifact_revisions")
    op.execute("DROP FUNCTION IF EXISTS prevent_artifact_revision_update()")
    op.drop_constraint("fk_quest_artifact_current_revision", "quest_artifacts", type_="foreignkey")
    op.drop_index("uq_artifact_revision_idempotency", table_name="quest_artifact_revisions")
    op.drop_table("quest_artifact_revisions")
    op.drop_table("quest_artifacts")
    op.drop_table("quest_preparation_evidence")
    op.drop_constraint("ck_quests_state", "quests", type_="check")
    op.create_check_constraint(
        "ck_quests_state", "quests",
        "state in ('awaiting_partner','preparing','cancelled','expired')",
    )
