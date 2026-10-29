# Decisions

Notable engineering decisions and trade-offs. This file grows with each slice.

## How I work

I work in three phases, in order:

1. **Research.** For each stage (OCR, PDF geometry, NER, fuzzy matching, RAG, evaluation) I reviewed the literature and compared candidate packages by license, maintenance and fit before writing code.
2. **Notebooks.** Each stage is prototyped in a local notebook on the sample PDFs: try options, see where they fail, measure, and keep the simplest one that works. Notebooks stay out of this PR; their conclusions are recorded in this file.
3. **Implementation.** Each slice of `app/` then follows a short spec with numbered acceptance criteria, tests named after them (`test_ac_<area>_<nn>_*`), minimal code to pass them, and lint, format and tests green before the commit.

Decisions that rest on published work cite it inline (author, year, section or table); full references are listed at the end of this file. Where a paper supports an idea but did not test our exact setup, the text says so and points to my own measurement.

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

## Fuzzy matching

- **Normalization before comparing:** `casefold`, Unicode NFKD with combining marks removed, apostrophes deleted (so `O'Brien`, `O’Brien` and `OBrien` share one key), other punctuation turned into spaces, and the titles Dr/Mr/Mrs/Ms/Miss/Prof dropped. Titles are one of the sources of name variation listed by Christen (2006, Sec. 2.1); without dropping them, "Dr. Robert Chen" vs "Robert Chen" scores 0.88.
- **Score = max(`fuzz.ratio`, `fuzz.token_sort_ratio`) / 100.** Both are full-string Indel similarities. For person names, edit-distance metrics beat token-based ones (Cohen et al. 2003, Table 2, Census data). `token_sort` handles reversed order ("Gonzalez Maria": 1.0 vs 0.571 with `ratio`); `ratio` handles a typo that sorting would move ("Katherine Dubois": 0.9375 vs 0.50). Taking the best of both orders follows Christen's "Permuted-Winkler" idea (2006, Sec. 3.2); applying it to Indel is my inference, measured on the labeled pairs below. `partial_ratio`, `token_set_ratio` and `WRatio` are not used: they give 1.0 to "Maria" vs "Maria Gonzalez".
- **Threshold 0.90 (the README default), configurable with `FUZZY_THRESHOLD`** and validated to [0, 1]. The function keeps the stub's two-argument signature; `threshold=None` reads the setting at call time.
- **Output:** every pair at or above the threshold, filtered on the raw score and rounded to 4 decimals only for output, sorted by score and then by name. Names are deduplicated by normalized key on both sides (the first spelling is kept), and names that normalize to an empty string are dropped (`ratio("", "")` is 100).
- **Measured on 27 labeled pairs** (`eval/gold_fuzzy_pairs.csv`: 15 same-person variants, 12 hard negatives): recall 12/15 and false-positive rate 4/12, each with a 95 % Wilson interval ([0.55, 0.93] and [0.14, 0.61]), because the Wald interval breaks down at small n (Brown, Cai & DasGupta 2001). Precision and F1 are not reported: they depend on the positive/negative mix I chose, and F1 weighs precision and recall differently by method and threshold (Hand & Christen 2018). These are resubstitution numbers: the same pairs informed the choice of scorer, and Christen (2006) notes that thresholds depend on the data.
- **Known limits:** initials ("J. Anderson"), middle names, two or more OCR errors in one name, and names one letter apart (Mario/Maria) are not resolved; `ø`/`ł` are not folded and `ü` does not become `ue`.

## Person NER

- **spaCy `en_core_web_sm`, label PERSON only**, behind a `NameRecognizer` Protocol, so unit tests use a fake (a lambda) and never load the model. The model is loaded once per name with `lru_cache`, on first use, not at import.
- **Spans per page, `(name, start, end)`.** Box lookup (OCR words) needs character offsets on each page's text, so `find_person_spans(pages)` works page by page. `extract_names(text)` keeps the stub's signature and treats the text as one page.
- **Three filters**, from the error analysis on the samples: a span that crosses a line break, a single word, or ALL CAPS (headers) is not a person name. Only the ALL CAPS filter is configurable (`NER_DROP_ALL_CAPS`), because it depends on the document type; "two words or more" defines a full name and keeps propagation safe.
- **Document-level propagation.** A name found on any page is also marked at its other exact, whole-word occurrences in the same document (never across documents). Within a document the same string rarely changes entity type (Finkel et al. 2005, Sec. 5.1, Table 3), and document-level consistency adds +2.95 F1 on persons while corpus-level adds only +0.09 (Krishnan & Manning 2006, Table 3); the principle goes back to "one sense per discourse" (Gale et al. 1992). Gains depend on the text type (Ratinov & Roth 2009), so I measured it: recall 0.945 → 0.982, no new false positives.
- **Measured on 55 labeled mentions** (`eval/gold_names.csv`, 3 sample PDFs): precision 54/54 = 1.0, recall 54/55 = 0.982. `app/` reproduces the notebook's spans exactly. Same caveat as fuzzy matching: these are the samples that guided the filters.
- **Known limits:** propagation is case-sensitive ("ROBERT CHEN" is not linked to "Robert Chen"); single-word mentions are dropped on purpose; a propagated span partially overlapping a longer spaCy span would give two spans (0 cases in the samples).

## Use of AI tools

- Claude Code (Anthropic) was used as a pair-programmer: researching options, drafting code and tests, and reviewing. The author reviewed and ran every change, owns every line, and made every commit.
- The evaluation labels (`eval/gold_names.csv`) start from the NER output and were corrected by me against each page image: 3 missed mentions added with their page and line, and the result checked against an independent count of surnames in the OCR words.

## References

- Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for a binomial proportion. *Statistical Science*, 16(2), 101–133.
- Christen, P. (2006). *A comparison of personal name matching: Techniques and practical issues*. Technical Report TR-CS-06-02, The Australian National University.
- Cohen, W. W., Ravikumar, P., & Fienberg, S. E. (2003). A comparison of string metrics for matching names and records. *KDD Workshop on Data Cleaning and Object Consolidation*.
- Finkel, J. R., Grenager, T., & Manning, C. (2005). Incorporating non-local information into information extraction systems by Gibbs sampling. *ACL 2005*.
- Gale, W. A., Church, K. W., & Yarowsky, D. (1992). One sense per discourse. *DARPA Speech and Natural Language Workshop*.
- Hand, D., & Christen, P. (2018). A note on using the F-measure for evaluating record linkage algorithms. *Statistics and Computing*, 28(3), 539–547.
- Krishnan, V., & Manning, C. D. (2006). An effective two-stage model for exploiting non-local dependencies in named entity recognition. *COLING-ACL 2006*.
- Ratinov, L., & Roth, D. (2009). Design challenges and misconceptions in named entity recognition. *CoNLL 2009*.
