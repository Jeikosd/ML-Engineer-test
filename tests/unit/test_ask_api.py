import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_embedder, get_llm
from app.main import app
from app.services.llm_client import (
    LLMBadResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.services.vector_service import store_document_chunks
from tests.unit.test_rag_service import FakeLLM, table_embed, unit

QUESTION = "what did Richard Hernandez say?"
CHUNK = "Richard Hernandez called the meeting to order."


@pytest.fixture
def client(chroma):
    """App whose embedder sends the question and one stored chunk to the same vector."""
    embed = table_embed({QUESTION: unit(1.0), CHUNK: unit(1.0)})
    metadata = [{"doc_id": "a", "filename": "a.pdf", "page": 0, "chunk": 0}]
    store_document_chunks([CHUNK], metadata, embed)
    app.dependency_overrides[get_embedder] = lambda: embed
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ac_ask_05_ask_returns_rag_response(client, caplog):
    caplog.set_level(logging.INFO, logger="app")
    app.dependency_overrides[get_llm] = lambda: FakeLLM("He opened the meeting.")

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "He opened the meeting.",
        "sources": ["a.pdf:p0:c0"],
    }
    events = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app"]
    assert any(e.get("chunks") == 1 and e.get("abstained") is False for e in events)
    assert "Richard" not in caplog.text


def test_ac_ask_05_empty_question_is_422(client):
    response = client.post("/api/ask", json={"question": ""})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (LLMUnavailableError, 503),
        (LLMTimeoutError, 504),
        (LLMBadResponseError, 502),
    ],
)
def test_ac_ask_05_llm_errors_map_to_http(client, error, status):
    def failing_llm(messages):
        raise error("llm failed")

    app.dependency_overrides[get_llm] = lambda: failing_llm

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == status
    assert response.json() == {"detail": "llm failed"}
