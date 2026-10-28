"""Create pseudonymous guest and pair-quest schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261028_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("adult_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "guest_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guest_identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_guest_sessions_identity_id", "guest_sessions", ["identity_id"])
    op.create_index("ix_guest_sessions_expires_at", "guest_sessions", ["expires_at"])
    op.create_table(
        "quests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("lesson_id", sa.String(100), nullable=False),
        sa.Column("concept_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("template_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("state in ('awaiting_partner','preparing','cancelled','expired')", name="ck_quests_state"),
    )
    op.create_index("ix_quests_expires_at", "quests", ["expires_at"])
    op.create_table(
        "quest_participants",
        sa.Column("quest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quests.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guest_identities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role in ('host','collaborator')", name="ck_quest_participants_role"),
    )
    op.create_index("uq_quest_one_host", "quest_participants", ["quest_id"], unique=True, postgresql_where=sa.text("role = 'host'"))
    op.create_index("ix_quest_participants_limit", "quest_participants", ["quest_id"])
    op.create_table(
        "quest_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("quest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True)),
        sa.Column("redeemed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("guest_identities.id", ondelete="SET NULL")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("retry_key_hash", sa.String(64)),
        sa.Column("retry_until", sa.DateTime(timezone=True)),
        sa.Column("retry_session_hash", sa.String(64)),
    )
    op.create_index("ix_quest_invitations_quest_id", "quest_invitations", ["quest_id"])
    op.create_index("ix_quest_invitations_expires_at", "quest_invitations", ["expires_at"])
    op.create_index(
        "uq_quest_active_invitation", "quest_invitations", ["quest_id"], unique=True,
        postgresql_where=sa.text("redeemed_at is null and revoked_at is null"),
    )
    op.create_table(
        "quest_idempotency_records",
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guest_identities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("operation", sa.String(64), primary_key=True),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_two_quest_participants() RETURNS trigger AS $$
    BEGIN
      PERFORM 1 FROM quests WHERE id = NEW.quest_id FOR UPDATE;
      IF (SELECT count(*) FROM quest_participants WHERE quest_id = NEW.quest_id) >= 2 THEN
        RAISE EXCEPTION 'quest participant limit reached' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER quest_participant_limit BEFORE INSERT ON quest_participants
    FOR EACH ROW EXECUTE FUNCTION enforce_two_quest_participants()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS quest_participant_limit ON quest_participants")
    op.execute("DROP FUNCTION IF EXISTS enforce_two_quest_participants()")
    op.drop_table("quest_idempotency_records")
    op.drop_index("uq_quest_active_invitation", table_name="quest_invitations")
    op.drop_index("ix_quest_invitations_expires_at", table_name="quest_invitations")
    op.drop_index("ix_quest_invitations_quest_id", table_name="quest_invitations")
    op.drop_table("quest_invitations")
    op.drop_index("ix_quest_participants_limit", table_name="quest_participants")
    op.drop_index("uq_quest_one_host", table_name="quest_participants")
    op.drop_table("quest_participants")
    op.drop_index("ix_quests_expires_at", table_name="quests")
    op.drop_table("quests")
    op.drop_index("ix_guest_sessions_expires_at", table_name="guest_sessions")
    op.drop_index("ix_guest_sessions_identity_id", table_name="guest_sessions")
    op.drop_table("guest_sessions")
    op.drop_table("guest_identities")
