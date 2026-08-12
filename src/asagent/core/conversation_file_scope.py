from dataclasses import dataclass
from pathlib import Path

from asagent.core.ids import ConversationId


@dataclass(frozen=True, slots=True)
class ConversationFileScope:
    """The external files and folders explicitly authorized for one conversation."""

    conversation_id: ConversationId
    additional_roots: tuple[Path, ...] = ()
    additional_files: tuple[Path, ...] = ()
