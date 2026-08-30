from dataclasses import dataclass
from pathlib import Path

from asagent.core.conversation_file_scope import ConversationFileScope
from asagent.core.ids import ConversationId
from asagent.core.repositories import ConversationFileScopeRepository
from asagent.workspace.resolver import WorkspaceResolver


@dataclass(frozen=True, slots=True)
class WorkspaceSettingsStatus:
    conversation_id: ConversationId
    workspace_root: Path
    additional_roots: tuple[Path, ...]
    additional_files: tuple[Path, ...]


class ConversationWorkspaceSettings:
    """Validates and persists the external file scope of one conversation."""

    def __init__(
        self,
        *,
        scopes: ConversationFileScopeRepository,
        workspace_root: Path,
    ) -> None:
        self._scopes = scopes
        self._workspace_root = workspace_root

    async def get_status(
        self,
        conversation_id: ConversationId,
    ) -> WorkspaceSettingsStatus:
        saved_scope = await self._scopes.get(conversation_id)
        resolver = WorkspaceResolver(
            workspace_root=self._workspace_root,
            additional_roots=saved_scope.additional_roots,
            additional_files=saved_scope.additional_files,
        )
        return WorkspaceSettingsStatus(
            conversation_id=conversation_id,
            workspace_root=resolver.workspace_root,
            additional_roots=resolver.additional_roots,
            additional_files=resolver.additional_files,
        )

    async def model_context(self, conversation_id: ConversationId) -> str:
        """Describe user-selected paths for this Run without reading them."""

        status = await self.get_status(conversation_id)
        if not status.additional_roots and not status.additional_files:
            return ""

        lines = [
            "The user explicitly shared the following local paths for this "
            "conversation:",
            *(f"- Folder: {path}" for path in status.additional_roots),
            *(f"- File: {path}" for path in status.additional_files),
            "When the user refers to attached or shared folders or files without "
            "naming a specific path, inspect all relevant shared paths above using "
            "filesystem.list for folders, filesystem.read_file for UTF-8 text files, "
            "and document.extract_text for PDF files. If "
            "the user asks a question that applies to shared folders or files in "
            "general (e.g. counting files, listing contents, or searching), inspect "
            "each shared path and summarize the findings per path. Do not claim "
            "that a path is unavailable before using the relevant tool.",
        ]
        return "\n".join(lines)

    async def save(
        self,
        *,
        conversation_id: ConversationId,
        additional_roots: tuple[Path, ...],
        additional_files: tuple[Path, ...],
    ) -> WorkspaceSettingsStatus:
        resolver = WorkspaceResolver(
            workspace_root=self._workspace_root,
            additional_roots=additional_roots,
            additional_files=additional_files,
        )
        await self._scopes.save(
            ConversationFileScope(
                conversation_id=conversation_id,
                additional_roots=resolver.additional_roots,
                additional_files=resolver.additional_files,
            ),
        )
        return WorkspaceSettingsStatus(
            conversation_id=conversation_id,
            workspace_root=resolver.workspace_root,
            additional_roots=resolver.additional_roots,
            additional_files=resolver.additional_files,
        )
