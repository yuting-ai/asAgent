import json
from collections.abc import Mapping
from typing import BinaryIO

import pypdf
import pypdf.errors

MAX_PDF_FILE_BYTES = 20 * 1024 * 1024  # 20 MiB
MAX_PAGE_STREAM_BYTES = 16 * 1024 * 1024  # 16 MiB
MAX_RESULT_CHARS = 18_000
MAX_PAGES_PER_CALL = 10
DEFAULT_PAGE_BATCH = 5
MAX_ACCUMULATED_TEXT_CHARS = 12_000


def parse_page_range(
    arguments: Mapping[str, object],
) -> tuple[int, int, int | None]:
    """Validates and extracts (start_page, start_char_offset, end_page) from tool arguments."""
    start_page_val = arguments.get("start_page", 1)
    if (
        not isinstance(start_page_val, int)
        or isinstance(start_page_val, bool)
        or start_page_val < 1
    ):
        raise ValueError("start_page must be an integer greater than or equal to 1")

    start_char_offset_val = arguments.get("start_char_offset", 0)
    if (
        not isinstance(start_char_offset_val, int)
        or isinstance(start_char_offset_val, bool)
        or start_char_offset_val < 0
    ):
        raise ValueError(
            "start_char_offset must be an integer greater than or equal to 0"
        )

    end_page_val = arguments.get("end_page")
    if end_page_val is not None:
        if (
            not isinstance(end_page_val, int)
            or isinstance(end_page_val, bool)
            or end_page_val < 1
        ):
            raise ValueError("end_page must be an integer greater than or equal to 1")
        if end_page_val < start_page_val:
            raise ValueError("start_page must not exceed end_page")
        if (end_page_val - start_page_val + 1) > MAX_PAGES_PER_CALL:
            raise ValueError("a single call may extract at most 10 pages")

    return start_page_val, start_char_offset_val, end_page_val


def extract_pdf_text_from_stream(
    stream: BinaryIO,
    *,
    start_page: int,
    start_char_offset: int,
    end_page: int | None,
) -> str:
    """Synchronously parses PDF text from a readable/seekable binary stream with offset pagination."""
    try:
        reader = pypdf.PdfReader(stream)
    except pypdf.errors.FileNotDecryptedError as error:
        raise ValueError(
            "PDF is encrypted and password-protected PDFs are not supported"
        ) from error
    except Exception as error:
        raise ValueError("PDF is invalid or corrupted") from error

    if reader.is_encrypted:
        raise ValueError(
            "PDF is encrypted and password-protected PDFs are not supported"
        )

    try:
        page_count = len(reader.pages)
    except Exception as error:
        raise ValueError("PDF is invalid or corrupted") from error

    if page_count == 0:
        raise ValueError("PDF is invalid or corrupted")

    if start_page > page_count:
        raise ValueError("page range exceeds the PDF page count")

    if end_page is None:
        effective_end_page = min(page_count, start_page + DEFAULT_PAGE_BATCH - 1)
    else:
        if end_page > page_count:
            raise ValueError("page range exceeds the PDF page count")
        effective_end_page = end_page

    pages: list[dict[str, object]] = []
    total_text_chars = 0
    truncated = False
    next_position: dict[str, int] | None = None
    last_extracted_page = start_page

    for page_num in range(start_page, effective_end_page + 1):
        page_idx = page_num - 1
        try:
            page = reader.pages[page_idx]
            contents = page.get_contents()
            if contents is not None:
                stream_data = contents.get_data()
                if len(stream_data) > MAX_PAGE_STREAM_BYTES:
                    raise ValueError("PDF page content exceeds the extraction limit")
            raw_text = page.extract_text() or ""
        except ValueError:
            raise
        except Exception as error:
            raise ValueError("PDF is invalid or corrupted") from error

        page_start_offset = start_char_offset if page_num == start_page else 0
        if page_start_offset > len(raw_text):
            raise ValueError("start_char_offset exceeds page text length")

        available_text = raw_text[page_start_offset:]

        if _fits_payload(
            candidate_text=available_text,
            page_num=page_num,
            page_start_offset=page_start_offset,
            total_text_chars=total_text_chars,
            pages=pages,
            page_count=page_count,
            start_page=start_page,
            start_char_offset=start_char_offset,
        ):
            pages.append({"page_number": page_num, "text": available_text})
            total_text_chars += len(available_text)
            last_extracted_page = page_num
        else:
            low = 0
            high = len(available_text)
            best_cut = 0
            while low <= high:
                mid = (low + high) // 2
                if _fits_payload(
                    candidate_text=available_text[:mid],
                    page_num=page_num,
                    page_start_offset=page_start_offset,
                    total_text_chars=total_text_chars,
                    pages=pages,
                    page_count=page_count,
                    start_page=start_page,
                    start_char_offset=start_char_offset,
                ):
                    best_cut = mid
                    low = mid + 1
                else:
                    high = mid - 1

            if best_cut > 0:
                pages.append(
                    {
                        "page_number": page_num,
                        "text": available_text[:best_cut],
                    }
                )
                total_text_chars += best_cut
                last_extracted_page = page_num
                next_position = {
                    "page": page_num,
                    "char_offset": page_start_offset + best_cut,
                }
            else:
                next_position = {
                    "page": page_num,
                    "char_offset": page_start_offset,
                }
            truncated = True
            break

    if not truncated:
        if effective_end_page < page_count:
            next_position = {
                "page": effective_end_page + 1,
                "char_offset": 0,
            }
        else:
            next_position = None

    text_layer_found = any(bool(p["text"] and str(p["text"]).strip()) for p in pages)
    actual_end_page = last_extracted_page if pages else start_page

    payload = {
        "format": "pdf",
        "page_count": page_count,
        "start_page": start_page,
        "start_char_offset": start_char_offset,
        "end_page": actual_end_page,
        "pages": pages,
        "next_position": next_position,
        "text_layer_found": text_layer_found,
        "truncated": truncated,
    }

    return json.dumps(payload, ensure_ascii=False)


def _fits_payload(
    *,
    candidate_text: str,
    page_num: int,
    page_start_offset: int,
    total_text_chars: int,
    pages: list[dict[str, object]],
    page_count: int,
    start_page: int,
    start_char_offset: int,
) -> bool:
    if total_text_chars + len(candidate_text) > MAX_ACCUMULATED_TEXT_CHARS:
        return False
    test_pages = pages + [{"page_number": page_num, "text": candidate_text}]
    test_pos = {
        "page": page_num,
        "char_offset": page_start_offset + len(candidate_text),
    }
    test_payload = {
        "format": "pdf",
        "page_count": page_count,
        "start_page": start_page,
        "start_char_offset": start_char_offset,
        "end_page": page_num,
        "pages": test_pages,
        "next_position": test_pos,
        "text_layer_found": True,
        "truncated": True,
    }
    test_json = json.dumps(test_payload, ensure_ascii=False)
    return len(test_json) <= MAX_RESULT_CHARS
