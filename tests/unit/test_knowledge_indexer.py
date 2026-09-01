import io
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pypdf
import pytest
from alembic.config import Config
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from alembic import command
from asagent.core.ids import LibraryId, SourceId, UserId
from asagent.knowledge.indexer import KnowledgeIndexer
from asagent.knowledge.models import (
    KnowledgeIndexJob,
    KnowledgeLibrary,
    KnowledgeSource,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
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


def _make_docx(title: str, body: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        f"<w:r><w:t>{title}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>{body}</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.fixture
async def indexer_setup(
    tmp_path: Path,
) -> AsyncIterator[
    tuple[SqliteKnowledgeRepository, KnowledgeIndexer, KnowledgeSource, Path]
]:
    db_path = tmp_path / "asagent.sqlite3"
    _upgrade(db_path)
    repo = SqliteKnowledgeRepository(db_path)

    fixed_now = datetime(2026, 8, 31, 13, 0, 0, tzinfo=UTC)
    indexer = KnowledgeIndexer(
        repository=repo,
        now=lambda: fixed_now,
    )

    user_id = UserId("u_indexer")
    now = fixed_now

    # Create library and source
    lib = KnowledgeLibrary(
        library_id=LibraryId("lib_idx"),
        user_id=user_id,
        name="Indexer Test Lib",
        normalized_name="indexer test lib",
        status="active",
        created_at=now,
        updated_at=now,
    )
    await repo.save_library(lib)

    source_dir = tmp_path / "source_folder"
    source_dir.mkdir()

    src = KnowledgeSource(
        source_id=SourceId("src_idx"),
        library_id=LibraryId("lib_idx"),
        display_path=str(source_dir),
        canonical_path=str(source_dir.resolve()),
        status="active",
        scan_status="queued",
        created_at=now,
        updated_at=now,
    )
    await repo.save_source(src)

    try:
        yield repo, indexer, src, source_dir
    finally:
        await repo.aclose()


async def test_initial_indexing_and_cache_reuse(
    indexer_setup: tuple[
        SqliteKnowledgeRepository, KnowledgeIndexer, KnowledgeSource, Path
    ],
) -> None:
    repo, indexer, src, source_dir = indexer_setup

    # 1. Populate initial files
    notes_file = source_dir / "notes.md"
    notes_file.write_text("# Chapter 1\n\nInitial notes on indexing.", encoding="utf-8")

    pdf_file = source_dir / "doc.pdf"
    pdf_file.write_bytes(_make_pdf(["Page one content in test PDF."]))

    # Run initial index
    stats1 = await indexer.index_source(src.source_id)
    assert stats1.total_scanned == 2
    assert stats1.added_docs == 2
    assert stats1.unchanged_docs == 0
    assert stats1.modified_docs == 0
    assert stats1.deleted_docs == 0
    assert stats1.new_chunks >= 2

    # Check source status & documents in DB
    updated_src = await repo.get_source(src.source_id)
    assert updated_src is not None
    assert updated_src.scan_status == "ready"

    docs = await repo.list_documents_for_source(src.source_id)
    assert len(docs) == 2
    assert all(d.status == "active" for d in docs)

    # 2. Run index again with no changes -> 100% cache reuse
    stats2 = await indexer.index_source(src.source_id)
    assert stats2.total_scanned == 2
    assert stats2.added_docs == 0
    assert stats2.unchanged_docs == 2
    assert stats2.modified_docs == 0
    assert stats2.deleted_docs == 0
    assert stats2.new_chunks == 0
    assert stats2.total_chunks == stats1.total_chunks


async def test_docx_and_html_flow_through_the_full_indexer(
    indexer_setup: tuple[
        SqliteKnowledgeRepository, KnowledgeIndexer, KnowledgeSource, Path
    ],
) -> None:
    repo, indexer, src, source_dir = indexer_setup
    (source_dir / "report.docx").write_bytes(
        _make_docx("Methods", "The DOCX retrieval pipeline was evaluated locally.")
    )
    (source_dir / "article.html").write_text(
        "<html><head><title>Web Research</title></head>"
        "<body><h2>Results</h2><p>The HTML index is searchable.</p></body></html>",
        encoding="utf-8",
    )

    stats = await indexer.index_source(src.source_id)
    documents = await repo.list_documents_for_source(src.source_id)
    by_path = {document.relative_path: document for document in documents}
    docx_chunks = await repo.list_active_chunks_for_document(
        by_path["report.docx"].document_id
    )
    html_chunks = await repo.list_active_chunks_for_document(
        by_path["article.html"].document_id
    )

    assert stats.total_scanned == 2
    assert stats.added_docs == 2
    assert by_path["report.docx"].file_type == "docx"
    assert by_path["article.html"].file_type == "html"
    assert "DOCX retrieval pipeline" in " ".join(chunk.text for chunk in docx_chunks)
    assert "HTML index is searchable" in " ".join(chunk.text for chunk in html_chunks)


async def test_incremental_modification_and_deletion(
    indexer_setup: tuple[
        SqliteKnowledgeRepository, KnowledgeIndexer, KnowledgeSource, Path
    ],
) -> None:
    repo, indexer, src, source_dir = indexer_setup

    notes_file = source_dir / "notes.md"
    notes_file.write_text("# Chapter 1\n\nOriginal text.", encoding="utf-8")

    pdf_file = source_dir / "to_delete.pdf"
    pdf_file.write_bytes(_make_pdf(["PDF to be deleted later."]))

    # Initial index
    await indexer.index_source(src.source_id)

    # Modify notes.md and delete to_delete.pdf
    notes_file.write_text("# Chapter 1\n\nModified new content!", encoding="utf-8")
    pdf_file.unlink()

    # Add a brand new text file
    new_txt = source_dir / "new.txt"
    new_txt.write_text("New plaintext file.", encoding="utf-8")

    # Run incremental index
    stats = await indexer.index_source(src.source_id)
    assert stats.total_scanned == 2  # notes.md and new.txt
    assert stats.added_docs == 1  # new.txt
    assert stats.modified_docs == 1  # notes.md
    assert stats.deleted_docs == 1  # to_delete.pdf
    assert stats.unchanged_docs == 0

    # Verify missing status
    all_docs = await repo.list_documents_for_source(src.source_id)
    by_path = {d.relative_path: d for d in all_docs}
    assert by_path["to_delete.pdf"].status == "missing"
    assert by_path["notes.md"].status == "active"
    assert by_path["new.txt"].status == "active"


async def test_failed_replacement_keeps_previous_document_and_retries(
    indexer_setup: tuple[
        SqliteKnowledgeRepository, KnowledgeIndexer, KnowledgeSource, Path
    ],
) -> None:
    repo, indexer, src, source_dir = indexer_setup
    pdf_file = source_dir / "paper.pdf"
    pdf_file.write_bytes(_make_pdf(["Previously indexed content."]))
    await indexer.index_source(src.source_id)

    original_document = (await repo.list_documents_for_source(src.source_id))[0]
    original_chunks = await repo.list_active_chunks_for_document(
        original_document.document_id
    )
    pdf_file.write_bytes(b"not a valid PDF")

    first_failure = await indexer.index_source(src.source_id)
    second_failure = await indexer.index_source(src.source_id)
    retained_document = (await repo.list_documents_for_source(src.source_id))[0]
    retained_chunks = await repo.list_active_chunks_for_document(
        retained_document.document_id
    )

    assert first_failure.modified_docs == 1
    assert second_failure.modified_docs == 1
    assert retained_document.content_hash == original_document.content_hash
    assert retained_chunks == original_chunks


async def test_job_cancellation(
    indexer_setup: tuple[
        SqliteKnowledgeRepository, KnowledgeIndexer, KnowledgeSource, Path
    ],
) -> None:
    repo, indexer, src, source_dir = indexer_setup

    f = source_dir / "test.md"
    f.write_text("# Header\nText", encoding="utf-8")

    from asagent.core.ids import IndexJobId

    job_id = IndexJobId("job_cancel_test")

    # Create job pre-cancelled
    now = datetime(2026, 8, 31, 13, 0, 0, tzinfo=UTC)
    job = KnowledgeIndexJob(
        job_id=job_id,
        library_id=src.library_id,
        kind="initial",
        status="running",
        discovered_files=0,
        processed_files=0,
        skipped_files=0,
        failed_files=0,
        total_chunks=0,
        indexed_chunks=0,
        cancel_requested=True,
        created_at=now,
        updated_at=now,
        source_id=src.source_id,
        last_error_code=None,
        started_at=now,
        completed_at=None,
    )
    await repo.save_index_job(job)

    stats = await indexer.index_source(src.source_id, job_id=job_id)
    assert stats.added_docs == 0

    saved_job = await repo.get_index_job(job_id)
    assert saved_job is not None
    assert saved_job.status == "cancelled"
