"""Add knowledge libraries, sources, documents, chunks, and retrieval schema.

Revision ID: 20260831_12
Revises: 20260823_11
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_12"
down_revision: str | None = "20260823_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update conversations kind check constraint to include 'knowledge'
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("conversation_kind_valid", type_="check")
        batch_op.create_check_constraint(
            "conversation_kind_valid",
            "kind IN ('chat', 'browser', 'automation_draft', 'automation_execution', 'knowledge')",
        )

    # 2. Create knowledge_libraries table
    op.create_table(
        "knowledge_libraries",
        sa.Column("library_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("library_id"),
        sa.CheckConstraint(
            "status IN ('active', 'deleting')",
            name="knowledge_library_status_valid",
        ),
        sa.UniqueConstraint(
            "user_id",
            "normalized_name",
            name="knowledge_library_user_normalized_name_uniq",
        ),
    )

    # 3. Create knowledge_sources table
    op.create_table(
        "knowledge_sources",
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("library_id", sa.String(), nullable=False),
        sa.Column("display_path", sa.Text(), nullable=False),
        sa.Column("canonical_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scan_status", sa.String(), nullable=False),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["library_id"],
            ["knowledge_libraries.library_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_id"),
        sa.CheckConstraint(
            "status IN ('active', 'detached', 'missing', 'deleting')",
            name="knowledge_source_status_valid",
        ),
        sa.CheckConstraint(
            "scan_status IN ('idle', 'queued', 'scanning', 'indexing', 'ready', 'error')",
            name="knowledge_source_scan_status_valid",
        ),
        sa.UniqueConstraint(
            "library_id",
            "canonical_path",
            name="knowledge_source_library_canonical_path_uniq",
        ),
    )

    # 4. Create knowledge_documents table
    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("mtime_ns", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("parser_version", sa.String(), nullable=False),
        sa.Column("current_chunker_version", sa.String(), nullable=False),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.source_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("document_id"),
        sa.CheckConstraint(
            "file_type IN ('pdf', 'markdown', 'text')",
            name="knowledge_document_file_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'missing', 'unsupported', 'parse_error')",
            name="knowledge_document_status_valid",
        ),
        sa.UniqueConstraint(
            "source_id",
            "relative_path",
            name="knowledge_document_source_relative_path_uniq",
        ),
    )

    # 5. Create knowledge_chunks table
    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("document_content_hash", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("chunker_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.document_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("chunk_id"),
        sa.CheckConstraint(
            "status IN ('active', 'superseded')",
            name="knowledge_chunk_status_valid",
        ),
        sa.CheckConstraint(
            "chunk_index >= 0", name="knowledge_chunk_index_nonnegative"
        ),
    )

    # 6. Create knowledge_index_profiles table
    op.create_table(
        "knowledge_index_profiles",
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("embedding_revision", sa.String(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("embedding_normalized", sa.Integer(), nullable=False),
        sa.Column("chunker_version", sa.String(), nullable=False),
        sa.Column("qdrant_collection", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("profile_id"),
        sa.CheckConstraint(
            "status IN ('building', 'active', 'retired', 'failed')",
            name="knowledge_index_profile_status_valid",
        ),
        sa.CheckConstraint(
            "embedding_normalized IN (0, 1)",
            name="knowledge_profile_normalized_valid",
        ),
    )

    # 7. Create knowledge_chunk_embeddings table
    op.create_table(
        "knowledge_chunk_embeddings",
        sa.Column("chunk_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("point_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["knowledge_chunks.chunk_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["knowledge_index_profiles.profile_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("chunk_id", "profile_id"),
        sa.CheckConstraint(
            "status IN ('pending', 'embedding', 'indexed', 'error', 'deleting')",
            name="knowledge_chunk_embedding_status_valid",
        ),
    )

    # 8. Create knowledge_index_jobs table
    op.create_table(
        "knowledge_index_jobs",
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("library_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "discovered_files",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("processed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cancel_requested",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["library_id"],
            ["knowledge_libraries.library_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.source_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("job_id"),
        sa.CheckConstraint(
            "kind IN ('initial', 'rescan', 'reactivate', 'rebuild', 'delete')",
            name="knowledge_index_job_kind_valid",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')",
            name="knowledge_index_job_status_valid",
        ),
        sa.CheckConstraint(
            "cancel_requested IN (0, 1)",
            name="knowledge_index_job_cancel_requested_valid",
        ),
    )

    # 9. Create knowledge_retrieval_hits table
    op.create_table(
        "knowledge_retrieval_hits",
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("citation_label", sa.String(), nullable=False),
        sa.Column("document_name_snapshot", sa.Text(), nullable=False),
        sa.Column("source_path_snapshot", sa.Text(), nullable=False),
        sa.Column("page_start_snapshot", sa.Integer(), nullable=True),
        sa.Column("page_end_snapshot", sa.Integer(), nullable=True),
        sa.Column("section_title_snapshot", sa.Text(), nullable=True),
        sa.Column("content_hash_snapshot", sa.String(), nullable=False),
        sa.Column("snippet_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["knowledge_chunks.chunk_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["knowledge_index_profiles.profile_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", "rank"),
        sa.CheckConstraint("rank >= 1", name="knowledge_retrieval_hit_rank_positive"),
    )

    # 10. Create knowledge_conversations table
    op.create_table(
        "knowledge_conversations",
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("library_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.conversation_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["library_id"],
            ["knowledge_libraries.library_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("conversation_id"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_conversations")
    op.drop_table("knowledge_retrieval_hits")
    op.drop_table("knowledge_index_jobs")
    op.drop_table("knowledge_chunk_embeddings")
    op.drop_table("knowledge_index_profiles")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_sources")
    op.drop_table("knowledge_libraries")

    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("conversation_kind_valid", type_="check")
        batch_op.create_check_constraint(
            "conversation_kind_valid",
            "kind IN ('chat', 'browser', 'automation_draft', 'automation_execution')",
        )
