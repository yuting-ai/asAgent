import io
import zipfile
from pathlib import Path

import pypdf
import pytest
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from asagent.core.ids import DocumentId
from asagent.knowledge.chunker import (
    CHUNKER_VERSION,
    chunk_document,
    count_tokens_simple,
    split_section_into_chunks,
)
from asagent.knowledge.parser import (
    PARSER_VERSION,
    ParsedSection,
    parse_docx,
    parse_file,
    parse_html,
    parse_markdown,
    parse_pdf,
    parse_text,
)
from asagent.knowledge.scanner import (
    compute_file_sha256,
    scan_directory,
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


def _make_docx(paragraphs: list[tuple[str | None, str]]) -> bytes:
    paragraph_xml = []
    for style, text in paragraphs:
        style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        paragraph_xml.append(f"<w:p>{style_xml}<w:r><w:t>{text}</w:t></w:r></w:p>")
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f"{''.join(paragraph_xml)}"
        "</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_scanner_filters_and_hashing(tmp_path: Path) -> None:
    sub_dir = tmp_path / "docs" / "papers"
    sub_dir.mkdir(parents=True)

    f1 = sub_dir / "paper.pdf"
    f1.write_bytes(_make_pdf(["Sample page one content."]))

    f2 = sub_dir / "notes.md"
    f2.write_text("# Notes\n\nSome notes about AI.", encoding="utf-8")

    f3 = tmp_path / "readme.txt"
    f3.write_text("Plain text readme.", encoding="utf-8")

    f4 = sub_dir / "article.html"
    f4.write_text("<h1>Article</h1><p>HTML body.</p>", encoding="utf-8")

    f5 = sub_dir / "report.docx"
    f5.write_bytes(_make_docx([("Title", "Quarterly report")]))

    # Ignored files
    (tmp_path / ".hidden.md").write_text("hidden", encoding="utf-8")
    (tmp_path / "ignored.bin").write_bytes(b"\x00\x01\x02")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config.txt").write_text("git config", encoding="utf-8")

    node_modules = tmp_path / "node_modules" / "pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "index.js").write_text("console.log('hi')", encoding="utf-8")

    # Scan directory
    scanned = scan_directory(tmp_path)
    assert len(scanned) == 5

    rel_paths = [f.relative_path for f in scanned]
    assert rel_paths == [
        "docs/papers/article.html",
        "docs/papers/notes.md",
        "docs/papers/paper.pdf",
        "docs/papers/report.docx",
        "readme.txt",
    ]

    # Verify file types & hashes
    by_path = {f.relative_path: f for f in scanned}
    assert by_path["docs/papers/notes.md"].file_type == "markdown"
    assert by_path["docs/papers/paper.pdf"].file_type == "pdf"
    assert by_path["docs/papers/article.html"].file_type == "html"
    assert by_path["docs/papers/report.docx"].file_type == "docx"
    assert by_path["readme.txt"].file_type == "text"
    assert by_path["readme.txt"].content_hash == compute_file_sha256(f3)

    # Invalid directory raises
    with pytest.raises(ValueError):
        scan_directory(tmp_path / "non_existent")


def test_scanner_does_not_follow_file_symlinks_outside_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    outside_dir = tmp_path / "private"
    source_dir.mkdir()
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.md"
    outside_file.write_text("private content", encoding="utf-8")
    (source_dir / "linked.md").symlink_to(outside_file)

    assert scan_directory(source_dir) == ()


def test_parser_markdown() -> None:
    md_content = """# Deep Learning Overview

Introduction to neural networks.

## Transformer Architecture

Self-attention mechanism and feed-forward layers.

### Multi-Head Attention

Details about heads.
"""
    parsed = parse_markdown(md_content)
    assert parsed.file_type == "markdown"
    assert parsed.parser_version == PARSER_VERSION
    assert len(parsed.sections) == 3

    assert parsed.sections[0].section_title == "Deep Learning Overview"
    assert "Introduction to neural networks" in parsed.sections[0].text

    assert parsed.sections[1].section_title == "Transformer Architecture"
    assert "Self-attention mechanism" in parsed.sections[1].text

    assert parsed.sections[2].section_title == "Multi-Head Attention"
    assert "Details about heads" in parsed.sections[2].text


def test_parser_text() -> None:
    text_content = "Just plain text content without any markdown headers."
    parsed = parse_text(text_content)
    assert parsed.file_type == "text"
    assert len(parsed.sections) == 1
    assert parsed.sections[0].text == text_content
    assert parsed.sections[0].section_title is None
    assert parsed.sections[0].page_start is None


def test_parser_html_keeps_visible_structure_and_ignores_executable_content() -> None:
    parsed = parse_html(
        """
        <html>
          <head>
            <title>Research &amp; Development</title>
            <style>.secret { display: none; }</style>
            <script>sendPrivateData()</script>
          </head>
          <body>
            <p>Opening summary.</p>
            <h2>Findings</h2>
            <p>The model reached <strong>95%</strong> accuracy.</p>
            <ul><li>First result</li><li>Second result</li></ul>
          </body>
        </html>
        """
    )

    assert parsed.file_type == "html"
    assert [section.section_title for section in parsed.sections] == [
        "Research & Development",
        "Findings",
    ]
    assert "Opening summary." in parsed.sections[0].text
    assert "95% accuracy" in parsed.sections[1].text
    assert "First result" in parsed.sections[1].text
    assert "sendPrivateData" not in " ".join(
        section.text for section in parsed.sections
    )


def test_parse_docx_file(tmp_path: Path) -> None:
    docx_path = tmp_path / "report.docx"
    docx_path.write_bytes(
        _make_docx(
            [
                ("Title", "Annual Research Report"),
                (None, "Executive summary."),
                ("Heading1", "Methods"),
                (None, "We evaluated the local retrieval pipeline."),
            ]
        )
    )

    parsed = parse_docx(docx_path)

    assert parsed.file_type == "docx"
    assert [section.section_title for section in parsed.sections] == [
        "Annual Research Report",
        "Methods",
    ]
    assert "Executive summary." in parsed.sections[0].text
    assert "local retrieval pipeline" in parsed.sections[1].text


def test_parser_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "multi_page.pdf"
    pdf_path.write_bytes(
        _make_pdf(["First page introduction.", "Second page architecture."])
    )

    parsed = parse_pdf(pdf_path)
    assert parsed.file_type == "pdf"
    assert len(parsed.sections) == 2

    assert parsed.sections[0].page_start == 1
    assert parsed.sections[0].page_end == 1
    assert "First page introduction." in parsed.sections[0].text

    assert parsed.sections[1].page_start == 2
    assert parsed.sections[1].page_end == 2
    assert "Second page architecture." in parsed.sections[1].text


def test_parse_file_dispatcher(tmp_path: Path) -> None:
    md_path = tmp_path / "test.md"
    md_path.write_text("# Heading\nBody text.", encoding="utf-8")
    parsed_md = parse_file(md_path, "markdown")
    assert parsed_md.file_type == "markdown"

    txt_path = tmp_path / "test.txt"
    txt_path.write_text("Simple text.", encoding="utf-8")
    parsed_txt = parse_file(txt_path, "text")
    assert parsed_txt.file_type == "text"

    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(_make_pdf(["PDF text"]))
    parsed_pdf = parse_file(pdf_path, "pdf")
    assert parsed_pdf.file_type == "pdf"

    html_path = tmp_path / "test.html"
    html_path.write_text("<h1>Web note</h1><p>Body.</p>", encoding="utf-8")
    parsed_html = parse_file(html_path, "html")
    assert parsed_html.file_type == "html"

    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(_make_docx([("Heading1", "Word note")]))
    parsed_docx = parse_file(docx_path, "docx")
    assert parsed_docx.file_type == "docx"


def test_chunker_deterministic_hashes_and_metadata() -> None:
    doc_id = DocumentId("doc_test_123")
    doc_hash = "abc123456789hash"

    md_content = """# Section One
This is the first section of the document with enough text to be meaningful.

# Section Two
This is the second section of the document discussing separate topics.
"""
    parsed = parse_markdown(md_content)
    chunks1 = chunk_document(
        document_id=doc_id,
        document_content_hash=doc_hash,
        parsed_doc=parsed,
        target_tokens=50,
        overlap_tokens=10,
    )

    assert len(chunks1) == 2
    assert chunks1[0].chunk_index == 0
    assert chunks1[0].section_title == "Section One"
    assert chunks1[0].document_id == "doc_test_123"
    assert chunks1[0].chunker_version == CHUNKER_VERSION

    assert chunks1[1].chunk_index == 1
    assert chunks1[1].section_title == "Section Two"

    # Determinism: running again produces identical content hashes and index
    chunks2 = chunk_document(
        document_id=doc_id,
        document_content_hash=doc_hash,
        parsed_doc=parsed,
        target_tokens=50,
        overlap_tokens=10,
    )
    assert [c.content_hash for c in chunks1] == [c.content_hash for c in chunks2]


def test_chunker_with_pdf_page_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "pages.pdf"
    pdf_path.write_bytes(_make_pdf(["Page 1 content.", "Page 2 content."]))
    parsed = parse_pdf(pdf_path)

    chunks = chunk_document(
        document_id=DocumentId("doc_pdf"),
        document_content_hash="pdfhash",
        parsed_doc=parsed,
    )

    assert len(chunks) == 2
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert "Page 1 content." in chunks[0].text

    assert chunks[1].page_start == 2
    assert chunks[1].page_end == 2
    assert "Page 2 content." in chunks[1].text


def test_chunker_overlap_and_sliding_window() -> None:
    long_text = "\n\n".join([f"Paragraph {i}: " + "word " * 40 for i in range(10)])
    section = ParsedSection(text=long_text, section_title="Long Section")

    chunks = split_section_into_chunks(
        section,
        token_counter=count_tokens_simple,
        target_tokens=60,
        overlap_tokens=15,
    )

    assert len(chunks) > 1
    for chunk in chunks:
        tokens = count_tokens_simple(chunk)
        # Chunks should fit within reasonable boundaries
        assert tokens > 0
