import io
import json
from pathlib import Path

import pypdf
import pytest
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from asagent.tools import pdf_text


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


def test_parse_page_range_valid_and_defaults() -> None:
    assert pdf_text.parse_page_range({}) == (1, 0, None)
    assert pdf_text.parse_page_range({"start_page": 2, "start_char_offset": 50}) == (
        2,
        50,
        None,
    )
    assert pdf_text.parse_page_range(
        {"start_page": 1, "start_char_offset": 0, "end_page": 5}
    ) == (1, 0, 5)


@pytest.mark.parametrize(
    ("arguments", "error_match"),
    [
        (
            {"start_page": 0},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"start_page": -1},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"start_page": "1"},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"start_page": True},
            "start_page must be an integer greater than or equal to 1",
        ),
        (
            {"start_char_offset": -1},
            "start_char_offset must be an integer greater than or equal to 0",
        ),
        (
            {"start_char_offset": "0"},
            "start_char_offset must be an integer greater than or equal to 0",
        ),
        (
            {"start_char_offset": True},
            "start_char_offset must be an integer greater than or equal to 0",
        ),
        (
            {"end_page": 0},
            "end_page must be an integer greater than or equal to 1",
        ),
        (
            {"end_page": -2},
            "end_page must be an integer greater than or equal to 1",
        ),
        (
            {"start_page": 5, "end_page": 4},
            "start_page must not exceed end_page",
        ),
        (
            {"start_page": 1, "end_page": 11},
            "a single call may extract at most 10 pages",
        ),
    ],
)
def test_parse_page_range_invalid_arguments(
    arguments: dict[str, object], error_match: str
) -> None:
    with pytest.raises(ValueError, match=error_match):
        pdf_text.parse_page_range(arguments)


def test_file_stream_and_bytesio_memory_stream_produce_identical_output(
    tmp_path: Path,
) -> None:
    pdf_bytes = _make_pdf(["Page 1 Content", "Page 2 Content", "Page 3 Content"])
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(pdf_bytes)

    # 1. Read via open() file stream
    with file_path.open("rb") as stream:
        result_from_file = pdf_text.extract_pdf_text_from_stream(
            stream, start_page=1, start_char_offset=0, end_page=2
        )

    # 2. Read via io.BytesIO memory stream (Browser tool pattern)
    memory_stream = io.BytesIO(pdf_bytes)
    result_from_memory = pdf_text.extract_pdf_text_from_stream(
        memory_stream, start_page=1, start_char_offset=0, end_page=2
    )

    assert result_from_file == result_from_memory
    parsed = json.loads(result_from_file)
    assert parsed["page_count"] == 3
    assert parsed["start_page"] == 1
    assert parsed["start_char_offset"] == 0
    assert parsed["end_page"] == 2
    assert len(parsed["pages"]) == 2
    assert parsed["next_position"] == {"page": 3, "char_offset": 0}
    assert parsed["text_layer_found"] is True
    assert parsed["truncated"] is False


def test_file_stream_and_memory_stream_continuous_exact_reconstruction(
    tmp_path: Path,
) -> None:
    # Construct a complex multi-page document with oversized text and quotes
    pages_text = [
        "Section 1: " + ('"Quote" ' * 600) + ("Text " * 800),
        "Section 2: " + ("Detail " * 1200),
        "Section 3: " + ('"Example" ' * 1000),
        "Section 4: " + ("Final analysis " * 500),
    ]
    full_expected_text = "".join(pages_text)
    pdf_bytes = _make_pdf(pages_text)
    file_path = tmp_path / "complex.pdf"
    file_path.write_bytes(pdf_bytes)

    # Sequential reading loop using file streams
    file_responses: list[dict[str, object]] = []
    file_chunks: list[str] = []
    curr_page = 1
    curr_offset = 0
    while True:
        with file_path.open("rb") as stream:
            res_str = pdf_text.extract_pdf_text_from_stream(
                stream,
                start_page=curr_page,
                start_char_offset=curr_offset,
                end_page=None,
            )
        res = json.loads(res_str)
        file_responses.append(res)
        for p in res["pages"]:
            file_chunks.append(str(p["text"]))
        next_pos = res["next_position"]
        if next_pos is None:
            break
        curr_page = next_pos["page"]
        curr_offset = next_pos["char_offset"]

    # Sequential reading loop using in-memory BytesIO
    memory_responses: list[dict[str, object]] = []
    memory_chunks: list[str] = []
    curr_page = 1
    curr_offset = 0
    while True:
        mem_stream = io.BytesIO(pdf_bytes)
        res_str = pdf_text.extract_pdf_text_from_stream(
            mem_stream,
            start_page=curr_page,
            start_char_offset=curr_offset,
            end_page=None,
        )
        res = json.loads(res_str)
        memory_responses.append(res)
        for p in res["pages"]:
            memory_chunks.append(str(p["text"]))
        next_pos = res["next_position"]
        if next_pos is None:
            break
        curr_page = next_pos["page"]
        curr_offset = next_pos["char_offset"]

    # Verify both methods produced identical results and payloads
    assert len(file_responses) == len(memory_responses)
    assert file_responses == memory_responses
    assert "".join(file_chunks) == full_expected_text
    assert "".join(memory_chunks) == full_expected_text
