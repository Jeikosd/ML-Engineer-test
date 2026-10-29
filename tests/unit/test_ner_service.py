import pytest

from app.config import Settings
from app.services import ner_service
from app.services.ner_service import extract_names, find_person_spans


@pytest.fixture(autouse=True)
def default_settings(monkeypatch):
    monkeypatch.setattr(ner_service, "get_settings", lambda: Settings(_env_file=None))


def test_ac_ner_02_filters_drop_non_names():
    page = "Robert Chen\nCFO Chen JOHN SMITH"
    spans = [("Robert Chen\nCFO", 0, 15), ("Chen", 16, 20), ("JOHN SMITH", 21, 31)]

    assert find_person_spans([page], {page: spans}.get) == [[]]


def test_ac_ner_05_all_caps_kept_when_disabled(monkeypatch):
    keep = Settings(_env_file=None, ner_drop_all_caps=False)
    monkeypatch.setattr(ner_service, "get_settings", lambda: keep)

    result = find_person_spans(["JOHN SMITH"], lambda text: [("JOHN SMITH", 0, 10)])

    assert result == [[("JOHN SMITH", 0, 10)]]


def test_ac_ner_07_extract_names_unique_and_empty(monkeypatch):
    spans = [("Ann Lee", 0, 7), ("Bob Ray", 12, 19), ("Ann Lee", 25, 32)]
    monkeypatch.setattr(ner_service, "spacy_persons", lambda text: spans)

    assert extract_names("Ann Lee met Bob Ray, then Ann Lee") == ["Ann Lee", "Bob Ray"]
    assert find_person_spans([]) == []
    monkeypatch.setattr(ner_service, "spacy_persons", lambda text: [])
    assert extract_names("") == []
