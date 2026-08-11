from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)


def test_openapi_declares_the_current_authenticated_v1_surface() -> None:
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=InMemoryConversationRepository(),
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
    )
    for path, method, success_status in expected_operations:
        operation = paths[path][method]

        assert operation["security"] == [{"HTTPBearer": []}]
        assert success_status in operation["responses"]

    assert "422" in paths["/api/v1/conversations"]["post"]["responses"]
