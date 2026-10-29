"""`POST /api/extract`: validate the upload, delegate to the extraction service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile
from pydantic import Json

from app.config import get_settings
from app.dependencies import get_ocr_engine, get_recognizer
from app.models.schemas import ExtractionResponse, NamePair
from app.services.extraction_service import extract
from app.services.ner_service import NameRecognizer
from app.services.ocr_service import DocumentTooLargeError, OcrEngine

router = APIRouter()


@router.post("/extract", response_model=ExtractionResponse)
def extract_names(
    pdf_file: UploadFile,
    names: Annotated[Json[list[NamePair]], Form()],
    engine: Annotated[OcrEngine, Depends(get_ocr_engine)],
    recognizer: Annotated[NameRecognizer, Depends(get_recognizer)],
):
    limit = get_settings().max_upload_mb * 1024 * 1024
    pdf_bytes = pdf_file.file.read(limit + 1)
    if len(pdf_bytes) > limit:
        raise DocumentTooLargeError("upload exceeds the size limit")
    return extract(pdf_bytes, names, engine, recognizer)
