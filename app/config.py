"""Centralized, environment-overridable settings (read from env vars or `.env`)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OCR (the `tesseract` binary is resolved from PATH)
    ocr_dpi: int = 300
    ocr_lang: str = "eng"
    ocr_psm: int = 3
    ocr_timeout_s: int = 30

    # Embeddings
    embedding_device: str = "cpu"


@lru_cache
def get_settings() -> Settings:
    return Settings()
