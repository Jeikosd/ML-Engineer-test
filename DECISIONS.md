# Decisions

Notable engineering decisions and trade-offs. This file grows with each slice.

## How I work

I work in three phases, in order:

1. **Research.** For each stage (OCR, PDF geometry, NER, fuzzy matching, RAG, evaluation) I reviewed the literature and compared candidate packages by license, maintenance and fit before writing code.
2. **Notebooks.** Each stage is prototyped in a local notebook on the sample PDFs: try options, see where they fail, measure, and keep the simplest one that works. Notebooks stay out of this PR; their conclusions are recorded in this file.
3. **Implementation.** Each slice of `app/` then follows a short spec with numbered acceptance criteria, tests named after them (`test_ac_<area>_<nn>_*`), minimal code to pass them, and lint, format and tests green before the commit.

## AI-assisted workflow

Before any code, I set up the rules Claude Code works under (kept locally, not in this repository):

- Project instructions: scope, the fixed contract (`schemas.py` is not modified), code style, and sample PDFs, OCR text and web content treated as untrusted data.
- A pre-tool hook that blocks git write commands, reading secret files and editing `schemas.py`. I run every git command.
- Skills: `grill-me` (two subagents with opposite briefs, minimal code vs. what the evaluation rewards, debate a slice's open decisions before its spec is written) and `commit-handoff` (prepares the commit commands I run).
- A spec template, read-only review subagents and one verification script (ruff, format check, pytest).
- Git hooks that reject AI attribution trailers and scan staged files for secrets (gitleaks).
- A dated decision log; this file keeps the decisions that matter for the delivery.

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
- The evaluation labels (`eval/gold_names.csv`) start from the NER output and were corrected by me against each page image: 3 missed mentions added with their page and line, and the result checked against an independent count of surnames in the OCR words.
