import io
import json
from collections.abc import Mapping
from pathlib import Path

import pypdf
import pytest
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from asagent.core.tool import Tool
from asagent.tools import pdf_text
from asagent.tools.builtin.document_extract_text import DocumentExtractTextTool
from asagent.workspace.resolver import (
    WorkspacePathOutsideAllowedRootsError,
    WorkspaceResolver,
)


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
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): font,
                    }
                )
            }
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


def _make_blank_pdf(num_pages: int = 1) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_encrypted_pdf(password: str = "secret") -> bytes:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _tool(workspace_root: Path) -> DocumentExtractTextTool:
    return DocumentExtractTextTool(
        WorkspaceResolver(workspace_root=workspace_root),
    )


def test_document_extract_text_tool_satisfies_protocol_and_schema(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool: Tool = _tool(workspace_root)

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "document.extract_text"
    assert tool.definition.display_name == "Extract document text"
    assert tool.definition.risk_level == "low"
    assert tool.definition.required_permissions == frozenset({"filesystem.read"})
    assert tool.definition.requires_approval is False
    assert tool.definition.timeout_seconds == 15.0

    schema = tool.definition.input_schema
    assert schema["type"] == "object"
    assert schema["required"] == ["path"]
    assert schema["additionalProperties"] is False

    properties = schema["properties"]
    assert isinstance(properties, Mapping)
    assert "path" in properties
    assert properties["start_page"]["type"] == "integer"
    assert properties["start_page"]["minimum"] == 1
    assert properties["start_page"]["default"] == 1
    assert properties["start_char_offset"]["type"] == "integer"
    assert properties["start_char_offset"]["minimum"] == 0
    assert properties["start_char_offset"]["default"] == 0
    assert properties["end_page"]["type"] == "integer"
    assert properties["end_page"]["minimum"] == 1


@pytest.mark.asyncio
async def test_extract_text_single_page_pdf(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "sample.pdf"
    pdf_path.write_bytes(_make_pdf(["Hello World"]))

    result_raw = await _tool(workspace_root).execute({"path": "sample.pdf"})
    result = json.loads(result_raw)

    assert result["format"] == "pdf"
    assert result["page_count"] == 1
    assert result["start_page"] == 1
    assert result["start_char_offset"] == 0
    assert result["end_page"] == 1
    assert len(result["pages"]) == 1
    assert result["pages"][0]["page_number"] == 1
    assert result["pages"][0]["text"] == "Hello World"
    assert result["next_position"] is None
    assert result["text_layer_found"] is True
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_extract_text_multipage_default_pagination(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "doc.pdf"
    pdf_path.write_bytes(_make_pdf([f"Content on page {i}" for i in range(1, 8)]))

    result_raw = await _tool(workspace_root).execute({"path": "doc.pdf"})
    result = json.loads(result_raw)

    assert result["page_count"] == 7
    assert result["start_page"] == 1
    assert result["start_char_offset"] == 0
    assert result["end_page"] == 5
    assert len(result["pages"]) == 5
    assert result["pages"][0]["page_number"] == 1
    assert result["pages"][4]["page_number"] == 5
    assert result["pages"][0]["text"] == "Content on page 1"
    assert result["next_position"] == {"page": 6, "char_offset": 0}
    assert result["text_layer_found"] is True
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_extract_text_explicit_page_range(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "doc.pdf"
    pdf_path.write_bytes(_make_pdf([f"Content on page {i}" for i in range(1, 8)]))

    result_raw = await _tool(workspace_root).execute(
        {"path": "doc.pdf", "start_page": 6, "end_page": 7}
    )
    result = json.loads(result_raw)

    assert result["page_count"] == 7
    assert result["start_page"] == 6
    assert result["start_char_offset"] == 0
    assert result["end_page"] == 7
    assert len(result["pages"]) == 2
    assert result["pages"][0]["page_number"] == 6
    assert result["pages"][1]["page_number"] == 7
    assert result["pages"][0]["text"] == "Content on page 6"
    assert result["pages"][1]["text"] == "Content on page 7"
    assert result["next_position"] is None
    assert result["text_layer_found"] is True
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_extract_text_blank_and_scanned_pdf(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "scanned.pdf"
    pdf_path.write_bytes(_make_blank_pdf(num_pages=2))

    result_raw = await _tool(workspace_root).execute({"path": "scanned.pdf"})
    result = json.loads(result_raw)

    assert result["page_count"] == 2
    assert result["start_page"] == 1
    assert result["start_char_offset"] == 0
    assert result["end_page"] == 2
    assert len(result["pages"]) == 2
    assert result["pages"][0]["text"] == ""
    assert result["pages"][1]["text"] == ""
    assert result["next_position"] is None
    assert result["text_layer_found"] is False
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_rejects_outside_missing_directory_and_non_pdf(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "folder").mkdir()
    (workspace_root / "file.txt").write_text("not a pdf", encoding="utf-8")
    tool = _tool(workspace_root)

    with pytest.raises(WorkspacePathOutsideAllowedRootsError):
        await tool.execute({"path": "../outside.pdf"})

    with pytest.raises(ValueError, match="file does not exist"):
        await tool.execute({"path": "missing.pdf"})

    with pytest.raises(ValueError, match="path must resolve to a file"):
        await tool.execute({"path": "folder"})

    with pytest.raises(ValueError, match="file must be a PDF"):
        await tool.execute({"path": "file.txt"})


@pytest.mark.asyncio
async def test_rejects_encrypted_pdf(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "locked.pdf"
    pdf_path.write_bytes(_make_encrypted_pdf("pass123"))

    with pytest.raises(
        ValueError,
        match="PDF is encrypted and password-protected PDFs are not supported",
    ):
        await _tool(workspace_root).execute({"path": "locked.pdf"})


@pytest.mark.asyncio
async def test_rejects_corrupted_pdf(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncorrupted content\n%%EOF")

    with pytest.raises(ValueError, match="PDF is invalid or corrupted"):
        await _tool(workspace_root).execute({"path": "broken.pdf"})


@pytest.mark.asyncio
async def test_rejects_oversized_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "large.pdf"
    pdf_path.write_bytes(_make_pdf(["Sample"]))

    # Test file size check without writing a full 20MB file
    monkeypatch.setattr(
        pdf_text,
        "MAX_PDF_FILE_BYTES",
        10,
    )
    with pytest.raises(ValueError, match="PDF exceeds the 20 MiB file limit"):
        await _tool(workspace_root).execute({"path": "large.pdf"})


@pytest.mark.asyncio
async def test_rejects_invalid_page_ranges(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "three_pages.pdf"
    pdf_path.write_bytes(_make_pdf(["p1", "p2", "p3"]))
    tool = _tool(workspace_root)

    with pytest.raises(ValueError, match="start_page must not exceed end_page"):
        await tool.execute({"path": "three_pages.pdf", "start_page": 3, "end_page": 2})

    with pytest.raises(ValueError, match="a single call may extract at most 10 pages"):
        await tool.execute({"path": "three_pages.pdf", "start_page": 1, "end_page": 11})

    with pytest.raises(ValueError, match="page range exceeds the PDF page count"):
        await tool.execute({"path": "three_pages.pdf", "start_page": 5})

    with pytest.raises(ValueError, match="page range exceeds the PDF page count"):
        await tool.execute({"path": "three_pages.pdf", "start_page": 1, "end_page": 5})


@pytest.mark.asyncio
async def test_rejects_oversized_page_content_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "big_stream.pdf"
    pdf_path.write_bytes(_make_pdf(["Content Stream"]))

    # Monkeypatch stream limit to 5 bytes to trigger limit
    monkeypatch.setattr(
        pdf_text,
        "MAX_PAGE_STREAM_BYTES",
        5,
    )
    with pytest.raises(
        ValueError, match="PDF page content exceeds the extraction limit"
    ):
        await _tool(workspace_root).execute({"path": "big_stream.pdf"})


async def _extract_all_text_sequentially(
    tool: DocumentExtractTextTool,
    path: str,
) -> tuple[str, list[dict[str, object]]]:
    """Helper that calls the tool sequentially using next_position until EOF."""
    current_page = 1
    current_offset = 0
    all_chunks: list[str] = []
    all_responses: list[dict[str, object]] = []

    while True:
        result_raw = await tool.execute(
            {
                "path": path,
                "start_page": current_page,
                "start_char_offset": current_offset,
            }
        )
        result = json.loads(result_raw)
        all_responses.append(result)
        for page in result["pages"]:
            all_chunks.append(page["text"])

        next_pos = result["next_position"]
        if next_pos is None:
            break
        current_page = next_pos["page"]
        current_offset = next_pos["char_offset"]

    return "".join(all_chunks), all_responses


@pytest.mark.asyncio
async def test_continuous_extraction_scenario_1_exact_budget_page_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "exact_boundary.pdf"
    page1_text = "A" * 100
    page2_text = "B" * 100
    pdf_path.write_bytes(_make_pdf([page1_text, page2_text]))

    # Set budget to exactly 100 chars (matches page 1 length)
    monkeypatch.setattr(
        pdf_text,
        "MAX_ACCUMULATED_TEXT_CHARS",
        100,
    )
    tool = _tool(workspace_root)
    full_extracted, responses = await _extract_all_text_sequentially(
        tool, "exact_boundary.pdf"
    )

    assert len(responses) == 2
    # First response took exactly page 1, next_position points to page 2 char 0
    assert responses[0]["start_page"] == 1
    assert responses[0]["end_page"] == 1
    assert responses[0]["next_position"] == {"page": 2, "char_offset": 0}
    assert responses[0]["truncated"] is True

    # Second response took page 2, next_position is None
    assert responses[1]["start_page"] == 2
    assert responses[1]["end_page"] == 2
    assert responses[1]["next_position"] is None
    assert responses[1]["truncated"] is False

    # Exact byte-for-byte reconstructed text
    assert full_extracted == page1_text + page2_text


@pytest.mark.asyncio
async def test_continuous_extraction_scenario_2_single_page_oversized_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "long_single_page.pdf"
    long_text = "X" * 17_000
    pdf_path.write_bytes(_make_pdf([long_text]))

    tool = _tool(workspace_root)
    full_extracted, responses = await _extract_all_text_sequentially(
        tool, "long_single_page.pdf"
    )

    # First call took budget (12,000), second call took remainder (5,000)
    assert len(responses) == 2
    assert responses[0]["start_page"] == 1
    assert responses[0]["end_page"] == 1
    assert responses[0]["next_position"] == {"page": 1, "char_offset": 12_000}
    assert responses[0]["truncated"] is True

    assert responses[1]["start_page"] == 1
    assert responses[1]["start_char_offset"] == 12_000
    assert responses[1]["end_page"] == 1
    assert responses[1]["next_position"] is None
    assert responses[1]["truncated"] is False

    # Full text match with 0 lost characters
    assert full_extracted == long_text
    assert len(full_extracted) == 17_000


@pytest.mark.asyncio
async def test_continuous_extraction_scenario_3_single_page_many_quotes(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "quotes.pdf"
    quotes_text = '"' * 10_000
    pdf_path.write_bytes(_make_pdf([quotes_text]))

    tool = _tool(workspace_root)
    full_extracted, responses = await _extract_all_text_sequentially(tool, "quotes.pdf")

    assert len(responses) >= 2
    # Verify every individual response is strictly <= MAX_RESULT_CHARS (18,000)
    for resp in responses:
        json_len = len(json.dumps(resp, ensure_ascii=False))
        assert json_len <= pdf_text.MAX_RESULT_CHARS

    # Full text match with 0 lost characters
    assert full_extracted == quotes_text
    assert len(full_extracted) == 10_000


@pytest.mark.asyncio
async def test_continuous_extraction_multipage_full_reconstruction(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "multi.pdf"
    pages_text = [
        "Chapter 1: " + ("Intro " * 500),
        "Chapter 2: " + ("Methods " * 600),
        "Chapter 3: " + ("Results " * 700),
        "Chapter 4: " + ("Discussion " * 800),
        "Chapter 5: " + ("Conclusion " * 900),
    ]
    pdf_path.write_bytes(_make_pdf(pages_text))

    tool = _tool(workspace_root)
    full_extracted, responses = await _extract_all_text_sequentially(tool, "multi.pdf")

    assert len(responses) >= 2
    # Exact byte-for-byte concatenated match
    assert full_extracted == "".join(pages_text)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "error_match"),
    [
        ({}, "path must be a string"),
        ({"path": 123}, "path must be a string"),
        ({"path": ""}, "path must be a string"),
        (
            {"path": "doc.pdf", "start_page": 0},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"path": "doc.pdf", "start_page": -1},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"path": "doc.pdf", "start_page": "1"},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"path": "doc.pdf", "start_page": True},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"path": "doc.pdf", "start_char_offset": -1},
            "start_char_offset must be an integer greater than or equal to 0",
        ),
        (
            {"path": "doc.pdf", "start_char_offset": "0"},
            "start_char_offset must be an integer greater than or equal to 0",
        ),
        (
            {"path": "doc.pdf", "start_char_offset": True},
            "start_char_offset must be an integer greater than or equal to 0",
        ),
        (
            {"path": "doc.pdf", "end_page": 0},
            "end_page must be an integer greater than or equal to 1",
        ),
        (
            {"path": "doc.pdf", "end_page": -2},
            "end_page must be an integer greater than or equal to 1",
        ),
        (
            {"path": "doc.pdf", "end_page": "5"},
            "end_page must be an integer greater than or equal to 1",
        ),
        (
            {"path": "doc.pdf", "end_page": False},
            "end_page must be an integer greater than or equal to 1",
        ),
    ],
)
async def test_rejects_invalid_direct_arguments(
    tmp_path: Path, arguments: dict[str, object], error_match: str
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    tool = _tool(workspace_root)

    with pytest.raises(ValueError, match=error_match):
        await tool.execute(arguments)


@pytest.mark.asyncio
async def test_rejects_start_char_offset_exceeding_page_length(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    pdf_path = workspace_root / "short.pdf"
    pdf_path.write_bytes(_make_pdf(["Short Text"]))

    tool = _tool(workspace_root)
    with pytest.raises(ValueError, match="start_char_offset exceeds page text length"):
        await tool.execute(
            {"path": "short.pdf", "start_page": 1, "start_char_offset": 9999}
        )
