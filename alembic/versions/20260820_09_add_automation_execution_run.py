"""link automation executions to runs

Revision ID: 20260820_09
Revises: 20260820_08
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_09"
down_revision: str | None = "20260820_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("automation_executions") as batch_op:
        batch_op.add_column(sa.Column("run_id", sa.String()))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True)))
        batch_op.create_foreign_key(
            "automation_execution_run_id_fkey",
            "runs",
            ["run_id"],
            ["run_id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_constraint("automation_execution_status_valid", type_="check")
        batch_op.drop_constraint("automation_execution_run_id_fkey", type_="foreignkey")
        batch_op.create_check_constraint(
            "automation_execution_status_valid",
            "status IN ('claimed', 'missed', 'completed', 'failed', 'cancelled')",
        )


def downgrade() -> None:
    with op.batch_alter_table("automation_executions") as batch_op:
        batch_op.drop_constraint("automation_execution_status_valid", type_="check")
        batch_op.create_check_constraint(
            "automation_execution_status_valid", "status IN ('claimed', 'missed')"
        )
        batch_op.drop_column("completed_at")
        batch_op.drop_column("run_id")
