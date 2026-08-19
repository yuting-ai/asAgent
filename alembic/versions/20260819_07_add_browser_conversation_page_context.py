"""add browser conversation page context

Revision ID: 20260819_07
Revises: 20260816_06
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_07"
down_revision: str | None = "20260816_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(sa.Column("last_page_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_page_title", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_column("last_page_title")
        batch_op.drop_column("last_page_url")
