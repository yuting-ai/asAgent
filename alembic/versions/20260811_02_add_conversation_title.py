"""Add optional conversation titles.

Revision ID: 20260811_02
Revises: 20260809_01
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_02"
down_revision: str | None = "20260809_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("title", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "title")
