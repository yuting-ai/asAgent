"""Create the initial persistent state schema.

Revision ID: 20260809_01
Revises:
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="message_sequence_positive"),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="message_role_valid"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.conversation_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "sequence",
            name="message_conversation_sequence",
        ),
    )
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.conversation_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "run_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="run_event_sequence_positive"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.run_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("run_id", "sequence", name="run_event_run_sequence"),
    )
    op.create_table(
        "tool_calls",
        sa.Column("tool_call_id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("model_call_id", sa.String(), nullable=False),
        sa.Column("tool_id", sa.String(), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("result", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "result IS NULL OR error IS NULL",
            name="tool_call_result_or_error",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.run_id"],
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("tool_calls")
    op.drop_table("run_events")
    op.drop_table("runs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")
