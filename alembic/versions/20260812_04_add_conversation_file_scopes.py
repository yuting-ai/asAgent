"""Add per-conversation external file scopes.

Revision ID: 20260812_04
Revises: 20260812_03
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_04"
down_revision: str | None = "20260812_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_file_scopes",
        sa.Column("conversation_id", sa.String(), primary_key=True),
        sa.Column("additional_roots_json", sa.Text(), nullable=False),
        sa.Column("additional_files_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.conversation_id"],
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("conversation_file_scopes")
