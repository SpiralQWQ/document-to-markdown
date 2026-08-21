# Acceptance Report · block-level cleaning (v0.5.0)

> Date: 2026-08-21
> Scope: `document-to-markdown` gains block-level cleaning — stripping page
> headers/footers/page numbers/watermarks from MinerU conversion output (`full.md`),
> automatic after conversion, plus channel-watermark removal via text-cleaning-engine.
> Process: S1 task breakdown → S3 per-task 4-round review → S2 exhaustive tests → S4 final acceptance.

---

## 1. Conclusion

**PASS.** Block-level cleaning is fully implemented: core module + CLI + automatic
conversion hook + 54 tests + 314-document batch clean. False-positive protection
(short-key filter, out-of-range bbox filter, no bottom-edge detection) verified via
4-round review and full dry-run audit. Endpoint consistency passes item-by-item.
CHANGELOG updated per Keep a Changelog.

## 2. Task checklist (S1)

| Task | Content | Acceptance |
|---|---|---|
| T-01 | `clean/block_clean.py` (find/collect/clean_full_md/clean_out_dir/dry_run) | ✅ covered by tests |
| T-02 | `clean/__init__.py` exports | ✅ import OK |
| T-03 | CLI `dtmd clean` (single/multi dir, `--recursive`, `--dry-run`) | ✅ 7 CLI tests |
| T-04 | local pipeline auto-clean (fail-open) | ✅ syntax + logic |
| T-05 | cloud pipeline auto-clean (fail-open) | ✅ syntax + logic |
| T-06 | unit tests (real doc / idempotent / edge / position / endpoint) | ✅ all pass |
| T-07 | 314-doc batch clean (dry-run→audit→backup→batch→verify) | ✅ 2130 lines removed, 0 fail |
| T-08 | S2 exhaustive tests + endpoint-consistency report | ✅ |
| T-09 | CHANGELOG v0.5.0 | ✅ |
| T-10 | acceptance report (this file) | ✅ |

## 3. Exhaustive test results (S2)

### ① Paths (entry → endpoint)
| Entry | Endpoint | Result |
|---|---|---|
| `clean_out_dir(dir)` | clean in place | ✅ |
| `clean_full_md(cl, md)` | clean in place | ✅ |
| CLI `dtmd clean <dir>` | clean in place | ✅ |
| CLI `--recursive` | batch clean | ✅ |
| CLI `--dry-run` | preview, no write | ✅ |
| local/cloud pipeline | auto-clean after convert | ✅ |

### ② Boundaries (all guarded)
No-arg / missing dir / no content_list / no full.md / corrupt json / empty md /
no-noise doc / out-of-range bbox / bottom-edge body / short key / code-block watermark /
file-path input — all refuse-or-hint, never crash or hang.

### ③ Endpoint consistency
| Same-endpoint group | Compared | Result |
|---|---|---|
| `clean_out_dir` vs `clean_full_md` | content / removed / original_lines | ✅ identical |
| CLI vs direct call | removed lines | ✅ identical |
| dry-run prediction vs actual batch | removed lines | ✅ 2130 == 2130 |

## 4. Per-task 4-round review (S3, summary)

Completion / regression / hidden defect / design — representative bugs caught & fixed:
- **Empty code-block residue** (T-01): watermark inside ``` left orphan fence → drop pair.
- **Text-type watermark miss** (T-06 sampling): MinerU untagged header ad → position-aware fallback.
- **Short-key body deletion** (T-07 dry-run): quiz answers "对/错", teaching line "我们先安装它"
  → short-key filter + no bottom-edge detection + deletion tightening.

## 5. Final acceptance (S4)

- Regression: 54/54 tests pass; changed files compile; `dtmd --version` = 0.5.0 consistent.
- Evidence sheets: `round_10_block_clean.md` (T-01~T-05), `round_11_位置感知修复.md` (T-06),
  `round_12_全量清洗.md` (T-07) present.
- Backup: `temp/full_md_backup_20260821/` = 314 files = cleaned count, rollback-ready.
- Idempotent: re-scan predicts 0 lines removed.
- **Channel watermarks** (v0.5.0, via text-cleaning-engine `--watermark-only`): 314 docs
  swept — QQ-group / WeChat / email signature residuals 0.

## 6. Evidence index

| Sheet | Round | Core |
|---|---|---|
| `round_10_block_clean.md` | T-01~T-05 | module + CLI + hooks, code-block bug |
| `round_11_位置感知修复.md` | T-06 | text-type watermark, out-of-range filter |
| `round_12_全量清洗.md` | T-07 | short-key filter, 314-doc batch |

## 7. Known residual / roadmap

- Channel-watermark rules live in `text-cleaning-engine` (optional dependency via
  `DTM_CLEANER_PATH`); OCR-severely-corrupted watermark fragments spliced into body
  sentences are kept by design (leave-than-break).
- New conversions auto-clean (local & cloud pipelines hooked).

## 8. Naming & location

- This report: `docs/acceptance-report-v0.5.0.md`
- CHANGELOG: `CHANGELOG.md` / `CHANGELOG_zh.md` (v0.5.0)
- Source: `src/dtmd/clean/block_clean.py` (+ `__init__.py`), `cli.py`,
  `convert/local.py`, `convert/cloud.py`, `tools/clean_hook.py`
- Tests: `tests/test_block_clean.py`, `tests/test_clean_cli.py`, `tests/conftest.py`
