from datetime import UTC, datetime

from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.ids import MessageId, RunId
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)


class UnusedRunStarter:
    async def start(
        self,
        *,
        user_message: UserMessage,
        run: Run,
    ) -> None:
        del user_message, run
        raise AssertionError("run submission is not used by this test")


def _discard_submission(submission: SubmittedRun) -> None:
    del submission


def test_openapi_declares_the_current_authenticated_v1_surface() -> None:
    conversations = InMemoryConversationRepository()
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=UnusedRunStarter(),
            now=lambda: datetime(2026, 8, 11, tzinfo=UTC),
            new_run_id=lambda: RunId("unused-run"),
            new_message_id=lambda: MessageId("unused-message"),
        ),
        dispatch_submitted_run=_discard_submission,
    )

    schema = app.openapi()

    assert schema["info"] == {
        "title": "asAgent Local API",
        "version": "0.1.0",
    }
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }

    paths = schema["paths"]
    assert set(paths) == {
        "/api/v1/health",
        "/api/v1/conversations",
        "/api/v1/conversations/{conversation_id}/messages",
    }

    expected_operations = (
        ("/api/v1/health", "get", "200"),
        ("/api/v1/conversations", "get", "200"),
        ("/api/v1/conversations", "post", "201"),
        ("/api/v1/conversations/{conversation_id}/messages", "get", "200"),
        (
            "/api/v1/conversations/{conversation_id}/messages",
            "post",
            "201",
        ),
    )
    for path, method, success_status in expected_operations:
        operation = paths[path][method]

        assert operation["security"] == [{"HTTPBearer": []}]
        assert success_status in operation["responses"]

    assert "422" in paths["/api/v1/conversations"]["post"]["responses"]
    assert (
        "422"
        in paths["/api/v1/conversations/{conversation_id}/messages"]["post"][
            "responses"
        ]
    )
