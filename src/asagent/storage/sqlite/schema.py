from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

automations = Table(
    "automations",
    metadata,
    Column("automation_id", String, primary_key=True),
    Column(
        "user_id",
        String,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", String, nullable=False),
    Column("plan_summary", Text, nullable=False),
    Column("allowed_capabilities_json", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('draft', 'active', 'paused')", name="automation_status_valid"
    ),
)

automation_triggers = Table(
    "automation_triggers",
    metadata,
    Column("automation_trigger_id", String, primary_key=True),
    Column(
        "automation_id",
        String,
        ForeignKey("automations.automation_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("kind", String, nullable=False),
    Column("timezone", String, nullable=False),
    Column("local_time", String, nullable=False),
    Column("weekday", Integer),
    Column("next_run_at", DateTime(timezone=True)),
    Column("enabled", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "kind IN ('once', 'daily', 'weekly')", name="automation_trigger_kind_valid"
    ),
    CheckConstraint("enabled IN (0, 1)", name="automation_trigger_enabled_valid"),
    CheckConstraint(
        "(kind = 'weekly' AND weekday BETWEEN 0 AND 6) "
        "OR (kind != 'weekly' AND weekday IS NULL)",
        name="automation_trigger_weekday_valid",
    ),
)

automation_executions = Table(
    "automation_executions",
    metadata,
    Column("automation_execution_id", String, primary_key=True),
    Column(
        "automation_id",
        String,
        ForeignKey("automations.automation_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "automation_trigger_id",
        String,
        ForeignKey("automation_triggers.automation_trigger_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("scheduled_for", DateTime(timezone=True), nullable=False),
    Column("status", String, nullable=False),
    Column("claimed_at", DateTime(timezone=True), nullable=False),
    Column(
        "run_id",
        String,
        ForeignKey(
            "runs.run_id",
            name="automation_execution_run_id_fkey",
            ondelete="RESTRICT",
        ),
    ),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        "status IN ('claimed', 'missed', 'completed', 'failed', 'cancelled')",
        name="automation_execution_status_valid",
    ),
    UniqueConstraint(
        "automation_trigger_id",
        "scheduled_for",
        name="automation_execution_trigger_scheduled_for",
    ),
)

conversations = Table(
    "conversations",
    metadata,
    Column("conversation_id", String, primary_key=True),
    Column(
        "user_id",
        String,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("title", String),
    Column("kind", Text, nullable=False, server_default="chat"),
    Column("last_page_url", Text),
    Column("last_page_title", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "kind IN ('chat', 'browser', 'automation_draft', 'automation_execution', 'knowledge')",
        name="conversation_kind_valid",
    ),
)

conversation_file_scopes = Table(
    "conversation_file_scopes",
    metadata,
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.conversation_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("additional_roots_json", Text, nullable=False),
    Column("additional_files_json", Text, nullable=False),
)

messages = Table(
    "messages",
    metadata,
    Column("message_id", String, primary_key=True),
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.conversation_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("sequence", Integer, nullable=False),
    Column("role", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("sequence >= 1", name="message_sequence_positive"),
    CheckConstraint("role IN ('user', 'assistant')", name="message_role_valid"),
    UniqueConstraint(
        "conversation_id", "sequence", name="message_conversation_sequence"
    ),
)

runs = Table(
    "runs",
    metadata,
    Column("run_id", String, primary_key=True),
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.conversation_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

run_events = Table(
    "run_events",
    metadata,
    Column("event_id", String, primary_key=True),
    Column(
        "run_id",
        String,
        ForeignKey("runs.run_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("sequence", Integer, nullable=False),
    Column("event_type", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("data_json", Text, nullable=False),
    CheckConstraint("sequence >= 1", name="run_event_sequence_positive"),
    UniqueConstraint("run_id", "sequence", name="run_event_run_sequence"),
)

connections = Table(
    "connections",
    metadata,
    Column("connection_id", String, primary_key=True),
    Column(
        "user_id",
        String,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("service_id", String, nullable=False),
    Column("account_label", String, nullable=False),
    Column("granted_scopes_json", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('active', 'reauthentication_required')",
        name="connection_status_valid",
    ),
)

tool_calls = Table(
    "tool_calls",
    metadata,
    Column("tool_call_id", String, primary_key=True),
    Column(
        "run_id",
        String,
        ForeignKey("runs.run_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("model_call_id", String, nullable=False),
    Column("tool_id", String, nullable=False),
    Column("arguments_json", Text, nullable=False),
    Column("result", Text),
    Column("error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        "result IS NULL OR error IS NULL",
        name="tool_call_result_or_error",
    ),
)

file_changes = Table(
    "file_changes",
    metadata,
    Column("file_change_id", String, primary_key=True),
    Column(
        "run_id", String, ForeignKey("runs.run_id", ondelete="RESTRICT"), nullable=False
    ),
    Column("operation", String, nullable=False),
    Column("status", String, nullable=False),
    Column("root_path", Text, nullable=False),
    Column("relative_path", Text, nullable=False),
    Column("before_hash", String),
    Column("after_hash", String),
    Column("snapshot_ref", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "operation IN ('create', 'replace', 'delete')",
        name="file_change_operation_valid",
    ),
    CheckConstraint(
        "status IN ('prepared', 'applied', 'reverted', 'conflicted')",
        name="file_change_status_valid",
    ),
)

knowledge_libraries = Table(
    "knowledge_libraries",
    metadata,
    Column("library_id", String, primary_key=True),
    Column(
        "user_id",
        String,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", String, nullable=False),
    Column("normalized_name", String, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('active', 'deleting')",
        name="knowledge_library_status_valid",
    ),
    UniqueConstraint(
        "user_id", "normalized_name", name="knowledge_library_user_normalized_name_uniq"
    ),
)

knowledge_sources = Table(
    "knowledge_sources",
    metadata,
    Column("source_id", String, primary_key=True),
    Column(
        "library_id",
        String,
        ForeignKey("knowledge_libraries.library_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("display_path", Text, nullable=False),
    Column("canonical_path", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("scan_status", String, nullable=False),
    Column("last_scanned_at", DateTime(timezone=True)),
    Column("detached_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('active', 'detached', 'missing', 'deleting')",
        name="knowledge_source_status_valid",
    ),
    CheckConstraint(
        "scan_status IN ('idle', 'queued', 'scanning', 'indexing', 'ready', 'error')",
        name="knowledge_source_scan_status_valid",
    ),
    UniqueConstraint(
        "library_id",
        "canonical_path",
        name="knowledge_source_library_canonical_path_uniq",
    ),
)

knowledge_documents = Table(
    "knowledge_documents",
    metadata,
    Column("document_id", String, primary_key=True),
    Column(
        "source_id",
        String,
        ForeignKey("knowledge_sources.source_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("relative_path", Text, nullable=False),
    Column("file_type", String, nullable=False),
    Column("status", String, nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("mtime_ns", Integer, nullable=False),
    Column("content_hash", String, nullable=False),
    Column("parser_version", String, nullable=False),
    Column("current_chunker_version", String, nullable=False),
    Column("last_indexed_at", DateTime(timezone=True)),
    Column("last_error_code", String),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "file_type IN ('pdf', 'markdown', 'text', 'docx', 'html')",
        name="knowledge_document_file_type_valid",
    ),
    CheckConstraint(
        "status IN ('active', 'missing', 'unsupported', 'parse_error')",
        name="knowledge_document_status_valid",
    ),
    UniqueConstraint(
        "source_id",
        "relative_path",
        name="knowledge_document_source_relative_path_uniq",
    ),
)

knowledge_chunks = Table(
    "knowledge_chunks",
    metadata,
    Column("chunk_id", String, primary_key=True),
    Column(
        "document_id",
        String,
        ForeignKey("knowledge_documents.document_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("document_content_hash", String, nullable=False),
    Column("chunk_index", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("token_count", Integer, nullable=False),
    Column("page_start", Integer),
    Column("page_end", Integer),
    Column("section_title", Text),
    Column("content_hash", String, nullable=False),
    Column("chunker_version", String, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("superseded_at", DateTime(timezone=True)),
    CheckConstraint(
        "status IN ('active', 'superseded')",
        name="knowledge_chunk_status_valid",
    ),
    CheckConstraint(
        "chunk_index >= 0",
        name="knowledge_chunk_index_nonnegative",
    ),
)

knowledge_index_profiles = Table(
    "knowledge_index_profiles",
    metadata,
    Column("profile_id", String, primary_key=True),
    Column("embedding_model", String, nullable=False),
    Column("embedding_revision", String, nullable=False),
    Column("embedding_dimension", Integer, nullable=False),
    Column("embedding_normalized", Integer, nullable=False),
    Column("chunker_version", String, nullable=False),
    Column("qdrant_collection", String, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("activated_at", DateTime(timezone=True)),
    CheckConstraint(
        "status IN ('building', 'active', 'retired', 'failed')",
        name="knowledge_index_profile_status_valid",
    ),
    CheckConstraint(
        "embedding_normalized IN (0, 1)",
        name="knowledge_profile_normalized_valid",
    ),
)

knowledge_chunk_embeddings = Table(
    "knowledge_chunk_embeddings",
    metadata,
    Column(
        "chunk_id",
        String,
        ForeignKey("knowledge_chunks.chunk_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "profile_id",
        String,
        ForeignKey("knowledge_index_profiles.profile_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("point_id", String, nullable=False),
    Column("status", String, nullable=False),
    Column("retry_count", Integer, nullable=False, server_default="0"),
    Column("last_error_code", String),
    Column("indexed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('pending', 'embedding', 'indexed', 'error', 'deleting')",
        name="knowledge_chunk_embedding_status_valid",
    ),
)

knowledge_index_jobs = Table(
    "knowledge_index_jobs",
    metadata,
    Column("job_id", String, primary_key=True),
    Column(
        "library_id",
        String,
        ForeignKey("knowledge_libraries.library_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "source_id",
        String,
        ForeignKey("knowledge_sources.source_id", ondelete="RESTRICT"),
    ),
    Column("kind", String, nullable=False),
    Column("status", String, nullable=False),
    Column("discovered_files", Integer, nullable=False, server_default="0"),
    Column("processed_files", Integer, nullable=False, server_default="0"),
    Column("skipped_files", Integer, nullable=False, server_default="0"),
    Column("failed_files", Integer, nullable=False, server_default="0"),
    Column("total_chunks", Integer, nullable=False, server_default="0"),
    Column("indexed_chunks", Integer, nullable=False, server_default="0"),
    Column("cancel_requested", Integer, nullable=False, server_default="0"),
    Column("last_error_code", String),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint(
        "kind IN ('initial', 'rescan', 'reactivate', 'rebuild', 'delete')",
        name="knowledge_index_job_kind_valid",
    ),
    CheckConstraint(
        "status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')",
        name="knowledge_index_job_status_valid",
    ),
    CheckConstraint(
        "cancel_requested IN (0, 1)",
        name="knowledge_index_job_cancel_requested_valid",
    ),
)

knowledge_retrieval_hits = Table(
    "knowledge_retrieval_hits",
    metadata,
    Column(
        "run_id",
        String,
        ForeignKey("runs.run_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("rank", Integer, primary_key=True),
    Column(
        "chunk_id",
        String,
        ForeignKey("knowledge_chunks.chunk_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "profile_id",
        String,
        ForeignKey("knowledge_index_profiles.profile_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("score", Float, nullable=False),
    Column("citation_label", String, nullable=False),
    Column("document_name_snapshot", Text, nullable=False),
    Column("source_path_snapshot", Text, nullable=False),
    Column("page_start_snapshot", Integer),
    Column("page_end_snapshot", Integer),
    Column("section_title_snapshot", Text),
    Column("content_hash_snapshot", String, nullable=False),
    Column("snippet_snapshot", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "rank >= 1",
        name="knowledge_retrieval_hit_rank_positive",
    ),
)

knowledge_conversations = Table(
    "knowledge_conversations",
    metadata,
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.conversation_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "library_id",
        String,
        ForeignKey("knowledge_libraries.library_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
