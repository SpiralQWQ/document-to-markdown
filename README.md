# document-to-markdown

Convert **PDF / Word (DOCX) / PowerPoint (PPTX)** documents into **AI-ready Markdown**
for LLM consumption (RAG, agent pipelines, note generation). Built on **MinerU**
as the parsing engine, with quality-gate patches and multi-format export.

> Project developed by [SpiralQWQ](https://github.com/SpiralQWQ).

> 🔗 **Integrates with** [**text-cleaning-engine**](https://github.com/SpiralQWQ/text-cleaning-engine)
> — optionally clean the converted Markdown (strip watermarks / navigation / garbled
> fragments) before feeding it to your LLM. See [Integrated text cleaning](#integrated-text-cleaning-optional-via-text-cleaning-engine).

## The problem it solves

| Pain point | document-to-markdown |
|---|---|
| PDF/Word/PPT → Markdown manually is slow | ✅ Automatic batch conversion |
| Scanned PDFs come out empty without OCR | ✅ Forced OCR on all documents |
| Tables/formulas often parse wrong | ✅ Quality gates catch them (T1/T2) |
| Corrupted/encrypted PDFs fail silently | ✅ Auto-repair before parsing (T4) |
| Only get Markdown, need Word/PDF/PPT | ✅ Pandoc multi-format export (T5) |

## Architecture

```
Input documents (PDF / DOCX / PPTX)
  ├─ T4 repair_pdf: fix corrupted/encrypted PDFs before parsing
  ├─ MinerU (local pipeline or cloud API): parse → full.md + images/ + json
  ├─ T1 md_lint: syntax gate (table column consistency, code fences)
  ├─ T2 table_recheck: camelot cross-check low-confidence tables
  └─ T5 export_md: Pandoc → docx / html / epub / pptx
```

## Files

| File | Purpose |
|---|---|
| `auto_convert.py` | Main local converter: batch-converts per plan, quality-checked, resume-safe |
| `mineru_day.py` | Cloud converter: batch upload → poll → download (MinerU cloud API) |
| `mineru_local_batch.py` | Lightweight local batch converter |
| `md_lint.py` | T1: Markdown syntax gate (mistune) |
| `table_recheck.py` | T2: Table quality check (camelot, accuracy scoring) |
| `pdf_repair.py` | T4: Corrupted/encrypted PDF repair (pikepdf) |
| `export_md.py` | T5: Multi-format export (Pandoc) |
| `formula_recheck.py` | Formula check hook (optional, needs Pix2Text) |
| `glm_mineru_proxy.py` | GLM adapter proxy (for MinerU hybrid mode) |
| `watchdog.py` | Watchdog: heartbeat file to detect stalls/deaths |
| `check_done.py` | Check which folders are fully converted |

## Installation

Follow these steps in order.

### Download checklist

| # | Get | Why | Where |
|---|---|---|---|
| 1 | This repo | the code | `git clone` below |
| 2 | Python 3.10+ | run the scripts | python.org |
| 3 | **MinerU** (+ models) | parsing engine | `pip install "mineru[all]"` |
| 4 | PyMuPDF | slice large PDFs | `pip install pymupdf` |
| 5 | mistune, camelot-py, pikepdf | quality gates | `pip install mistune "camelot-py[base]" pikepdf` |
| 6 | Pandoc (optional) | multi-format export | pandoc.org or `winget install JohnMacFarlane.Pandoc` |

### Step 1 — Clone this repo

```bash
git clone https://github.com/SpiralQWQ/document-to-markdown.git
cd document-to-markdown
```

### Step 2 — Install Python dependencies

```bash
pip install "mineru[all]" pymupdf mistune "camelot-py[base]" pikepdf
```

> **Forced OCR** is the default philosophy: every document (PDF/Word/PPT) is
> parsed with OCR enabled so scanned pages and formulas are not lost.
> This is slower but accurate — exactly what "slow, stable, accurate" means.

### Step 3 — Configure paths (environment variables)

All scripts read paths from environment variables, so you can run from any
location. Defaults point to the repo's own layout.

| Variable | Purpose | Default |
|---|---|---|
| `DTM_ROOT` | Root data directory (your documents) | repo parent dir |
| `DTM_TOOLS` | Tools directory (this repo) | repo dir |
| `DTM_MINERU_ENV` | MinerU virtual env path | `mineru` on PATH |
| `DTM_PANDOC` | Pandoc executable path | `pandoc` on PATH |
| `DTM_PIX2TEXT_ENV` | Pix2Text venv (optional, formula check) | empty (disabled) |
| `DTM_PROXY_PORT` | GLM proxy port | `8031` |

Example (Linux/macOS):

```bash
export DTM_MINERU_ENV="/path/to/your/mineru-env"
export DTM_ROOT="/path/to/your/documents"
```

Example (Windows PowerShell):

```powershell
$env:DTM_MINERU_ENV = "E:\path\to\mineru-env"
$env:DTM_ROOT = "E:\path\to\documents"
```

### Step 4 — Prepare data dir (`_data/plan.json`)

Conversion needs a **plan** `_data/plan.json` (describing which files to convert,
page ranges, etc.). The open-source release **does not include it** (it's your
private data); create it yourself.

Minimal plan example (`_data/plan.json`):

```json
{
  "days_normal": [
    {
      "blocks": [
        {
          "kind": "PDF",
          "file": "/path/to/your/file.pdf",
          "pages": 100,
          "size_mb": 5,
          "start": 1,
          "end": 100
        }
      ]
    }
  ]
}
```

Scripts auto-create `_data/` / `_docs/` / `_logs/` / `_slices/` on first run.

### Step 5 — Cloud API token (optional, for cloud mode)

If you use `mineru_day.py` (cloud mode), set your MinerU API token:

```bash
export MINERU_API_TOKEN="your_mineru_api_token"
```

Cloud mode uses the mineru.net API: up to **5000 files/day**; the first 1000
pages/day run at highest priority, beyond that a slower queue (still parses,
never lost).

### Step 5 — GLM API key (optional, for hybrid mode)

If you use the GLM adapter (`glm_mineru_proxy.py`) for hybrid MinerU mode:

```bash
export GLM_API_KEY="your_glm_api_key"
```

## Usage

### Local batch conversion

```bash
python auto_convert.py                 # convert per plan (checks every 10 blocks)
python auto_convert.py --no-check      # convert without pause
python auto_convert.py --max 5         # convert at most 5 blocks
```

### Cloud conversion (MinerU API)

```bash
python mineru_day.py --complex --dry-run   # preview what would be uploaded
python mineru_day.py --complex             # upload & poll complex documents
```

### Integrated text cleaning (optional, via text-cleaning-engine)

After conversion, you can hand the output Markdown to
[**text-cleaning-engine**](https://github.com/SpiralQWQ/text-cleaning-engine)
— a rule-driven engine that strips watermarks, navigation noise, ads, and
garbled fragments from converted text.

```bash
# 1. Clone the cleaning engine and point to it
git clone https://github.com/SpiralQWQ/text-cleaning-engine.git /path/to/text-cleaning-engine
export DTM_CLEANER_PATH="/path/to/text-cleaning-engine"

# 2. Clean a converted document via the hook (calls text-cleaning-engine's clean_md interface)
python tools/clean_hook.py path/to/full.md                # → full_clean.md
python tools/clean_hook.py path/to/full.md --anonymize    # → + PII scrub
```

Each `full.md` produces a cleaned `full_clean.md` in the same folder.
If `DTM_CLEANER_PATH` is not set, the hook silently skips (does not block).

The hook calls `text-cleaning-engine`'s standard entry point internally:
`python -m cleaner.clean_md <file> [--anonymize]` → JSON `{ok, cleaned_text, stats}`.

### Multi-format export

```bash
python export_md.py path/to/full.md --to docx   # → full.docx
python export_md.py path/to/full.md --to html   # → full.html
python export_md.py path/to/full.md --to pptx   # → full.pptx
```

### Quality checks (run standalone)

```bash
python md_lint.py path/to/full.md          # markdown syntax gate
python table_recheck.py some.pdf           # table quality check
python pdf_repair.py broken.pdf out.pdf    # repair corrupted PDF
```

## Output layout

```
{original_dir}/{docname}_mineru/
  ├── full.md           # main output (LLM-ready)
  ├── images/           # extracted images
  └── *.json            # intermediate parsing results
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) (EN) and [CHANGELOG_zh.md](CHANGELOG_zh.md) (中文).

## License

Dual-licensed under [AGPL-3.0](LICENSE) (open source) and a commercial license
([COMMERCIAL.md](COMMERCIAL.md)).

## Support

If this project helps you, feel free to buy me a coffee ☕. Donation is entirely
optional — the project stays free and open source forever.

<p align="center">
  <img src="assets/donate_wechat.jpg" alt="WeChat Pay" width="200">
  <img src="assets/donate_alipay.jpg" alt="Alipay" width="200">
</p>
