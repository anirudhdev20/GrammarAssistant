# Grammar Assistant

An intelligent grammar and writing assistant with a local-first NLP pipeline and an optional LanguageTool pass. It ships as a FastAPI service, a browser editor, and a bookmarklet you can run on any page.

## Features

- Spelling correction with SymSpell, word-frequency priors, and bigram context ranking
- Grammar and usage rules for agreement, articles, confusables, repeated words, punctuation, comma splices, passive voice, and wordiness
- Optional LanguageTool checks for deeper grammar coverage
- Readability and document statistics: reading ease, grade level, vocabulary diversity, passive ratio, reading time
- Inline highlights, severity/type filters, apply/ignore actions, and adjustable minimum severity
- One-click **Fix all** for spelling, grammar, and punctuation suggestions
- Download the current text as a paginated PDF from the editor or the bookmarklet
- Upload a text-based PDF and pull its selectable text into the editor for checking
- Bookmarklet panel that checks selected text on any page and can hand off to the full editor
- Offset-safe handling of Unicode, including emoji, across chunking and LanguageTool UTF-16 offsets

## Architecture

```text
Browser editor / bookmarklet
            |
        FastAPI (app.main)
            |
    POST /api/analyze
            |
      Analyzer pipeline
      ├── spaCy document pass ──► custom rules + readability
      ├── SymSpell pass ────────► spelling + bigram context
      └── LanguageTool client ──► remote grammar issues (chunked)
            |
   merge / dedupe / filter ──► AnalyzeResponse
```

Key modules:

| Path | Purpose |
| --- | --- |
| `backend/app/nlp/segment.py` | Contiguous chunking and UTF-16/Python index conversion |
| `backend/app/nlp/languagetool.py` | Async LanguageTool client, throttling, cache, span mapping |
| `backend/app/nlp/spellcheck.py` | SymSpell vocabulary, misspelling table, bigram context scoring |
| `backend/app/nlp/rules.py` | spaCy POS/dependency rules and regex punctuation checks |
| `backend/app/nlp/readability.py` | textstat metrics and style ratios |
| `backend/app/nlp/pipeline.py` | Orchestration, issue merging, filtering, timing |
| `backend/app/pdf.py` | PDF rendering and text extraction for import/export |
| `backend/app/routers/` | `/health` and `/api/*` endpoints |
| `frontend/` | Editor, overlay highlights, stats sidebar, issue actions |
| `bookmarklet/` | Shadow-DOM panel source and build script |

## Requirements

- Python 3.11+ (tested on 3.14)
- Network access for the public LanguageTool API, or `GA_LT_ENABLED=false`
- Optional: Node.js is not required to run the app

The public LanguageTool endpoint is rate-limited (about 20 requests per minute and 20 KB per request). The backend throttles and caches requests, and chunks long documents. No local Java installation is needed unless you self-host LanguageTool.

## Quick start

From the project root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m spacy download en_core_web_sm
```

Run the server:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/>. The frontend is served by the same process. API docs are at `/docs`.

To work offline or avoid the public API:

```powershell
$env:GA_LT_ENABLED = "false"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Or place a `.env` file in `backend/`:

```dotenv
GA_LT_ENABLED=false
```

## Configuration

All settings use the `GA_` prefix and can be set as environment variables or in `backend/.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `GA_APP_NAME` | `Intelligent Grammar and Writing Assistant` | API title |
| `GA_LT_ENABLED` | `true` | Enable the LanguageTool pass |
| `GA_LT_URL` | `https://api.languagetool.org/v2/check` | LanguageTool endpoint |
| `GA_LT_LANGUAGE` | `en-US` | Default LanguageTool language |
| `GA_LT_TIMEOUT_SECONDS` | `12` | Per-request timeout |
| `GA_LT_REQUESTS_PER_MINUTE` | `18` | Client-side throttle |
| `GA_LT_CACHE_SECONDS` | `3600` | Response cache lifetime |
| `GA_LT_OFFSETS_UTF16` | `true` | Treat LanguageTool offsets as UTF-16 |
| `GA_MAX_TEXT_CHARS` | `60000` | Maximum accepted document size |
| `GA_MAX_PDF_BYTES` | `10485760` | Maximum uploaded PDF size in bytes |
| `GA_MAX_PDF_PAGES` | `100` | Pages read from an uploaded PDF |
| `GA_CHUNK_CHARS` | `15000` | LanguageTool chunk size |
| `GA_MAX_SUGGESTIONS` | `4` | Maximum suggestions retained per issue |
| `GA_CORS_ORIGINS` | `*` | Comma-separated allowed origins |

## API

### `GET /health`

Returns status, version, active spaCy model name, LanguageTool enablement, and the number of custom dictionary words.

### `POST /api/analyze`

```json
{
  "text": "I recieve teh mail.",
  "language": "en-US",
  "categories": ["spelling", "grammar"],
  "min_severity": "suggestion",
  "include_stats": true,
  "use_remote": true
}
```

Response:

```json
{
  "issues": [
    {
      "id": "spell:3:10",
      "start": 2,
      "end": 9,
      "text": "recieve",
      "type": "spelling",
      "severity": "error",
      "message": "Possible misspelling. Did you mean 'receive'?",
      "suggestions": ["receive"],
      "rule_id": "MISSPELLING",
      "source": "spellcheck"
    }
  ],
  "stats": { "words": 4, "sentences": 1, "reading_time_seconds": 1 },
  "text_length": 18,
  "timing_ms": { "document": 42.0, "language_tool": 380.0, "total": 430.0 },
  "degraded": []
}
```

`start` and `end` are Python string indices (Unicode code points). The frontend converts them to JavaScript UTF-16 offsets.

### Other endpoints

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/rewrite` | Apply a replacement to a span: `{text, start, end, replacement}` |
| `GET` | `/api/dictionary` | List custom dictionary words |
| `POST` | `/api/dictionary` | Add `{ "word": "fastapi" }` |
| `DELETE` | `/api/dictionary/{word}` | Remove a word |
| `POST` | `/api/export/pdf` | Render `{text, title?}` as a downloadable PDF |
| `POST` | `/api/import/pdf` | Extract text from an uploaded PDF (`multipart/form-data`, field `file`) |

Example:

```powershell
$body = @{ text = "I recieve teh mail."; include_stats = $true } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/analyze -Method Post -ContentType "application/json" -Body $body
```

## Frontend

- Type or paste text; analysis is debounced and previous requests are aborted.
- Toggle **Deep check** to include LanguageTool. If the server disables it, a notice explains the fallback.
- Use the type chips and minimum-severity selector to focus feedback.
- Apply a suggestion, jump to the span, or ignore an issue.
- Use **Fix all** to replace every spelling, grammar, and punctuation issue that has a suggestion in one pass.
- Use **Download PDF** to save the current editor text as a paginated PDF.
- Use **Upload PDF** to extract selectable text from a PDF and load it into the editor. Scanned PDFs require OCR first.
- `?text=...` on the page URL prefills the editor and runs a check; `?api=...` points the frontend at another backend.
- `Ctrl+Enter` (`Cmd+Enter` on macOS) runs a check immediately.

## Bookmarklet

Build the installable `javascript:` URL:

```powershell
powershell -ExecutionPolicy Bypass -File .\bookmarklet\build.ps1
```

Then:

1. Create a browser bookmark and paste the contents of `bookmarklet/bookmarklet.txt` as its URL.
2. Select text on any page (optional) and click the bookmark.
3. Use **Check** in the panel. **Fix all** applies safe corrections, **PDF** saves the text, and **Open app** hands the text to the full editor.

The panel calls `http://127.0.0.1:8000` by default. To point it elsewhere, set a global before clicking or store a base URL for the site:

```js
window.GA_API_BASE = "https://assistant.example.com";
localStorage.setItem("ga_api_base", "https://assistant.example.com");
```

The backend's default `GA_CORS_ORIGINS=*` allows cross-origin checks. Some sites enforce a Content Security Policy that can block injected panels or cross-origin requests; in that case, use **Open app** or the full editor.

## Tests

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

The suite covers segmentation and offsets, spelling, rule behavior, readability, and API contracts. LanguageTool is disabled in tests via `backend/tests/conftest.py`.

## Project layout

```text
backend/
  app/
    config.py, schemas.py, main.py, pdf.py
    nlp/            # segmentation, LanguageTool, spelling, rules, readability, pipeline
    routers/        # health, analyze, export, pdf_import, rewrite, dictionary
    resources/      # allowlist
  tests/            # pytest suite
  requirements.txt
frontend/
  index.html
  css/styles.css
  js/api.js, js/app.js
bookmarklet/
  bookmarklet.js, build.ps1, bookmarklet.txt
docs/
```

## Known limitations

- English only; `en_core_web_sm` is fast but makes occasional POS mistakes, so some style rules are heuristic.
- LanguageTool public API quotas and latency apply; self-host it and set `GA_LT_URL` for heavier use.
- The custom dictionary is stored in memory and resets on restart.
- Issue merging favors local rules when spans overlap; LanguageTool may report a different suggestion for the same span.
- No authentication or persistence layer.
- PDFs embed the bundled Vera font; emoji and non-Latin scripts may render as blank glyphs.
- PDF import relies on the PDF's text layer. Scanned or image-only PDFs need OCR, and password-protected PDFs are rejected.

## License

MIT. See `GrammarAssistant/LICENSE`.
