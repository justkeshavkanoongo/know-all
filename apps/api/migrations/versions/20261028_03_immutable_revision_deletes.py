"""Prevent revision deletion except as part of quest cleanup."""
from alembic import op

revision = "20261028_03"
down_revision = "20261028_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS quest_artifact_revision_immutable ON quest_artifact_revisions")
    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_artifact_revision_update() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'DELETE' AND NOT EXISTS (SELECT 1 FROM quests WHERE id = OLD.quest_id) THEN
        RETURN OLD;
      END IF;
      RAISE EXCEPTION 'artifact revisions are immutable' USING ERRCODE = '55000';
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER quest_artifact_revision_immutable
    BEFORE UPDATE OR DELETE ON quest_artifact_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_artifact_revision_update()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS quest_artifact_revision_immutable ON quest_artifact_revisions")
    op.execute("""
    CREATE TRIGGER quest_artifact_revision_immutable
    BEFORE UPDATE ON quest_artifact_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_artifact_revision_update()
    """)
