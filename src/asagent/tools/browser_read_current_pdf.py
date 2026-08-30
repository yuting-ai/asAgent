import asyncio
import io
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition
from asagent.tools import pdf_text
from asagent.tools.errors import ToolOperationError, ToolTimeoutError

_PARSE_TIMEOUT_SECONDS = 15.0


class BrowserReadCurrentPdfTool:
    """Extracts text from the PDF currently open in the active browser tab."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id
        self._cached_document_id: str | None = None
        self._cached_pdf_bytes: bytes | None = None

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.read_current_pdf",
            display_name="Read current PDF",
            description=(
                "Extracts text from the PDF document currently open in the active browser tab. "
                "Pages are 1-indexed. Reads up to 5 pages by default (max 10 pages per call). "
                "Supports character offset continuation within a page via start_char_offset. "
                "If next_position is present in the output, call again with start_page=next_position.page "
                "and start_char_offset=next_position.char_offset to continue reading seamlessly. "
                "Only extracts documents with a text layer; OCR is not supported."
                " Continuation uses one snapshot for this run only. If the tab or document "
                "changes, start a new browser run instead of reusing an old offset."
            ),
            input_schema={
                "type": "object",
                "properties": {
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
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"browser.read"}),
            requires_approval=False,
            timeout_seconds=40.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        start_page, start_char_offset, end_page = pdf_text.parse_page_range(arguments)

        if self._cached_document_id is not None and self._cached_pdf_bytes is None:
            raise ToolOperationError("PDF document changed; start a new browser run")

        try:
            if self._cached_pdf_bytes is None:
                doc = await self._client.read_current_pdf(self._tab_id)
                self._cached_document_id = doc.document_id
                self._cached_pdf_bytes = doc.data
            else:
                assert self._cached_document_id is not None
                await self._client.validate_current_pdf(
                    self._tab_id, self._cached_document_id
                )

            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._extract_sync,
                    self._cached_pdf_bytes,
                    start_page,
                    start_char_offset,
                    end_page,
                ),
                timeout=_PARSE_TIMEOUT_SECONDS,
            )
            assert self._cached_document_id is not None
            await self._client.validate_current_pdf(
                self._tab_id, self._cached_document_id
            )
            return result
        except BrowserPageBridgeError as error:
            self._cached_pdf_bytes = None
            raise ValueError(str(error)) from error
        except TimeoutError as error:
            self._cached_pdf_bytes = None
            raise ToolTimeoutError("PDF text extraction timed out") from error
        except (ToolOperationError, asyncio.CancelledError):
            self._cached_pdf_bytes = None
            raise

    @classmethod
    def _extract_sync(
        cls,
        pdf_bytes: bytes,
        start_page: int,
        start_char_offset: int,
        end_page: int | None,
    ) -> str:
        with io.BytesIO(pdf_bytes) as stream:
            return pdf_text.extract_pdf_text_from_stream(
                stream,
                start_page=start_page,
                start_char_offset=start_char_offset,
                end_page=end_page,
            )
