"""add automation persistence

Revision ID: 20260820_08
Revises: 20260819_07
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_08"
down_revision: str | None = "20260819_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automations",
        sa.Column("automation_id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("plan_summary", sa.Text(), nullable=False),
        sa.Column("allowed_capabilities_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'paused')", name="automation_status_valid"
        ),
    )
    op.create_table(
        "automation_triggers",
        sa.Column("automation_trigger_id", sa.String(), primary_key=True),
        sa.Column(
            "automation_id",
            sa.String(),
            sa.ForeignKey("automations.automation_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("local_time", sa.String(), nullable=False),
        sa.Column("weekday", sa.Integer()),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('once', 'daily', 'weekly')", name="automation_trigger_kind_valid"
        ),
        sa.CheckConstraint(
            "enabled IN (0, 1)", name="automation_trigger_enabled_valid"
        ),
        sa.CheckConstraint(
            "(kind = 'weekly' AND weekday BETWEEN 0 AND 6) OR (kind != 'weekly' AND weekday IS NULL)",
            name="automation_trigger_weekday_valid",
        ),
    )
    op.create_table(
        "automation_executions",
        sa.Column("automation_execution_id", sa.String(), primary_key=True),
        sa.Column(
            "automation_id",
            sa.String(),
            sa.ForeignKey("automations.automation_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "automation_trigger_id",
            sa.String(),
            sa.ForeignKey(
                "automation_triggers.automation_trigger_id", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('claimed', 'missed')", name="automation_execution_status_valid"
        ),
        sa.UniqueConstraint(
            "automation_trigger_id",
            "scheduled_for",
            name="automation_execution_trigger_scheduled_for",
        ),
    )


def downgrade() -> None:
    op.drop_table("automation_executions")
    op.drop_table("automation_triggers")
    op.drop_table("automations")
