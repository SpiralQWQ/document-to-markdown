# document-to-markdown

<p align="center">
  <strong>PDF / Word / PPT → AI-ready Markdown</strong><br>
  Batch document conversion with forced OCR, quality gates & multi-format export
</p>

<p align="center">
  <a href="https://github.com/SpiralQWQ/document-to-markdown/stargazers">
    <img src="https://img.shields.io/github/stars/SpiralQWQ/document-to-markdown?style=flat-square" alt="GitHub stars">
  </a>
  <a href="https://github.com/SpiralQWQ/document-to-markdown/blob/master/LICENSE">
    <img src="https://img.shields.io/github/license/SpiralQWQ/document-to-markdown?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/OCR-forced-orange.svg?style=flat-square" alt="Forced OCR">
  <img src="https://img.shields.io/badge/quality-L1%2FL2%2FL3-green.svg?style=flat-square" alt="Quality gates">
  <a href="https://github.com/SpiralQWQ/document-to-markdown/actions/workflows/ci.yml">
    <img src="https://github.com/SpiralQWQ/document-to-markdown/actions/workflows/ci.yml/badge.svg" alt="CI">
  </a>
  <a href="https://github.com/SpiralQWQ/document-to-markdown/commits/master">
    <img src="https://img.shields.io/github/last-commit/SpiralQWQ/document-to-markdown?style=flat-square" alt="Last commit">
  </a>
</p>

<p align="center">
  <a href="README_zh.md">中文</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="COMMERCIAL.md">Commercial license</a>
</p>

---

## Table of Contents

- [The problem it solves](#the-problem-it-solves)
- [Features](#features)
- [Architecture](#architecture)
- [Files](#files)
- [Installation](#installation)
- [Usage](#usage)
- [Quality checks (dtmd)](#quality-checks-dtmd)
- [Configuration reference](#configuration-reference)
- [Output layout](#output-layout)
- [FAQ / Troubleshooting](#faq-troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)
- [Support](#support)

---

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
| Can't trust conversion quality at scale | ✅ **dtmd QA**: L1/L2/L3 tri-color review + rework loop |

## Features

| Area | What you get |
|---|---|
| 📄 **Multi-format input** | PDF, Word (DOCX), PowerPoint (PPTX) |
| 🔍 **Forced OCR** | Every document parsed with OCR — scanned pages & formulas never lost |
| 🧪 **Quality gates (T1/T2/T4/T5)** | md syntax lint · table recheck · PDF repair · multi-format export |
| 🧠 **QA system (dtmd)** | L1 auto · L2 table recheck · L3 vision review · rework loop · tri-color report |
| ☁️ **Cloud mode** | MinerU API batch upload → poll → download (5000 files/day) |
| 🧼 **Text cleaning hook** | Integrates text-cleaning-engine (watermark/nav/garbled strip) |
| 🧽 **Block-level cleaning** | Auto-strips page headers/footers/page numbers/watermarks from converted `full.md` (MinerU type + position-aware) |
| 🔄 **Resume-safe** | Skips already-converted blocks; re-runs continue without re-upload |
| 🖥️ **Cross-platform** | Windows / Linux / macOS (env-var path config)

## Architecture

```
Input documents (PDF / DOCX / PPTX)
  ├─ T4 pdf_repair: fix corrupted/encrypted PDFs before parsing
  ├─ MinerU (local pipeline or cloud API): parse → full.md + images/ + json
  ├─ T1 md_lint: syntax gate (table column consistency, code fences)
  ├─ T2 table_recheck: camelot cross-check low-confidence tables
  └─ T5 export_md: Pandoc → docx / html / epub / pptx
```

## Files

| File | Purpose |
|---|---|
| `src/dtmd/convert/local.py` | Main local converter: batch-converts per plan, quality-checked, resume-safe |
| `src/dtmd/convert/cloud.py` | Cloud converter: batch upload → poll → download (MinerU cloud API) |
| `src/dtmd/convert/local_batch.py` | Lightweight local batch converter |
| `src/dtmd/cli.py` | **Unified CLI entry**: convert + L1/L2/L3 QA: L1/L2/L3 quality review + rework loop + report |
| `src/dtmd/quality/` | **QA package**: `blocks` (list/status) · `l1` (completeness/pages/md_lint/images) · `l2` (table recheck) · `l3` (formula density/text/vision) · `vision` (fitz render + dual-vision) · `sample` (L3 sampling) · `rework` · `report` |
| `src/dtmd/quality/gates/md_lint.py` | T1: Markdown syntax gate (mistune) |
| `src/dtmd/quality/gates/table_recheck.py` | T2: Table quality check (camelot, accuracy scoring) |
| `src/dtmd/quality/gates/pdf_repair.py` | T4: Corrupted/encrypted PDF repair (pikepdf) |
| `src/dtmd/export.py` | T5: Multi-format export (Pandoc) |
| `src/dtmd/tools/glm_mineru_proxy.py` | GLM adapter proxy (for MinerU hybrid mode) |
| `src/dtmd/tools/watchdog.py` | Watchdog: heartbeat file to detect stalls/deaths |
| `src/dtmd/tools/check_done.py` | Check which folders are fully converted |

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

Then install this package (editable) so `python -m dtmd` works from anywhere.
Run in the repo root:

```bash
python -m pip install -e .
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

If you use `dtmd convert --mode cloud` (cloud mode), set your MinerU API token:

```bash
export MINERU_API_TOKEN="your_mineru_api_token"
```

Cloud mode uses the mineru.net API: up to **5000 files/day**; the first 1000
pages/day run at highest priority, beyond that a slower queue (still parses,
never lost).

### Step 6 — GLM API key (optional, for hybrid mode)

If you use the GLM adapter (`glm_mineru_proxy.py`) for hybrid MinerU mode:

```bash
export GLM_API_KEY="your_glm_api_key"
```

## Usage

### Generate a plan (smart slicing)

Scan a folder of documents and generate `plan.json` — PDFs over 200 pages are
**smart-sliced at chapter boundaries** (TOC first, then font-size heading detection,
then hard cut as last resort) so content never breaks mid-chapter. Word/PowerPoint
files are queued whole.

```bash
python -m dtmd plan ./my-docs/                 # scan → smart slice → write _data/plan.json
python -m dtmd plan ./my-docs/ --dry-run       # preview only, write nothing
python -m dtmd plan ./my-docs/ --budget 3000   # daily page budget (default 5000)
python -m dtmd plan ./my-docs/ --out other.json
```

> Big books (>200 pages) are sliced into `p{start}-{end}` blocks automatically; every
> block stays within MinerU's 200-page-per-file limit.

### Local batch conversion

```bash
python -m dtmd convert --mode local                 # convert per plan (checks every 10 blocks)
python -m dtmd convert --mode local --no-check      # convert without pause
python -m dtmd convert --mode local --max 5         # convert at most 5 blocks
```

### Cloud conversion (MinerU API)

```bash
python -m dtmd convert --mode cloud 1 --dry-run      # preview Day 1 upload
python -m dtmd convert --mode cloud 1                # upload & poll Day 1
python -m dtmd convert --mode cloud --html doc.html  # single HTML file (MinerU-HTML model)
python -m dtmd convert --mode cloud --html-dir pages # every .html/.htm in a folder
```

> Quotas: ~5000 files/day, 200 pages per file (sliced automatically), first 1000 pages
> daily at highest priority (overflow is queued, never dropped). HTML has a separate quota.

### Merge sliced output

Multi-block books are split into `p{start}-{end}/` subdirectories. `dtmd merge` stitches
them back into one complete `full.md` at the `_mineru/` root (slices are kept untouched):

```bash
python -m dtmd merge ./my-book_mineru          # merge one book
python -m dtmd merge ./library --recursive     # merge every _mineru/ under a root
python -m dtmd merge ./library --dry-run       # preview counts only
```

### Mirror output (isolate conversion output from source dirs)

By default output lands next to each source file (`xxx_mineru/`). If the source tree must
stay untouched (e.g. git repos, shared libraries), set `DTM_OUTPUT_ROOT` and output is
**mirrored** to `{DTM_OUTPUT_ROOT}/{relative-path}/xxx_mineru/` instead:

```bash
export DTM_OUTPUT_ROOT="/path/to/output-root"   # empty/unset = beside source (default)
python -m dtmd plan ./repos/docs/               # src_rel_dir recorded per block automatically
python -m dtmd convert --mode cloud 1
# → /path/to/output-root/docs/xxx_mineru/full.md  (source tree untouched)
```

### Block-level cleaning (built-in, automatic)

Conversion now cleans output **automatically**: page headers/footers, page numbers and
repeated watermark lines (book titles, chapter headers, ad watermarks) are stripped from
`full.md` right after conversion (both local and cloud pipelines). Detection uses MinerU's
`content_list.json` block types (`header`/`footer`/`page_number`/`page_footnote`) plus a
position-aware fallback for watermarks MinerU did not tag — with cross-page dedup and
short-key filtering to avoid deleting body text.

```bash
# Clean one converted directory (in place, overwrites full.md)
python -m dtmd clean path/to/xxx_mineru

# Clean all converted dirs under a root (single-block + multi-block p{start}-{end} subdirs)
python -m dtmd clean /path/to/kb --recursive

# Preview only (report how many lines would be removed, without writing)
python -m dtmd clean /path/to/kb --recursive --dry-run
```

Block-level cleaning is built-in. For **text-feature watermarks** (QQ-group / WeChat /
email signatures that block-level position detection can miss), `dtmd clean` additionally
calls [**text-cleaning-engine**](https://github.com/SpiralQWQ/text-cleaning-engine)'s
precise `--watermark-only` mode — set `DTM_CLEANER_PATH` to enable it (skipped otherwise).

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
python -m dtmd.tools.clean_hook path/to/full.md                # → full_clean.md
python -m dtmd.tools.clean_hook path/to/full.md --anonymize    # → + PII scrub
```

Each `full.md` produces a cleaned `full_clean.md` in the same folder.
If `DTM_CLEANER_PATH` is not set, the hook silently skips (does not block).

The hook calls `text-cleaning-engine`'s standard entry point internally:
`python -m cleaner.clean_md <file> [--anonymize]` → JSON `{ok, cleaned_text, stats}`.

### Multi-format export

```bash
python -m dtmd.export path/to/full.md --to docx   # → full.docx
python -m dtmd.export path/to/full.md --to html   # → full.html
python -m dtmd.export path/to/full.md --to pptx   # → full.pptx
```

### Quality checks (run standalone)

```bash
python -m dtmd.quality.gates.md_lint path/to/full.md          # markdown syntax gate
python -m dtmd.quality.gates.table_recheck some.pdf           # table quality check
python -m dtmd.quality.gates.pdf_repair broken.pdf out.pdf    # repair corrupted PDF
```

## Quality checks (dtmd)

The `dtmd` CLI's **QA commands** form a three-layer quality review system for converted output.
Run it after conversion to know exactly which documents are trustworthy.

```
┌─ L1 · automated (free) ─────────────────────────────┐
│  completeness · page count · md_lint · image refs   │
│  → flags become "review candidates" (not failures)  │
├─ L2 · targeted (free) ──────────────────────────────┤
│  camelot table recheck on table-dense blocks        │
├─ L3 · vision review (costs tokens) ─────────────────┤
│  text layer (LaTeX balance) + vision layer          │
│  (fitz render + Qwen-VL/GLM dual-vision, A+B)      │
└─────────────────────────────────────────────────────┘
   → tri-color report: 放心 pass / 返工 rework / 误报 review
```

### Commands

```bash
python -m dtmd convert --mode local|cloud   # convert (local/cloud pipeline)
python -m dtmd list [--scope all|complex|normal]   # list blocks & status
python -m dtmd l1 [--scope all|complex|normal]   # L1 auto check → queue
python -m dtmd l2                                # L2 camelot table recheck
python -m dtmd l3                                # L3 plan + cost estimate (no vision)
python -m dtmd l3 --run                          # L3 execute vision review (costs tokens)
python -m dtmd rework --cmds                     # rework list + reconvert commands
python -m dtmd report                            # tri-color report (JSON + MD)
```

Typical flow: `l1 → l2 → l3 --run → rework → report`.

### Outputs

| Artifact | Path (default) |
|---|---|
| L1 review queue | `_data/qa/l1_queue.json` |
| L2 results | `_data/qa/l2_results.json` |
| L3 results | `_data/qa/l3_results.json` |
| Tri-color report | `_data/qa/qa_report.json` + `qa_report.md` |
| Rework list | `_data/qa/rework.json` |

> L3 vision review is **opt-in** (`--run`) because it calls Qwen-VL / GLM vision
> APIs (pay-per-use). The default `l3` shows a plan + cost estimate first.
> `--max-formula N` caps formula-dense samples to control cost.

## Configuration reference

All scripts read configuration from environment variables (no hard-coded paths).
Set them in your shell profile or a `.env` (see `.env.example`).

### Paths

| Variable | Purpose | Default |
|---|---|---|
| `DTM_ROOT` | Root data directory (your documents) | repo parent dir |
| `DTM_TOOLS` | Tools directory (this repo) | repo dir |
| `DTM_MINERU_ENV` | MinerU virtual env path | `mineru` on PATH |
| `DTM_PANDOC` | Pandoc executable path | `pandoc` on PATH |
| `DTM_PIX2TEXT_ENV` | Pix2Text venv (optional, formula check) | empty (disabled) |
| `DTM_CLEANER_PATH` | text-cleaning-engine repo path | empty (hook skips) |
| `DTM_BRIDGE_DIR` | Dir holding the GLM proxy script (`glm_mineru_proxy.py`) | empty (proxy disabled) |
| `DTM_VISION_ANALYZER` | vision_analyzer.py path (L3 vision review) | `vision_analyzer.py` on PATH |

### API keys

| Variable | Purpose |
|---|---|
| `MINERU_API_TOKEN` | MinerU cloud API (`dtmd convert --mode cloud`) |
| `GLM_API_KEY` | GLM-4.6V vision (L3 review, `vision_analyzer`) / hybrid proxy |
| `QWEN_API_KEY` | Qwen-VL vision (L3 review, `vision_analyzer` parallel) |
| `GEMINI_API_KEY` | Gemini vision (optional L3 backend) |

> L3 vision review uses **Qwen-VL + GLM-4.6V in parallel** by default
> (`--backend parallel`); set `QWEN_API_KEY` and `GLM_API_KEY`.

## Output layout

```
{original_dir}/{docname}_mineru/
  ├── full.md           # main output (LLM-ready)
  ├── images/           # extracted images
  └── *.json            # intermediate parsing results
```

## FAQ / Troubleshooting

### Q: A scanned PDF came out empty / missing text
Make sure OCR is on. `dtmd convert --mode local` and `dtmd convert --mode cloud` force OCR
by default. For a specific block, re-run with `--ocr` (see `python -m dtmd convert --help`).

### Q: `dtmd l1` flags lots of "table-like text not parsed"
That's the **md_lint `|` heuristic** — it treats any line containing `|` as a
potential table. Math (`|V|`) and code are common false positives, so these are
**low-priority candidates**, not failures. Confirm real issues with `l2`
(camelot) or `l3` (vision).

### Q: `dtmd l3` says "~315 vision calls" — is that normal?
Yes — that's the **cost estimate** for the selected targets. `l3` without `--run`
only prints the plan. Tune cost with `--max-formula N`, `--pages N`, or `--limit N`.

### Q: `camelot` fails to read my PDF
camelot needs **Ghostscript**. Install it and ensure it's on `PATH`. Some PDFs
need `--flavor lattice` instead of `stream`; the tool tries both automatically.

### Q: `_data/plan.json` not found
The plan is **your private data** (which files/pages to convert) and is not
shipped with the repo. Create one — see the minimal example in
[Installation → Step 4](#step-4--prepare-data-dir-_dataplanjson).

### Q: Why does `list --scope all` show fewer blocks than expected?
`complex` is a **subset** of `normal` (complex documents also appear in the
normal list). `dtmd` deduplicates blocks by `(file, start, end)`, so `all`
shows only the unique blocks.

### Q: Can I clean watermarks / navigation noise from the output?
Yes — use the optional [text-cleaning-engine](#integrated-text-cleaning-optional-via-text-cleaning-engine) hook
(`python -m dtmd.tools.clean_hook path/to/full.md` → `full_clean.md`).

## Roadmap

- [ ] **PyPI publish** (packaging metadata is ready)
- [ ] **Docker image**: one-command local pipeline
- [ ] **Table verification**: TEDS scoring (stronger than camelot accuracy)
- [ ] **Batch reporting**: aggregated QA report across many books
- [ ] **Web UI**: upload → convert → review dashboard

## Contributing

Contributions are welcome! Bug reports, feature ideas, and PRs are all
appreciated. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first, and note
that all contributions must follow our [Code of Conduct](CODE_OF_CONDUCT.md).

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
