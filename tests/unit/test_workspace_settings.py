from pathlib import Path

import pytest

from asagent.core.conversation_file_scope import ConversationFileScope
from asagent.core.ids import ConversationId
from asagent.workspace.settings import ConversationWorkspaceSettings


class InMemoryConversationFileScopeRepository:
    def __init__(self) -> None:
        self._scopes: dict[ConversationId, ConversationFileScope] = {}

    async def get(self, conversation_id: ConversationId) -> ConversationFileScope:
        return self._scopes.get(
            conversation_id,
            ConversationFileScope(conversation_id=conversation_id),
        )

    async def save(self, scope: ConversationFileScope) -> None:
        self._scopes[scope.conversation_id] = scope


@pytest.mark.asyncio
async def test_conversation_workspace_settings_normalizes_selected_paths_per_conversation(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    selected_root = tmp_path / "selected"
    selected_file = tmp_path / "report.md"
    workspace_root.mkdir()
    selected_root.mkdir()
    selected_file.write_text("report", encoding="utf-8")
    settings = ConversationWorkspaceSettings(
        scopes=InMemoryConversationFileScopeRepository(),
        workspace_root=workspace_root,
    )
    conversation_id = ConversationId("conversation-1")

    saved = await settings.save(
        conversation_id=conversation_id,
        additional_roots=(selected_root / ".", selected_root),
        additional_files=(selected_file,),
    )

    assert saved.conversation_id == conversation_id
    assert saved.workspace_root == workspace_root.resolve()
    assert saved.additional_roots == (selected_root.resolve(),)
    assert saved.additional_files == (selected_file.resolve(),)
    assert await settings.get_status(conversation_id) == saved


@pytest.mark.asyncio
async def test_conversation_workspace_settings_keeps_scopes_isolated(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    selected_file = tmp_path / "report.md"
    workspace_root.mkdir()
    selected_file.write_text("report", encoding="utf-8")
    settings = ConversationWorkspaceSettings(
        scopes=InMemoryConversationFileScopeRepository(),
        workspace_root=workspace_root,
    )

    await settings.save(
        conversation_id=ConversationId("conversation-1"),
        additional_roots=(),
        additional_files=(selected_file,),
    )

    assert (
        await settings.get_status(ConversationId("conversation-2"))
    ).additional_files == ()


@pytest.mark.asyncio
async def test_conversation_workspace_settings_rejects_invalid_selected_paths(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    settings = ConversationWorkspaceSettings(
        scopes=InMemoryConversationFileScopeRepository(),
        workspace_root=workspace_root,
    )

    with pytest.raises(ValueError, match="additional_roots must exist"):
        await settings.save(
            conversation_id=ConversationId("conversation-1"),
            additional_roots=(tmp_path / "missing",),
            additional_files=(),
        )

    with pytest.raises(ValueError, match="additional_files must exist"):
        await settings.save(
            conversation_id=ConversationId("conversation-1"),
            additional_roots=(),
            additional_files=(tmp_path / "missing",),
        )


@pytest.mark.asyncio
async def test_conversation_workspace_settings_model_context(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    folder_a = tmp_path / "folder_a"
    folder_b = tmp_path / "folder_b"
    file_a = tmp_path / "file_a.txt"
    workspace_root.mkdir()
    folder_a.mkdir()
    folder_b.mkdir()
    file_a.write_text("hello", encoding="utf-8")

    settings = ConversationWorkspaceSettings(
        scopes=InMemoryConversationFileScopeRepository(),
        workspace_root=workspace_root,
    )
    conversation_id = ConversationId("conversation-1")

    # Empty context when no additional paths attached
    assert await settings.model_context(conversation_id) == ""

    # Context with multiple folders and files
    await settings.save(
        conversation_id=conversation_id,
        additional_roots=(folder_a, folder_b),
        additional_files=(file_a,),
    )
    context = await settings.model_context(conversation_id)
    assert f"- Folder: {folder_a.resolve()}" in context
    assert f"- Folder: {folder_b.resolve()}" in context
    assert f"- File: {file_a.resolve()}" in context
    assert "inspect all relevant shared paths above" in context
