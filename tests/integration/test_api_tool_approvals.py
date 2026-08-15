import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.run_submission import RunSubmissionService
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ApprovalId, ConversationId, MessageId, RunId, UserId
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.core.tool_definition import ToolDefinition
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.tools.approval import PendingToolApprovalPolicy, ToolApprovalRequest


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.mark.asyncio
async def test_local_api_reads_and_decides_a_pending_tool_approval(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    now = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    conversation_id = ConversationId("conversation-1")
    run_id = RunId("run-1")
    request = ToolApprovalRequest(
        approval_id=ApprovalId("approval-1"),
        run_id=run_id,
        conversation_id=conversation_id,
        tool_call_id="call-1",
        definition=ToolDefinition(
            tool_id="mcp:test-server:add:1234",
            display_name="Add numbers",
            description="Add two numbers.",
            input_schema={"type": "object"},
            risk_level="medium",
            required_permissions=frozenset({"mcp.execute"}),
            requires_approval=True,
            timeout_seconds=10.0,
        ),
        arguments={"left": 2, "right": 3},
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    approvals = PendingToolApprovalPolicy()
    submission = RunSubmissionService(
        conversations=conversations,
        run_starter=starter,
        now=lambda: now,
        new_run_id=lambda: RunId("unused-run"),
        new_message_id=lambda: MessageId("unused-message"),
    )
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=submission,
        dispatch_submitted_run=lambda _: None,
        cancel_run=lambda _: False,
        tool_approvals=approvals,
    )
    waiting = asyncio.create_task(approvals.approve(request))
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(
            Conversation(
                conversation_id=conversation_id,
                user_id=UserId("local-user"),
                created_at=now,
                updated_at=now,
            ),
        )
        await runs.save(
            Run(
                run_id=run_id,
                conversation_id=conversation_id,
                status=RunStatus.EXECUTING_TOOLS,
                created_at=now,
                updated_at=now,
            ),
        )
        await asyncio.sleep(0)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            read = await client.get(
                "/api/v1/tool-approvals/approval-1",
                headers={"Authorization": "Bearer test-token"},
            )
            decided = await client.post(
                "/api/v1/tool-approvals/approval-1/decision",
                headers={"Authorization": "Bearer test-token"},
                json={"decision": "allow_once"},
            )

        assert read.status_code == 200
        assert read.json() == {
            "approval_id": "approval-1",
            "run_id": "run-1",
            "conversation_id": "conversation-1",
            "tool_call_id": "call-1",
            "tool_id": "mcp:test-server:add:1234",
            "display_name": "Add numbers",
            "description": "Add two numbers.",
            "arguments": {"left": 2, "right": 3},
            "resource_path": None,
            "impact_summary": None,
        }
        assert decided.status_code == 200
        assert decided.json() == {
            "approval_id": "approval-1",
            "decision": "allow_once",
        }
        assert await waiting is True
    finally:
        await approvals.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_file_write_approval_hides_content_and_exposes_exact_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    now = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
    conversation_id = ConversationId("conversation-1")
    run_id = RunId("run-1")
    request = ToolApprovalRequest(
        approval_id=ApprovalId("approval-file"),
        run_id=run_id,
        conversation_id=conversation_id,
        tool_call_id="call-file",
        definition=ToolDefinition(
            tool_id="filesystem.replace_file",
            display_name="Replace file",
            description="Replace a file.",
            input_schema={"type": "object"},
            risk_level="high",
            required_permissions=frozenset({"filesystem.write"}),
            requires_approval=True,
            timeout_seconds=10.0,
        ),
        arguments={"path": "/workspace/notes.txt", "content": "private body"},
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    approvals = PendingToolApprovalPolicy()
    submission = RunSubmissionService(
        conversations=conversations,
        run_starter=starter,
        now=lambda: now,
        new_run_id=lambda: RunId("unused-run"),
        new_message_id=lambda: MessageId("unused-message"),
    )
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=submission,
        dispatch_submitted_run=lambda _: None,
        cancel_run=lambda _: False,
        tool_approvals=approvals,
    )
    waiting = asyncio.create_task(approvals.approve(request))
    try:
        await conversations.save(
            Conversation(
                conversation_id,
                UserId("local-user"),
                now,
                now,
            )
        )
        await runs.save(
            Run(run_id, conversation_id, RunStatus.EXECUTING_TOOLS, now, now)
        )
        await asyncio.sleep(0)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/api/v1/tool-approvals/approval-file",
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["arguments"] == {"path": "/workspace/notes.txt"}
        assert payload["resource_path"] == "/workspace/notes.txt"
        assert payload["impact_summary"].startswith("Replace this UTF-8")
        assert "private body" not in response.text
    finally:
        approvals.deny_run(run_id)
        await waiting
        await approvals.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()
