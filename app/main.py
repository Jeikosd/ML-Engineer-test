"""FastAPI application entrypoint.

Assemble the app here: mount the routers under ``/api``, add ``GET /health``,
and wire whatever cross-cutting concerns you decide on (config, logging,
error handling, lifecycle). This skeleton just registers the routers.
"""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.extract import router as extract_router
from app.api.rag import router as rag_router
from app.log import log_requests
from app.services.ocr_service import (
    DocumentTooLargeError,
    InvalidPdfError,
    OcrEngineError,
)
from app.services.vector_service import VectorStoreError

ERROR_STATUS = {
    InvalidPdfError: 422,
    DocumentTooLargeError: 413,
    OcrEngineError: 503,
    VectorStoreError: 503,
}

logging.basicConfig(format="%(message)s")
logging.getLogger("app").setLevel(logging.INFO)  # ours only; libraries stay at WARNING

app = FastAPI(title="Document Intelligence Service")
app.middleware("http")(log_requests)


def domain_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=ERROR_STATUS[type(exc)])


for error in ERROR_STATUS:
    app.add_exception_handler(error, domain_error)

app.include_router(extract_router, prefix="/api", tags=["extraction"])
app.include_router(rag_router, prefix="/api", tags=["rag"])


@app.get("/health")
def health():
    return {"status": "ok"}
