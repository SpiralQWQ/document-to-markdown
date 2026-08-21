# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.5.0] - 2026-08-21

### Added
- **Block-level cleaning** (`dtmd.clean` package): strip page headers/footers/page
  numbers/watermarks from MinerU conversion output (`full.md`). Detection combines
  MinerU's `content_list.json` block types (`header`/`footer`/`page_number`/
  `page_footnote`) with a position-aware fallback (top-edge short text blocks repeated
  across pages) and cross-page dedup confirmation. Exposed as `clean_full_md` /
  `clean_out_dir` / `find_content_list`; dry-run and fail-open (never blocks).
- **`dtmd clean` CLI command**: clean one or many directories, `--recursive` (finds all
  dirs containing `full.md`, covering both single-block and multi-block `p{start}-{end}`
  subdirs), `--dry-run` (preview without writing), `--verbose`.
- **Automatic cleaning on conversion**: `convert/local.py` and `convert/cloud.py` now
  clean output immediately after conversion (fails open — never blocks the pipeline).
- **Channel watermark removal (optional, via text-cleaning-engine)**: after block-level
  cleaning, strip text-feature watermarks (QQ-group / WeChat / email signatures) through
  text-cleaning-engine's precise `--watermark-only` entry. Only the watermark segments are
  removed — the rest of the line/document is untouched (100% retention). Skipped (fails
  open) when `DTM_CLEANER_PATH` is not set.

### Fixed
- Short noise keys (<4 chars, e.g. page numbers, single-char answers) no longer match
  against body text during deletion, preventing accidental removal of short body words
  (e.g. True/False quiz answers).
- Out-of-range / abnormal bbox coordinates (y beyond page height) filtered out of
  position-based detection.
- Bottom-edge position detection removed — footer watermarks are already covered by
  MinerU `footer` / `page_number` types; this avoids false positives on body text near
  page bottoms.

### Tests
- `tests/test_block_clean.py` (synthetic data, no real documents required).
- `tests/test_clean_cli.py` (CLI boundary: no-arg / missing dir / dry-run / recursive /
  mixed / file-path input).

## [0.4.1] - 2026-08-13

### Added
- CI workflow (`.github/workflows/ci.yml`): pytest across Python 3.10/3.11/3.12.
- Unit tests for `config` and `cli` (`tests/test_config.py`, `tests/test_cli.py`).
- Community docs: `SECURITY.md`, issue templates and PR template (`.github/`).

### Fixed
- `md_lint` degraded-branch message aligned with `l1.py` low-priority classification (table-style text correctly filed as candidate when `mistune` is unavailable).

## [0.4.0] - 2026-08-13

**Structural restructure to `src/dtmd/` (SoC directory contract).**

### Changed
- **New `src/dtmd/` layout** (src layout, `python -m dtmd` unified CLI):
  - `dtmd/convert/` — conversion domain (`base` shared / `local` pipeline / `cloud` pipeline)
  - `dtmd/quality/` — QA domain (`gates` checkers + `levels` L1/L2/L3 + `blocks`/`sample`/`rework`/`report` + `vision`)
  - `dtmd/export.py`, `dtmd/tools/` (watchdog/check_done/clean_hook/glm_proxy), `dtmd/config.py`, `dtmd/utils.py`
- **Deleted all root shims** (`auto_convert.py`/`mineru_day.py`/`qa_runner.py`/...) and old flat packages — root now has no `.py` files.
- **Unified CLI**: `python -m dtmd convert|l1|l2|l3|rework|report|list` (7 commands) replaces the per-script entry points.
- **Command migration**: `python auto_convert.py` → `python -m dtmd convert --mode local`; `python mineru_day.py --complex` → `python -m dtmd convert --mode cloud`; `python qa_runner.py l1` → `python -m dtmd l1`.
- Deduplicated `safe()` (was 4 copies) into `dtmd.utils`; unified `is_done`/`already_done` into `dtmd.convert.base`.

### Fixed
- Hard-coded absolute path in `qa/vision.py` (`C:/Users/...`) → env-var `DTM_VISION_ANALYZER` (privacy red line).
- `tests/` imports migrated to `dtmd.*` (15 tests pass).

### Added
- `--version` / `--mode local|cloud` on the unified CLI.
- Friendly data-missing error message instead of bare traceback (plan.json is private data).

## [0.3.0] - 2026-08-12

QA system (`qa_runner`) for verifying converted output quality.

### Added
- **`qa_runner.py` + `qa/` package** (10 files): `list / l1 / l2 / l3 / rework / report` commands.
- **L1 automated layer**: completeness + dual-layer page-count check (origin.pdf hard + content_list soft) + md_lint (high/low priority split) + image-reference integrity.
- **L2 table recheck**: camelot on table-dense blocks only (stderr suppressed to avoid pypdf warning spam).
- **L3 review layer**: text layer (LaTeX balance / content consistency) + vision layer (fitz render + Qwen-VL/GLM dual-vision A+B region+whole-page review) + verdict rules.
- **Rework loop**: rework list + reconvert command generation.
- **Tri-color report**: pass / rework / false-positive, JSON + Markdown output.
- **Sampling cost control**: high-priority always checked, formula-dense representatives capped (`--max-formula`), vision-call estimate.

### Fixed
- argparse subparser default clobbering parent `--scope` value.
- Dirty block data (missing file/start/end) crashing the whole scan.
- `origin.pdf` UUID-prefix naming incompatibility (cloud `{uuid}_origin.pdf`).
- content_list trailing-blank-page off-by-one false positive.
- `doc.close()` accessed in f-string after close.
- rework command missing `--complex`.
- `report` silently producing a misleading all-pass report when the L1 queue was missing.
- plan.json `pending_complex ⊂ pending_normal` overlap causing duplicate processing (deduped in `load_blocks`).

### Verified
- `load_blocks(all)` dedupes overlapping complex/normal entries.
- L1 full scan: all blocks done, no missing output.
- L2 table recheck: table-dense blocks flagged for review.
- Full L3 vision review: pass/suspicious verdicts, no fail after `$` heuristic fix.
- Final tri-color report generated (pass / rework / review).

## [0.2.0] - 2026-08-11

Modular restructure + text-cleaning-engine integration.

### Changed

- **Modular package layout**: scripts reorganized from flat root files into
  `converter/` (core conversion), `quality/` (T1/T2/T4 patches), `export/` (T5),
  `tools/` (helpers), `cli/` (entry points).
- **Single source of truth for paths** (`paths.py`): all scripts now resolve
  data/docs/logs/tool paths from one module, environment-overridable
  (`DTM_ROOT`, `DTM_MINERU_ENV`, `DTM_PANDOC`, …). No more per-script path drift.
- **Root thin entry points**: `python auto_convert.py` and `python mineru_day.py`
  still work — they forward to the packages.

### Added

- **`requirements.txt`** — full pip dependency list.
- **`.env.example`** — environment template (paths + API keys, never committed).
- **`tests/`** — unit tests for `md_lint`, `table_recheck`, `pdf_repair`, `export`.
- **`--clean` integration hook** (`tools/clean_hook.py`): after conversion, hands
  `full.md` to [text-cleaning-engine](https://github.com/SpiralQWQ/text-cleaning-engine)
  to strip watermarks/navigation/garbled fragments → `full_clean.md`.
  Enabled via `python auto_convert.py --clean`; requires `DTM_CLEANER_PATH`.
  Silently skips when not configured. Fixed UTF-8 stdin/stdout for correct CJK.

### Fixed (found by exhaustive testing)

- **Pandoc detection regression**: after restructure, `PANDOC` defaulted to
  `pandoc` on PATH, but the portable Pandoc wasn't on PATH → all exports failed.
  `paths._detect_pandoc()` now checks env var → portable path → PATH.
- **clean_hook env read**: `CLEANER_PATH` was captured at import time, so changing
  `DTM_CLEANER_PATH` mid-run had no effect. Now read live via `_cleaner_path()`.

### Tested

- **84 exhaustive test cases** across 8 tasks (paths, md_lint, table_recheck,
  pdf_repair, export_md, clean_hook, CLI entry, imports/privacy), each passing
  4 review rounds. Full report: `docs/acceptance-report-v0.2.0.md`.

## [0.1.0] - 2026-08-11

Initial open-source release: a batch document-to-Markdown converter powered by
MinerU, with quality-gate patches and multi-format export.

### Added

- **Core converter** (`auto_convert.py`): batch-converts PDF/DOCX/PPTX per plan,
  forced OCR on all documents, quality-checked, resume-safe (skips completed blocks).
- **Cloud converter** (`mineru_day.py`): batch upload → poll → download using the
  MinerU cloud API (`model_version=vlm`, forced OCR for complex docs).
- **T1 · Markdown syntax gate** (`md_lint.py`): uses mistune 3.x AST to check
  table column consistency, code-fence closure, and garbled characters.
  Integrated into `verify_output()`.
- **T2 · Table quality check** (`table_recheck.py`): uses camelot 2.x
  (stream/lattice + accuracy scoring) to flag low-confidence tables.
  Integrated into `verify_output()` (only for PDFs ≤200 pages).
- **T4 · PDF repair** (`pdf_repair.py`): uses pikepdf 10.x to strip empty-password
  encryption and recover lightly corrupted PDFs; true encryption is flagged
  for manual handling. Integrated into `convert_block()` before slicing.
- **T5 · Multi-format export** (`export_md.py`): Pandoc-based export of `full.md`
  to docx / html / epub / pptx. Runs from the md directory so `images/` paths resolve.
- **Helper tools**: `check_done.py` (folder completion check), `watchdog.py`
  (heartbeat + stall detection), `glm_mineru_proxy.py` (GLM adapter for hybrid mode),
  `formula_recheck.py` (optional formula check hook), `wait_cloud.sh`.
- **Structure**: `_data/` (plan/progress), `_docs/` (plans/docs), `_logs/` (logs),
  `_archive/` (historical), `_slices/` (temp slices). All scripts read paths from
  environment variables (`DTM_ROOT`, `DTM_MINERU_ENV`, `DTM_PANDOC`, …) so the
  repo runs from any location.

### Removed (during development)

- **T3 · Formula recheck with MixTeX**: MixTeX is not on PyPI (the documented
  `pip install mixtex` does not exist); Pix2Text was evaluated but does not do
  formula-level rechecking (whole-page recognition with typos). Not shipped to
  avoid adding a feature with no real value.

### Fixed

- **mistune auto-closes unclosed code fences**: mistune 3.x silently closes
  unterminated code blocks, so fence-closure detection now counts fence lines
  (odd count = unclosed).
- **pikepdf 10.x `strict` param removed**: recovery now uses `attempt_recovery=True`.
- **export_md custom output path**: output now uses an absolute path so `--out`
  works across directories.

### Deps

- Python 3.10+: `mistune 3.3.4`, `camelot-py 2.0.0`, `pikepdf 10.11.0`
- Optional: `Pandoc` (3.x) for export, `Pix2Text` venv for formula check,
  `GLM_API_KEY` for hybrid mode, `MINERU_API_TOKEN` for cloud mode.
