from app.config import Settings


def test_ac_cfg_01_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("OCR_DPI", "150")

    settings = Settings(_env_file=None)

    assert settings.ocr_dpi == 150
    assert settings.ocr_lang == "eng"
