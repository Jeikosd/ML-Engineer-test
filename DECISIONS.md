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

## OCR and bounding boxes

- **Bytes in, one open.** `ocr_pages(pdf_bytes)` opens the PDF once with `pymupdf.open(stream=..., filetype="pdf")`: the upload is already in memory, so no temp files. pymupdf still opens an image (a PNG) as a document even with `filetype="pdf"`, so the code also checks `doc.is_pdf`. Empty, non-PDF, image or corrupt bytes raise `InvalidPdfError` (it wraps pymupdf's `FileDataError`), so the endpoint maps it without importing pymupdf. The path-based stubs read the file and delegate.
- **Every page, boxes in PDF points.** Each page is rendered at `OCR_DPI` (300) in grayscale and read by Tesseract behind an `OcrEngine` Protocol (unit tests use a fake). Pixels become points with `page.rect.width / pix.width`, so no DPI is hard-coded (the test runs at 150 DPI to catch that). Words with `conf < 0` or blank text are dropped.
- **Origin is configurable.** Top-left by default, like the image; `BBOX_ORIGIN=bottom-left` flips each word (`y = H - y - h`) for PDF-native consumers. The flip is monotonic, so the union box does not change shape.
- **Boxes by offsets, not string search.** NER spans and OCR words share the same page text, so a name's box is the union of the words its span touches. There is no string comparison to break on case or OCR noise. NER runs once over all pages, so a name found on one page is also boxed on the others.
- **One box per occurrence.** 0 of 54 mentions cross a line (NER drops those), and `ExtractedName` has one box. Edge punctuation stays inside ("Thompson," → about 5 pt wider on 19/54 mentions); the box still contains the name.
- **Measured.** A synthetic scanned PDF (fonts 11/14/24) gives a box inside the text box (±1 pt) with ≥ 0.95 of its width; IoU is not used because the reference is a line box and Tesseract boxes the ink. On the 3 samples: precision 1.0, recall 54/55, every box within ±2 pt of `eval/gold_boxes.csv`, and `app/` matches the notebook prototype exactly (0.0 pt). The miss (Lucas Zimmermann) is an NER miss: OCR reads both words.
- **License note.** pymupdf is AGPL-3.0 (or Artifex commercial). Fine for this take-home; for a closed product, pypdfium2 (Apache/BSD) would replace the renderer.

## Extraction endpoint

- **Thin router, pure pipeline.** `POST /api/extract` reads the upload and delegates to `extract(pdf_bytes, names, engine, recognizer)`, a plain function (no state, so no class) that runs OCR → NER → boxes → fuzzy match. The OCR engine and the name recognizer are injected with `Depends`; tests replace them through `app.dependency_overrides`, so unit tests never run Tesseract or spaCy.
- **`names` validated by FastAPI.** The form field is declared as `Json[list[NamePair]]`, so invalid JSON, a missing field or an empty name returns FastAPI's own 422 before any OCR runs.
- **Errors by content, mapped in one place.** Three domain errors and one status table in `main.py`: `InvalidPdfError` → 422 (empty, not a PDF, an image, corrupt, or password-protected), `DocumentTooLargeError` → 413 (`MAX_UPLOAD_MB`, `MAX_PAGES`), `OcrEngineError` → 503 (Tesseract timeout or missing binary). There is no `%PDF-` magic check: the parser already rejects non-PDFs by content, and the PDF format allows bytes before the header. A password-protected PDF opens without error and fails only when rendered, so `ocr_pages` checks `needs_pass` right after opening; the page limit is checked in the same open, before rendering.
- **Upload limit.** The router reads at most `MAX_UPLOAD_MB` + 1 byte. Starlette has already received the body (spooled to disk above 1 MB) and closes the file after the request, so the limit rejects the upload but does not save the transfer; in production a proxy limit would.
- **Structured logs without PII.** One JSON line per request (method, path, status, ms) and one per extraction (pages, names in, names found, matches), both tagged with a request id taken from `X-Request-ID` or generated, and returned in the response header. Names are never logged. Standard library only.
- **Measured.** On `company_memo.pdf` with the fuzzy notebook's query list, the endpoint returns the 8 mentions on page 0 and the 3 expected matches (integration test, skipped without Tesseract or the spaCy model).

## RAG ingestion

- **Chunks per page, 500 characters, 60 of overlap, cut only between words.** Each page's OCR text is split on whitespace; words are packed until the next one would pass 500 characters, and the next chunk starts with the last whole words that fit in 60 characters.
  *Why:* the README forbids cutting words; chunking per page keeps the page number exact for `sources`; 500 characters is about 75 MiniLM tokens, far below its 256-token limit, so nothing is truncated.
- **This strategy over five alternatives, for robustness rather than a metric.** Compared with paired tests (exact McNemar on hit@1, paired bootstrap of ΔMRR) on 22 questions with labeled pages (`eval/questions.json`, plus 4 with no answer): no overlap, sentences, recursive splitting, whole page, whole document.
  *Why:* none differed significantly (all p ≥ 0.45, every ΔMRR interval contains 0), so the metric cannot choose. Overlap keeps a name that falls on a chunk border ("Jennifer Liu") whole in one chunk, and Chroma's own evaluation finds overlap neutral to slightly positive for this model (78.7 vs 78.5 recall, 250 tokens with 125 vs 0 overlap; Smith & Troynikov 2024). Whole document was the worst (ΔMRR −0.078) and loses the page. Semantic chunking was not tried: Qu et al. (2024) find it does not justify its cost.
- **No OCR text normalization.**
  *Why:* OCR noise degrades RAG (Zhang et al. 2025), but joining hyphens and collapsing whitespace did not change the metrics on our documents; code that changes nothing measurable is not added.
- **Metrics read as regression checks, not as quality estimates.** Reference: hit@1 0.68 [0.47, 0.84], hit@3 0.95, MRR 0.82 [0.71, 0.93].
  *Why:* with 5 pages in total, hit@3 is close to 1 for every strategy and 22 questions only detect large differences; the numbers say "it did not get worse", not how it would do on a real corpus.
- **Measured: `app/` reproduces the prototype.** On the sample pages, `chunk_text` gives the same 12 chunks as the notebook prototype, and retrieval through `store_document_chunks` and `search_similar` ranks all 22 questions exactly as the prototype does.
  *Why:* the notebook is where the strategy was chosen; this check shows the code that ships is that strategy and not a variant of it.
- **`all-MiniLM-L6-v2`, normalized embeddings.**
  *Why:* `bge-small-en-v1.5` scores higher on MTEB retrieval (51.68 vs 41.95; Muennighoff et al. 2023) but tied on our questions, so the change would not be measurable here. Normalized vectors make cosine, dot product and L2 rank the same.
- **Embedding model stored in the collection metadata and checked on reopen.**
  *Why:* MiniLM and bge-small both have 384 dimensions, so switching models without re-ingesting would mix vectors from two models with no error. A mismatch raises `VectorStoreError`.
- **Chroma `PersistentClient`, one per process, one collection, cosine, explicit vectors.** Created with `{"hnsw": {"space": "cosine"}}` and `embedding_function=None`; queries always pass vectors; `score = 1 - distance`.
  *Why:* Chroma's default is squared L2, which is not the score we want to report; without `embedding_function=None`, a text query makes Chroma download its own ONNX model (about 79 MB) and embed with a different model. One client per process avoids reopening the store on each request.
- **IDs `doc_id:page:chunk`, with `doc_id` the SHA-256 of the PDF bytes; `filename` in the metadata.**
  *Why:* the README requires IDs unique across documents; hashing the bytes makes the same PDF map to the same chunks under any filename. A re-scan has different bytes and counts as a new document.
- **Re-ingestion deletes the document's chunks, then adds the new ones.**
  *Why:* Chroma silently drops an `add` whose ID already exists (the old text stays), and `upsert` would leave stale chunks when a new version has fewer of them.
- **`ChromaError` → `VectorStoreError` → 503.**
  *Why:* `ChromaError` is the common base of Chroma's internal, not-found and invalid-argument errors, so one `except` covers them; the endpoint maps domain errors in one table, as `/api/extract` does, without importing Chroma.
- **A PDF with no text returns 200 with `chunks_stored = 0`.**
  *Why:* a blank page is a valid PDF with nothing to index, not a client error. The code skips Chroma there because `add([])` raises `ValueError`, which would become a 500.
- **One uvicorn worker with embedded Chroma.**
  *Why:* measured with two processes on the same path, the reader sees the new `count` (SQLite) but its `query` still uses the old vector index and returns the wrong chunk, with no error. One worker is uvicorn's default; more workers need Chroma as a separate service.
- **No chunking or vector-store package beyond Chroma.**
  *Why:* LangChain text splitters, semchunk, chonkie, fastembed, FAISS, LanceDB, Qdrant and sqlite-vec were reviewed; none saves anything against about 15 lines of chunking, and each adds dependencies (onnxruntime, grpc, pyarrow, langchain-core) or lacks metadata (FAISS).

## Use of AI tools

- Claude Code (Anthropic) was used as a pair-programmer: researching options, drafting code and tests, and reviewing. The author reviewed and ran every change, owns every line, and made every commit.
- The evaluation labels (`eval/gold_names.csv`) start from the NER output and were corrected by me against each page image: 3 missed mentions added with their page and line, and the result checked against an independent count of surnames in the OCR words.
- The box reference (`eval/gold_boxes.csv`) comes from the notebook prototype, checked against the page images, plus one box built by hand from its two OCR words; it is not generated from `app/`, so the test does not compare the code with itself.

## References

- Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for a binomial proportion. *Statistical Science*, 16(2), 101–133.
- Christen, P. (2006). *A comparison of personal name matching: Techniques and practical issues*. Technical Report TR-CS-06-02, The Australian National University.
- Cohen, W. W., Ravikumar, P., & Fienberg, S. E. (2003). A comparison of string metrics for matching names and records. *KDD Workshop on Data Cleaning and Object Consolidation*.
- Finkel, J. R., Grenager, T., & Manning, C. (2005). Incorporating non-local information into information extraction systems by Gibbs sampling. *ACL 2005*.
- Gale, W. A., Church, K. W., & Yarowsky, D. (1992). One sense per discourse. *DARPA Speech and Natural Language Workshop*.
- Hand, D., & Christen, P. (2018). A note on using the F-measure for evaluating record linkage algorithms. *Statistics and Computing*, 28(3), 539–547.
- Krishnan, V., & Manning, C. D. (2006). An effective two-stage model for exploiting non-local dependencies in named entity recognition. *COLING-ACL 2006*.
- Muennighoff, N., Tazi, N., Magne, L., & Reimers, N. (2023). MTEB: Massive Text Embedding Benchmark. *EACL 2023*.
- Qu, R., Tu, R., & Bao, F. (2024). Is semantic chunking worth the computational cost? arXiv:2410.13070.
- Ratinov, L., & Roth, D. (2009). Design challenges and misconceptions in named entity recognition. *CoNLL 2009*.
- Smith, B., & Troynikov, A. (2024). *Evaluating chunking strategies for retrieval*. Chroma technical report. https://www.trychroma.com/research/evaluating-chunking
- Zhang, J., et al. (2025). OCR hinders RAG: Evaluating the cascading impact of OCR on retrieval-augmented generation. *ICCV 2025*. arXiv:2412.02592.
