# Decisions

Notable engineering decisions and trade-offs. This file grows with each slice.

## Environment and dependencies

- **Python 3.12 pinned** (`.python-version`) and `uv.lock` committed, so every machine resolves the same versions.
- **`rapidfuzz` directly, instead of `thefuzz` + `python-Levenshtein`.** `thefuzz` 0.22 is a thin wrapper over `rapidfuzz`, and `python-Levenshtein` is GPL-2.0-or-later and not needed. Same scorers, one layer and one copyleft dependency less.
- **spaCy model as a locked dependency.** `en_core_web_sm` 3.8.0 is pinned by URL in `[tool.uv.sources]`, so its version lives in `uv.lock`. No `spacy download` step: it installs through `pip`, which a uv virtual environment does not include.
- **`dev` kept as an optional extra** (`pytest`, `pytest-cov`, `ruff`), so `uv sync --extra dev` from the README keeps working. `pytest-asyncio` removed: no async tests are needed.
- **CPU-only PyTorch on every platform.** `torch` is pinned to the official CPU index (`download.pytorch.org/whl/cpu`, `explicit = true`), so the lock contains no CUDA packages. Embedding a few chunks with a small model does not need a GPU, installs stay small (also in Docker), and a local GPU stays free for the LLM.
- **`tenacity`** is included for retry policies on external calls (LLM; vector store when it runs as a separate service).
- **ruff with the default 88 columns**, matching the style of the provided stubs, so formatting does not touch files outside each change.

## Configuration

- **Single source of settings** in `app/config.py` (pydantic-settings). Precedence: environment variable, then `.env`, then the default in code. Values are typed (`OCR_DPI=150` arrives as an `int`).
- OCR DPI, language, page segmentation mode and timeout are configurable.
- **The `tesseract` binary is resolved from `PATH`**, like any command-line tool, instead of a configurable path. Linux package managers install it on `PATH`; the Windows installer does not, so the setup step there is to add it. Trade-off: one less setting, but Tesseract must be on `PATH`.
- `.env.example` documents every key. `.gitignore` un-ignores it (`!.env.example`) because the original `.env.*` rule excluded it.

## Use of AI tools

- Claude Code (Anthropic) was used as a pair-programmer: researching options, drafting code and tests, and reviewing. The author reviewed and ran every change, owns every line, and made every commit.
