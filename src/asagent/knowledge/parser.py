import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import pypdf
import pypdf.errors

from asagent.knowledge.models import DocumentFileType

PARSER_VERSION = "asagent-parser-v2"
MAX_DOCX_DOCUMENT_XML_BYTES = 32 * 1024 * 1024

_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WORD_TAG = f"{{{_WORD_NAMESPACE}}}"
_HTML_IGNORED_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}
_HTML_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "dt",
    "dd",
    "figcaption",
    "figure",
    "footer",
    "header",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tr",
    "ul",
}
_HTML_HEADING_TAGS = {f"h{level}" for level in range(1, 7)}


@dataclass(frozen=True, slots=True)
class ParsedSection:
    """A structured section extracted from a document with page and title metadata."""

    text: str
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """The structured parsing result of a document."""

    file_type: DocumentFileType
    parser_version: str
    sections: tuple[ParsedSection, ...]


_HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def parse_markdown(content: str) -> ParsedDocument:
    """Parse Markdown content by splitting on heading boundaries."""
    lines = content.splitlines()
    sections: list[ParsedSection] = []

    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match:
            # Previous section flush
            text = "\n".join(current_lines).strip()
            if text:
                sections.append(ParsedSection(text=text, section_title=current_title))
            current_title = match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    text = "\n".join(current_lines).strip()
    if text:
        sections.append(ParsedSection(text=text, section_title=current_title))

    if not sections and content.strip():
        sections.append(ParsedSection(text=content.strip(), section_title=None))

    return ParsedDocument(
        file_type="markdown",
        parser_version=PARSER_VERSION,
        sections=tuple(sections),
    )


def parse_text(content: str) -> ParsedDocument:
    """Parse plain text content into a clean single section."""
    cleaned = content.strip()
    sections = (ParsedSection(text=cleaned, section_title=None),) if cleaned else ()
    return ParsedDocument(
        file_type="text",
        parser_version=PARSER_VERSION,
        sections=sections,
    )


class _VisibleHTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0
        self._in_head = False
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if self._ignored_depth > 0:
            if tag in _HTML_IGNORED_TAGS:
                self._ignored_depth += 1
            return
        if tag in _HTML_IGNORED_TAGS:
            self._ignored_depth = 1
            return
        if tag == "head":
            self._in_head = True
            return
        if tag == "title" and self._in_head:
            self._in_title = True
            return
        if self._in_head:
            return
        if tag in _HTML_HEADING_TAGS:
            self._parts.append(f"\n\n{'#' * int(tag[1])} ")
        elif tag == "br":
            self._parts.append("\n")
        elif tag == "li":
            self._parts.append("\n- ")
        elif tag in _HTML_BLOCK_TAGS:
            self._parts.append("\n")
        elif tag in {"td", "th"}:
            self._parts.append("\t")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._ignored_depth > 0:
            if tag in _HTML_IGNORED_TAGS:
                self._ignored_depth -= 1
            return
        if tag == "title" and self._in_title:
            self._in_title = False
            return
        if tag == "head":
            self._in_head = False
            return
        if self._in_head:
            return
        if tag in _HTML_BLOCK_TAGS or tag in _HTML_HEADING_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return
        if self._in_title:
            self._title_parts.append(data)
            return
        if not self._in_head:
            self._parts.append(data)

    def markdown_text(self) -> str:
        lines = [
            re.sub(r"[\t ]+", " ", line).strip()
            for line in "".join(self._parts).splitlines()
        ]
        compact_lines: list[str] = []
        for line in lines:
            if line or (compact_lines and compact_lines[-1]):
                compact_lines.append(line)
        body = "\n".join(compact_lines).strip()
        title = re.sub(r"\s+", " ", "".join(self._title_parts)).strip()
        if title and not body.startswith(f"# {title}"):
            return f"# {title}\n\n{body}".strip()
        return body


def parse_html(content: str) -> ParsedDocument:
    """Extract visible, non-executable HTML text and preserve heading boundaries."""
    parser = _VisibleHTMLTextParser()
    parser.feed(content)
    parser.close()
    markdown_document = parse_markdown(parser.markdown_text())
    return ParsedDocument(
        file_type="html",
        parser_version=PARSER_VERSION,
        sections=markdown_document.sections,
    )


def _docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_WORD_TAG}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{_WORD_TAG}tab":
            parts.append("\t")
        elif node.tag in {f"{_WORD_TAG}br", f"{_WORD_TAG}cr"}:
            parts.append("\n")
    return "".join(parts).strip()


def _docx_paragraph_style(paragraph: ElementTree.Element) -> str | None:
    properties = paragraph.find(f"{_WORD_TAG}pPr")
    if properties is None:
        return None
    style = properties.find(f"{_WORD_TAG}pStyle")
    if style is None:
        return None
    return style.get(f"{_WORD_TAG}val")


def _is_docx_heading_style(style: str | None) -> bool:
    if style is None:
        return False
    normalized = re.sub(r"[\s_-]+", "", style).casefold()
    return normalized == "title" or normalized.startswith("heading")


def _read_docx_document_xml(file_path: Path) -> bytes:
    try:
        with zipfile.ZipFile(file_path) as archive:
            member = archive.getinfo("word/document.xml")
            if member.flag_bits & 0x1:
                raise ValueError("encrypted DOCX files are not supported")
            if member.file_size > MAX_DOCX_DOCUMENT_XML_BYTES:
                raise ValueError("DOCX document XML exceeds the extraction limit")
            with archive.open(member) as stream:
                content = stream.read(MAX_DOCX_DOCUMENT_XML_BYTES + 1)
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Failed to open DOCX file {file_path}: {exc}") from exc
    if len(content) > MAX_DOCX_DOCUMENT_XML_BYTES:
        raise ValueError("DOCX document XML exceeds the extraction limit")
    return content


def parse_docx(file_path: Path) -> ParsedDocument:
    """Extract DOCX paragraphs and split sections on Word heading styles."""
    try:
        root = ElementTree.fromstring(_read_docx_document_xml(file_path))
    except ElementTree.ParseError as exc:
        raise ValueError(f"Failed to parse DOCX file {file_path}: {exc}") from exc

    sections: list[ParsedSection] = []
    current_title: str | None = None
    current_paragraphs: list[str] = []

    def flush_section() -> None:
        text = "\n\n".join(current_paragraphs).strip()
        if text:
            sections.append(ParsedSection(text=text, section_title=current_title))

    for paragraph in root.iter(f"{_WORD_TAG}p"):
        text = _docx_paragraph_text(paragraph)
        if not text:
            continue
        if _is_docx_heading_style(_docx_paragraph_style(paragraph)):
            flush_section()
            current_title = text
            current_paragraphs = [text]
        else:
            current_paragraphs.append(text)
    flush_section()

    return ParsedDocument(
        file_type="docx",
        parser_version=PARSER_VERSION,
        sections=tuple(sections),
    )


def parse_pdf(file_path: Path) -> ParsedDocument:
    """Parse a PDF document page by page using pypdf."""
    sections: list[ParsedSection] = []

    try:
        reader = pypdf.PdfReader(str(file_path))
    except Exception as exc:
        raise ValueError(f"Failed to open PDF file {file_path}: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError(f"Encrypted PDF file {file_path}: {exc}") from exc

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""

        cleaned = page_text.strip()
        if cleaned:
            sections.append(
                ParsedSection(
                    text=cleaned,
                    page_start=page_num,
                    page_end=page_num,
                    section_title=None,
                )
            )

    return ParsedDocument(
        file_type="pdf",
        parser_version=PARSER_VERSION,
        sections=tuple(sections),
    )


def parse_file(file_path: Path, file_type: DocumentFileType) -> ParsedDocument:
    """Parse any supported document file into structured sections."""
    if file_type == "pdf":
        return parse_pdf(file_path)
    if file_type == "docx":
        return parse_docx(file_path)

    text_content = file_path.read_text(encoding="utf-8", errors="replace")
    if file_type == "html":
        return parse_html(text_content)
    if file_type == "markdown":
        return parse_markdown(text_content)
    if file_type == "text":
        return parse_text(text_content)

    raise ValueError(f"Unsupported file type: {file_type}")
