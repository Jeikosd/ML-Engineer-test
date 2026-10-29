"""RAG endpoints — implement `POST /api/ingest` and `POST /api/ask` here.

Keep the router thin; delegate to the RAG / vector / OCR services. Map failures
(bad upload, vector store down, LLM error) to meaningful HTTP status codes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.dependencies import get_embedder, get_ocr_engine, read_pdf
from app.models.schemas import IngestResponse
from app.services.embedding_service import Embedder
from app.services.ocr_service import OcrEngine
from app.services.rag_service import ingest

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest_pdf(
    pdf_file: UploadFile,
    pdf_bytes: Annotated[bytes, Depends(read_pdf)],
    engine: Annotated[OcrEngine, Depends(get_ocr_engine)],
    embed: Annotated[Embedder, Depends(get_embedder)],
):
    return ingest(pdf_bytes, pdf_file.filename, engine, embed)


# TODO: implement POST /api/ask    (response_model=RAGResponse)
