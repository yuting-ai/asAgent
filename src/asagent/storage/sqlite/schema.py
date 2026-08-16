from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
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
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "kind IN ('chat', 'browser')",
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
