"""Dependencies injected into the routers (tests override them with fakes)."""

from app.services.ner_service import NameRecognizer, spacy_persons
from app.services.ocr_service import OcrEngine, tesseract_data


def get_ocr_engine() -> OcrEngine:
    return tesseract_data


def get_recognizer() -> NameRecognizer:
    return spacy_persons
