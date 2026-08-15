"""Add reversible file change metadata.

Revision ID: 20260815_05
Revises: 20260812_04
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260815_05"
down_revision: str | None = "20260812_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "file_changes",
        sa.Column("file_change_id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("before_hash", sa.String()),
        sa.Column("after_hash", sa.String()),
        sa.Column("snapshot_ref", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "operation IN ('create', 'replace', 'delete')",
            name="file_change_operation_valid",
        ),
        sa.CheckConstraint(
            "status IN ('prepared', 'applied', 'reverted', 'conflicted')",
            name="file_change_status_valid",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    op.drop_table("file_changes")
