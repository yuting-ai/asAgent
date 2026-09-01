"""Allow DOCX and HTML knowledge documents.

Revision ID: 20260901_13
Revises: 20260831_12
Create Date: 2026-09-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260901_13"
down_revision: str | None = "20260831_12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.drop_constraint("knowledge_document_file_type_valid", type_="check")
        batch_op.create_check_constraint(
            "knowledge_document_file_type_valid",
            "file_type IN ('pdf', 'markdown', 'text', 'docx', 'html')",
        )


def downgrade() -> None:
    op.execute(
        "UPDATE knowledge_documents "
        "SET file_type = 'text', status = 'unsupported' "
        "WHERE file_type IN ('docx', 'html')"
    )
    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.drop_constraint("knowledge_document_file_type_valid", type_="check")
        batch_op.create_check_constraint(
            "knowledge_document_file_type_valid",
            "file_type IN ('pdf', 'markdown', 'text')",
        )
