"""Allow conversations used only while drafting automations.

Revision ID: 20260820_10
Revises: 20260820_09
Create Date: 2026-08-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260820_10"
down_revision: str | None = "20260820_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("conversation_kind_valid", type_="check")
        batch_op.create_check_constraint(
            "conversation_kind_valid",
            "kind IN ('chat', 'browser', 'automation_draft')",
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("conversation_kind_valid", type_="check")
        batch_op.create_check_constraint(
            "conversation_kind_valid", "kind IN ('chat', 'browser')"
        )
