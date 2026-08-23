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
        "kind IN ('chat', 'browser', 'automation_draft', 'automation_execution')",
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
