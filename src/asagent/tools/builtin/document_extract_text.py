import asyncio
from collections.abc import Mapping
from pathlib import Path

from asagent.core.tool_definition import ToolDefinition
from asagent.tools import pdf_text
from asagent.workspace.resolver import WorkspaceResolver


class DocumentExtractTextTool:
    """Extracts text from an authorized PDF document within the file scope."""

    def __init__(self, resolver: WorkspaceResolver) -> None:
        self._resolver = resolver

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="document.extract_text",
            display_name="Extract document text",
            description=(
                "Extracts text from PDF (.pdf) documents. "
                "Always use this tool instead of filesystem.read_file when reading PDF files. "
                "Pages are 1-indexed. Reads up to 5 pages by default (max 10 pages per call). "
                "Supports character offset continuation within a page via start_char_offset. "
                "If next_position is present in the output, call again with start_page=next_position.page "
                "and start_char_offset=next_position.char_offset to continue reading seamlessly. "
                "Only extracts documents with a text layer; OCR is not supported."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "A PDF file inside the current conversation's authorized file scope."
                        ),
                    },
                    "start_page": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                        "description": (
                            "The 1-based page number to start extracting from. Defaults to 1."
                        ),
                    },
                    "start_char_offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": (
                            "The 0-based character offset within start_page to begin extracting from. "
                            "Defaults to 0. Use the char_offset from a previous next_position to resume."
                        ),
                    },
                    "end_page": {
                        "type": "integer",
                        "minimum": 1,
                        "description": (
                            "The 1-based page number to end extracting (inclusive). "
                            "Defaults to start_page + 4 (up to 5 pages)."
                        ),
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"filesystem.read"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        path = self._path_from(arguments)
        start_page, start_char_offset, end_page = pdf_text.parse_page_range(arguments)
        file_path = self._resolver.resolve(path)

        if not file_path.exists():
            raise ValueError("file does not exist")
        if not file_path.is_file():
            raise ValueError("path must resolve to a file")
        if file_path.suffix.lower() != ".pdf":
            raise ValueError("file must be a PDF")

        file_size = file_path.stat().st_size
        if file_size > pdf_text.MAX_PDF_FILE_BYTES:
            raise ValueError("PDF exceeds the 20 MiB file limit")

        return await asyncio.to_thread(
            self._extract_sync,
            file_path,
            start_page,
            start_char_offset,
            end_page,
        )

    @classmethod
    def _path_from(cls, arguments: Mapping[str, object]) -> Path:
        value = arguments.get("path")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("path must be a string")
        return Path(value)

    @classmethod
    def _extract_sync(
        cls,
        file_path: Path,
        start_page: int,
        start_char_offset: int,
        end_page: int | None,
    ) -> str:
        with file_path.open("rb") as stream:
            return pdf_text.extract_pdf_text_from_stream(
                stream,
                start_page=start_page,
                start_char_offset=start_char_offset,
                end_page=end_page,
            )
