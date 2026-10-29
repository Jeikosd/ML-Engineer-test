"""RAG: chunk text, and answer questions grounded in retrieved context.

Implement this. Reminders (graded): chunking must not cut words in half; the
LLM call needs a timeout and retries; the answer must be grounded in the
retrieved chunks and ``sources`` must reflect what was actually retrieved (no
fabricated sources); handle a missing/failing LLM cleanly.
"""

import hashlib

from app.config import get_settings
from app.log import log_event
from app.models.schemas import IngestResponse
from app.services.embedding_service import Embedder
from app.services.ocr_service import OcrEngine, ocr_pages, page_text
from app.services.vector_service import store_document_chunks


def ingest(
    pdf_bytes: bytes, filename: str, engine: OcrEngine, embed: Embedder
) -> IngestResponse:
    """OCR a PDF, chunk each page and store the chunks in the vector store."""
    settings = get_settings()
    doc_id = hashlib.sha256(pdf_bytes).hexdigest()
    pages = ocr_pages(pdf_bytes, engine)
    chunks, metadata = [], []
    for page, words in enumerate(pages):
        text, _ = page_text(words)
        for number, chunk in enumerate(
            chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        ):
            chunks.append(chunk)
            metadata.append(
                {"doc_id": doc_id, "filename": filename, "page": page, "chunk": number}
            )
    store_document_chunks(chunks, metadata, embed)
    log_event(pages=len(pages), chunks=len(chunks))
    return IngestResponse(status="ingested", chunks_stored=len(chunks))


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 60) -> list[str]:
    """Split text into whole-word chunks; each starts with the previous one's tail."""
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    chunks, current = [], []
    for word in text.split():
        if current and len(" ".join([*current, word])) > chunk_size:
            chunks.append(" ".join(current))
            tail = []
            for previous in reversed(current):
                tail_len = len(" ".join([previous, *tail]))
                if tail_len > overlap or tail_len + 1 + len(word) > chunk_size:
                    break
                tail = [previous, *tail]
            current = tail
        current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def generate_answer(question: str) -> dict:
    """Retrieve context and return ``{"answer", "sources"}``."""
    raise NotImplementedError
