"""Hide automation execution conversations from regular chat history.

Revision ID: 20260823_11
Revises: 20260820_10
Create Date: 2026-08-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260823_11"
down_revision: str | None = "20260820_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("conversation_kind_valid", type_="check")
        batch_op.create_check_constraint(
            "conversation_kind_valid",
            "kind IN ('chat', 'browser', 'automation_draft', 'automation_execution')",
        )

    op.execute(
        """
        UPDATE conversations
        SET kind = 'automation_execution'
        WHERE conversation_id IN (
            SELECT runs.conversation_id
            FROM runs
            JOIN automation_executions
              ON automation_executions.run_id = runs.run_id
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE conversations SET kind = 'chat' WHERE kind = 'automation_execution'"
    )
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("conversation_kind_valid", type_="check")
        batch_op.create_check_constraint(
            "conversation_kind_valid",
            "kind IN ('chat', 'browser', 'automation_draft')",
        )
