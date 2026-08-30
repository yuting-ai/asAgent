import asyncio
import io
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import httpx
import pypdf
import pytest
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from asagent.bootstrap.browser_page_bridge import BrowserPageBridgeClient
from asagent.tools.browser_read_current_pdf import BrowserReadCurrentPdfTool
from asagent.tools.errors import ToolOperationError, ToolTimeoutError


def _make_pdf(pages_text: list[str]) -> bytes:
    writer = pypdf.PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for text in pages_text:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        escaped_text = (
            text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
        stream.set_data(
            f"BT /F1 12 Tf 50 250 Td ({escaped_text}) Tj ET".encode(
                "latin1", errors="replace"
            )
        )
        page[NameObject("/Contents")] = stream

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class _FakeTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        handler: Callable[[httpx.Request], httpx.Response] | None = None,
    ) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.handler is not None:
            return self.handler(request)
        return httpx.Response(200, json={}, request=request)


def test_browser_read_current_pdf_definition() -> None:
    tool = BrowserReadCurrentPdfTool(
        client=BrowserPageBridgeClient(
            base_url="http://127.0.0.1:43124",
            token="bridge-token",
        ),
        tab_id="tab-1",
    )

    defn = tool.definition
    assert defn.tool_id == "browser.read_current_pdf"
    assert defn.display_name == "Read current PDF"
    assert defn.required_permissions == frozenset({"browser.read"})
    assert defn.requires_approval is False
    assert defn.timeout_seconds == 40.0
    assert defn.risk_level == "low"
    properties = defn.input_schema.get("properties")
    assert isinstance(properties, dict)
    assert "start_page" in properties
    assert "start_char_offset" in properties
    assert "end_page" in properties
    assert defn.input_schema["additionalProperties"] is False


@pytest.mark.asyncio
async def test_browser_read_current_pdf_rejects_invalid_arguments() -> None:
    tool = BrowserReadCurrentPdfTool(
        client=BrowserPageBridgeClient(
            base_url="http://127.0.0.1:43124",
            token="bridge-token",
        ),
        tab_id="tab-1",
    )

    with pytest.raises(
        ValueError,
        match="start_page must be an integer greater than or equal to 1",
    ):
        await tool.execute({"start_page": 0})

    with pytest.raises(
        ValueError,
        match="start_char_offset must be an integer greater than or equal to 0",
    ):
        await tool.execute({"start_char_offset": -1})

    with pytest.raises(ValueError, match="start_page must not exceed end_page"):
        await tool.execute({"start_page": 5, "end_page": 4})

    with pytest.raises(ValueError, match="a single call may extract at most 10 pages"):
        await tool.execute({"start_page": 1, "end_page": 11})


@pytest.mark.asyncio
async def test_browser_read_current_pdf_run_level_caching_and_pagination() -> None:
    pdf_bytes = _make_pdf(
        [
            "Page 1 Intro",
            "Page 2 Details",
            "Page 3 Analysis",
            "Page 4 Discussion",
            "Page 5 Conclusion",
            "Page 6 Appendix",
        ]
    )

    transport = _FakeTransport(
        handler=lambda req: (
            httpx.Response(200, json={"document_id": "doc-token-123"}, request=req)
            if req.url.path == "/validate-current-pdf"
            else httpx.Response(
                200,
                content=pdf_bytes,
                headers={
                    "Content-Type": "application/pdf",
                    "X-Document-Id": "doc-token-123",
                },
                request=req,
            )
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserReadCurrentPdfTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )

        # First call: reads pages 1 to 2
        result_raw_1 = await tool.execute({"start_page": 1, "end_page": 2})
        result_1 = json.loads(result_raw_1)
        assert result_1["start_page"] == 1
        assert result_1["end_page"] == 2
        assert len(result_1["pages"]) == 2
        assert result_1["pages"][0]["text"] == "Page 1 Intro"
        assert result_1["pages"][1]["text"] == "Page 2 Details"
        assert result_1["next_position"] == {"page": 3, "char_offset": 0}
        assert len(transport.requests) == 2  # Fetch plus post-extraction validation.

        # Second call: uses next_position to read pages 3 to 4
        next_pos = result_1["next_position"]
        result_raw_2 = await tool.execute(
            {
                "start_page": next_pos["page"],
                "start_char_offset": next_pos["char_offset"],
                "end_page": 4,
            }
        )
        result_2 = json.loads(result_raw_2)
        assert result_2["start_page"] == 3
        assert result_2["end_page"] == 4
        assert len(result_2["pages"]) == 2
        assert result_2["pages"][0]["text"] == "Page 3 Analysis"
        assert result_2["pages"][1]["text"] == "Page 4 Discussion"
        assert result_2["next_position"] == {"page": 5, "char_offset": 0}

        # Only the PDF bytes are fetched once; validation stays live on each call.
        assert (
            sum(req.url.path == "/read-current-pdf" for req in transport.requests) == 1
        )
        validations = [
            req for req in transport.requests if req.url.path == "/validate-current-pdf"
        ]
        assert len(validations) == 3
        assert all(
            json.loads(req.content)
            == {"tab_id": "tab-1", "document_id": "doc-token-123"}
            for req in validations
        )

        # Verify request details
        req = transport.requests[0]
        assert req.headers["Authorization"] == "Bearer bridge-token"
        assert req.url.path == "/read-current-pdf"
        assert json.loads(req.content.decode("utf-8")) == {"tab_id": "tab-1"}


@pytest.mark.asyncio
async def test_browser_read_current_pdf_handles_bridge_error() -> None:
    transport = _FakeTransport(
        handler=lambda req: httpx.Response(
            401,
            json={"detail": "invalid browser page bridge credentials"},
            request=req,
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserReadCurrentPdfTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="invalid-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )

        with pytest.raises(ValueError, match="current browser tab is not visible"):
            await tool.execute({})


@pytest.mark.asyncio
async def test_browser_read_current_pdf_handles_safe_operation_errors() -> None:
    transport = _FakeTransport(
        handler=lambda req: httpx.Response(
            409,
            json={"detail": "PDF exceeds the 20 MiB limit"},
            request=req,
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserReadCurrentPdfTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )

        with pytest.raises(ToolOperationError, match="PDF exceeds the 20 MiB limit"):
            await tool.execute({})


@pytest.mark.asyncio
async def test_browser_read_current_pdf_handles_invalid_pdf_data() -> None:
    transport = _FakeTransport(
        handler=lambda req: httpx.Response(
            200,
            content=b"%PDF-1.4 but corrupted content without valid xref %%EOF",
            headers={
                "Content-Type": "application/pdf",
                "X-Document-Id": "doc-corrupted",
            },
            request=req,
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserReadCurrentPdfTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )

        with pytest.raises(ValueError, match="PDF is invalid or corrupted"):
            await tool.execute({})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "detail",
    [
        "current browser tab is not visible",
        "PDF document changed; start a new browser run",
    ],
)
async def test_cached_pdf_is_rejected_after_tab_or_document_changes(
    detail: str,
) -> None:
    valid = True
    fetch_count = 0
    pdf_bytes = _make_pdf(["First", "Second"])

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetch_count
        if request.url.path == "/validate-current-pdf":
            return (
                httpx.Response(200, json={"document_id": "doc-original"})
                if valid
                else httpx.Response(409, json={"detail": detail})
            )
        fetch_count += 1
        return httpx.Response(
            200, content=pdf_bytes, headers={"x-document-id": "doc-original"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        tool = BrowserReadCurrentPdfTool(
            client=BrowserPageBridgeClient(
                base_url="http://bridge.test", token="test-token", http_client=client
            ),
            tab_id="tab-1",
        )
        await tool.execute({"end_page": 1})
        valid = False
        with pytest.raises(ToolOperationError, match=detail):
            await tool.execute({"start_page": 2})
        assert tool._cached_pdf_bytes is None
        # A retry must not silently refetch a different document with the old cursor.
        with pytest.raises(ToolOperationError, match="PDF document changed"):
            await tool.execute({"start_page": 2})
        assert fetch_count == 1


@pytest.mark.asyncio
async def test_document_change_during_extraction_discards_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid = True

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/validate-current-pdf":
            return (
                httpx.Response(200, json={"document_id": "doc-original"})
                if valid
                else httpx.Response(
                    409,
                    json={"detail": "PDF document changed; start a new browser run"},
                )
            )
        return httpx.Response(
            200,
            content=_make_pdf(["Old document"]),
            headers={"x-document-id": "doc-original"},
        )

    def extract(*_args: object) -> str:
        nonlocal valid
        valid = False
        return "old document result"

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        tool = BrowserReadCurrentPdfTool(
            client=BrowserPageBridgeClient(
                base_url="http://bridge.test", token="test-token", http_client=client
            ),
            tab_id="tab-1",
        )
        monkeypatch.setattr(tool, "_extract_sync", extract)
        with pytest.raises(ToolOperationError, match="PDF document changed"):
            await tool.execute({})
        assert tool._cached_pdf_bytes is None


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_parse_timeout_or_cancellation_releases_snapshot(
    monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    from asagent.tools import browser_read_current_pdf

    started, release, finished = Event(), Event(), Event()

    def extract(*_args: object) -> str:
        started.set()
        try:
            release.wait(timeout=2)
            return "result"
        finally:
            finished.set()

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=b"fixture", headers={"x-document-id": "doc-original"}
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserReadCurrentPdfTool(
            client=BrowserPageBridgeClient(
                base_url="http://bridge.test", token="test-token", http_client=client
            ),
            tab_id="tab-1",
        )
        monkeypatch.setattr(tool, "_extract_sync", extract)
        monkeypatch.setattr(
            browser_read_current_pdf, "_PARSE_TIMEOUT_SECONDS", 1.0 if cancel else 0.05
        )
        pending = asyncio.create_task(tool.execute({}))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            if cancel:
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            else:
                with pytest.raises(
                    ToolTimeoutError, match="PDF text extraction timed out"
                ):
                    await pending
            assert tool._cached_pdf_bytes is None
        finally:
            release.set()
            assert await asyncio.to_thread(finished.wait, 1)


class _InMemoryScopes:
    async def get(self, conversation_id: object) -> object:
        from asagent.core.conversation_file_scope import ConversationFileScope
        from asagent.core.ids import ConversationId

        return ConversationFileScope(
            conversation_id=ConversationId(str(conversation_id))
        )

    async def save(self, scope: object) -> None:
        del scope


@pytest.mark.asyncio
async def test_browser_system_prompt_includes_pdf_instructions(
    tmp_path: Path,
) -> None:
    from asagent.cli import _system_prompt_for_conversation
    from asagent.core.conversation import Conversation
    from asagent.core.ids import ConversationId, UserId
    from asagent.storage.in_memory_conversation_repository import (
        InMemoryConversationRepository,
    )
    from asagent.workspace.settings import ConversationWorkspaceSettings

    now = datetime(2026, 8, 30, tzinfo=UTC)
    conversations = InMemoryConversationRepository()
    chat_conv = Conversation(
        conversation_id=ConversationId("chat-1"),
        user_id=UserId("local-user"),
        created_at=now,
        updated_at=now,
        kind="chat",
    )
    browser_conv = Conversation(
        conversation_id=ConversationId("browser-1"),
        user_id=UserId("local-user"),
        created_at=now,
        updated_at=now,
        kind="browser",
    )
    await conversations.save(chat_conv)
    await conversations.save(browser_conv)

    workspace_settings = ConversationWorkspaceSettings(
        scopes=_InMemoryScopes(),  # type: ignore[arg-type]
        workspace_root=tmp_path,
    )

    chat_prompt = await _system_prompt_for_conversation(
        workspace_settings=workspace_settings,
        conversations=conversations,
        conversation_id=chat_conv.conversation_id,
    )
    assert "browser.read_current_pdf" not in chat_prompt

    browser_prompt = await _system_prompt_for_conversation(
        workspace_settings=workspace_settings,
        conversations=conversations,
        conversation_id=browser_conv.conversation_id,
    )
    assert "browser.read_current_pdf" in browser_prompt


@pytest.mark.asyncio
async def test_browser_read_current_pdf_in_agent_loop() -> None:
    from asagent.agent.loop import AgentLoop
    from asagent.cli import _register_browser_tools
    from asagent.core.conversation import Conversation
    from asagent.core.ids import ConversationId, RunId, UserId
    from asagent.models.contracts import (
        ModelMessage,
        ModelMessageRole,
        ModelResponse,
        ModelToolCall,
    )
    from asagent.models.fake_provider import FakeModelProvider
    from asagent.models.tool_names import openai_compatible_tool_name
    from asagent.storage.in_memory_conversation_repository import (
        InMemoryConversationRepository,
    )
    from asagent.tools.browser_run_bindings import BrowserRunBindings
    from asagent.tools.executor import ToolExecutor
    from asagent.tools.registry import ToolRegistry
    from asagent.tools.snapshot import ToolSnapshot

    pdf_bytes = _make_pdf(
        ["Quarterly Report Page 1: Revenue grew 20%.", "Page 2: Summary."]
    )
    transport = _FakeTransport(
        handler=lambda req: (
            httpx.Response(200, json={"document_id": "doc-token-777"}, request=req)
            if req.url.path == "/validate-current-pdf"
            else httpx.Response(
                200,
                content=pdf_bytes,
                headers={
                    "Content-Type": "application/pdf",
                    "X-Document-Id": "doc-token-777",
                },
                request=req,
            )
        )
    )

    now = datetime(2026, 8, 30, tzinfo=UTC)
    conversations = InMemoryConversationRepository()
    browser_conv = Conversation(
        conversation_id=ConversationId("browser-e2e"),
        user_id=UserId("local-user"),
        created_at=now,
        updated_at=now,
        kind="browser",
    )
    await conversations.save(browser_conv)

    bindings = BrowserRunBindings()
    run_id = RunId("run-pdf-e2e")
    bindings.bind(run_id, "tab-pdf")

    async with httpx.AsyncClient(transport=transport) as client:
        bridge_client = BrowserPageBridgeClient(
            base_url="http://127.0.0.1:43124",
            token="bridge-token",
            http_client=client,
        )

        registry = ToolRegistry()
        granted = await _register_browser_tools(
            registry=registry,
            conversations=conversations,
            conversation_id=browser_conv.conversation_id,
            run_id=run_id,
            browser_run_bindings=bindings,
            browser_page_client=bridge_client,
        )

        provider = FakeModelProvider(
            responses=(
                ModelResponse(
                    text=None,
                    tool_calls=(
                        ModelToolCall(
                            call_id="call-pdf-read",
                            name="browser_read_current_pdf",
                            arguments={"start_page": 1, "end_page": 1},
                        ),
                    ),
                ),
                ModelResponse(
                    text="The quarterly revenue grew by 20%.",
                    tool_calls=(),
                ),
            ),
        )

        snapshot = ToolSnapshot.from_definitions(
            registry.definitions(),
            provider_name_for=openai_compatible_tool_name,
        )
        executor = ToolExecutor(
            registry,
            granted_permissions=granted,
        )
        agent_loop = AgentLoop(
            model=provider,
            executor=executor,
            tool_snapshot=snapshot,
        )

        result = await agent_loop.run(
            model_name="fake-model",
            system_prompt="Use tools.",
            messages=(
                ModelMessage(
                    role=ModelMessageRole.USER,
                    content="Summarize the open PDF.",
                ),
            ),
        )

        assert result.text == "The quarterly revenue grew by 20%."
        assert len(provider.requests) == 2
        tool_reply_msg = provider.requests[1].messages[-1]
        assert tool_reply_msg.role is ModelMessageRole.TOOL
        assert tool_reply_msg.content is not None
        parsed_payload = json.loads(tool_reply_msg.content)
        assert (
            parsed_payload["pages"][0]["text"]
            == "Quarterly Report Page 1: Revenue grew 20%."
        )
