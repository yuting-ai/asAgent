"""Add conversation kind for chat and browser isolation.

Revision ID: 20260816_06
Revises: 20260815_05
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_06"
down_revision: str | None = "20260815_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "kind",
                sa.Text(),
                nullable=False,
                server_default="chat",
            ),
        )
        batch_op.create_check_constraint(
            "conversation_kind_valid",
            "kind IN ('chat', 'browser')",
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("conversation_kind_valid", type_="check")
        batch_op.drop_column("kind")
