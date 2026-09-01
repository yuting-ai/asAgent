import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from asagent.core.ids import ChunkId, DocumentId
from asagent.knowledge.models import KnowledgeChunk
from asagent.knowledge.parser import ParsedDocument, ParsedSection

CHUNKER_VERSION = "token-sliding-v1"
DEFAULT_TARGET_TOKENS = 256
DEFAULT_OVERLAP_TOKENS = 32
MIN_CHUNK_TOKENS = 10


def count_tokens_simple(text: str) -> int:
    """Fast whitespace/subword token estimator when formal tokenizer is not supplied."""
    if not text:
        return 0
    words = text.split()
    # Average ~1.3 tokens per whitespace word for English/code, or character count for CJK
    cjk_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return max(1, len(words) + cjk_chars)


def split_section_into_chunks(
    section: ParsedSection,
    *,
    token_counter: Callable[[str], int],
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """Split a single parsed section into overlapping text chunks respecting paragraph boundaries."""
    raw_text = section.text.strip()
    if not raw_text:
        return []

    total_tokens = token_counter(raw_text)
    if total_tokens <= target_tokens:
        return [raw_text]

    # Split on double newline first (paragraphs), then fallback to lines/sentences
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    segments: list[str] = []
    for p in paragraphs:
        if token_counter(p) > target_tokens:
            lines = [line.strip() for line in p.splitlines() if line.strip()]
            for line in lines:
                if token_counter(line) > target_tokens:
                    # Break long lines by sentences or word chunks
                    words = line.split()
                    step = max(1, target_tokens - overlap_tokens)
                    for i in range(0, len(words), step):
                        sub = " ".join(words[i : i + target_tokens])
                        if sub:
                            segments.append(sub)
                else:
                    segments.append(line)
        else:
            segments.append(p)

    chunks: list[str] = []
    current_segments: list[str] = []
    current_tokens = 0

    for seg in segments:
        seg_tokens = token_counter(seg)
        if current_tokens + seg_tokens > target_tokens and current_segments:
            chunk_text = "\n\n".join(current_segments).strip()
            if chunk_text:
                chunks.append(chunk_text)

            # Build overlap from the end of current_segments
            overlap_segments: list[str] = []
            overlap_count = 0
            for prev_seg in reversed(current_segments):
                prev_tok = token_counter(prev_seg)
                if overlap_count + prev_tok <= overlap_tokens or not overlap_segments:
                    overlap_segments.insert(0, prev_seg)
                    overlap_count += prev_tok
                else:
                    break

            current_segments = overlap_segments
            current_tokens = sum(token_counter(s) for s in current_segments)

        current_segments.append(seg)
        current_tokens += seg_tokens

    if current_segments:
        final_text = "\n\n".join(current_segments).strip()
        if final_text and (not chunks or final_text != chunks[-1]):
            chunks.append(final_text)

    return chunks


def chunk_document(
    *,
    document_id: DocumentId,
    document_content_hash: str,
    parsed_doc: ParsedDocument,
    token_counter: Callable[[str], int] | None = None,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    new_chunk_id: Callable[[], ChunkId] | None = None,
    now: Callable[[], datetime] | None = None,
) -> tuple[KnowledgeChunk, ...]:
    """Chunk a parsed document into immutable KnowledgeChunks with deterministic hashes."""
    count_fn = token_counter or count_tokens_simple
    id_fn = new_chunk_id or (lambda: ChunkId(f"chk_{uuid.uuid4().hex[:12]}"))
    time_fn = now or (lambda: datetime.now(UTC))

    created_time = time_fn()
    all_chunks: list[KnowledgeChunk] = []
    chunk_index = 0

    for section in parsed_doc.sections:
        section_chunks = split_section_into_chunks(
            section,
            token_counter=count_fn,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )

        for text in section_chunks:
            # Deterministic chunk hash
            hash_input = f"{document_content_hash}:{chunk_index}:{text}".encode()
            content_hash = hashlib.sha256(hash_input).hexdigest()
            token_count = count_fn(text)

            chunk = KnowledgeChunk(
                chunk_id=id_fn(),
                document_id=document_id,
                document_content_hash=document_content_hash,
                chunk_index=chunk_index,
                text=text,
                token_count=token_count,
                content_hash=content_hash,
                chunker_version=CHUNKER_VERSION,
                status="active",
                created_at=created_time,
                page_start=section.page_start,
                page_end=section.page_end,
                section_title=section.section_title,
            )
            all_chunks.append(chunk)
            chunk_index += 1

    return tuple(all_chunks)
