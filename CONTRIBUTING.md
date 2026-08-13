# Contributing to document-to-markdown

Thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to `document-to-markdown`.
These are guidelines, not rules — use your best judgment, and feel free to propose
changes to this document in a pull request.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [What should I know before getting started?](#what-should-i-know-before-getting-started)
- [How can I contribute?](#how-can-i-contribute)
  - [Reporting bugs](#reporting-bugs)
  - [Suggesting enhancements](#suggesting-enhancements)
  - [Your first code contribution](#your-first-code-contribution)
  - [Pull requests](#pull-requests)
- [Styleguides](#styleguides)
  - [Git commit messages](#git-commit-messages)
  - [Python styleguide](#python-styleguide)
  - [Documentation styleguide](#documentation-styleguide)

## Code of Conduct

This project and everyone participating in it is governed by our
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to
uphold this code. Please report unacceptable behavior to the maintainers.

## What should I know before getting started?

`document-to-markdown` converts PDF/Word/PPT to AI-ready Markdown via MinerU,
with quality gates (T1/T2/T4/T5) and a three-layer QA system (`qa_runner`).
Before diving in, skim the [README](README.md) to understand the architecture:

- **conversion**: `auto_convert.py` (local) / `mineru_day.py` (cloud)
- **quality gates**: `quality/md_lint.py`, `quality/table_recheck.py`, `quality/pdf_repair.py`
- **QA system**: `qa/` package (`l1/l2/l3/rework/report`)
- **paths**: all paths come from `paths.py` (env-var driven, no hard-coded absolute paths)

## How can I contribute?

### Reporting bugs

Open an issue with the template provided. Before filing:

- Search existing issues to avoid duplicates.
- Include a **minimal reproduction**: input file (or a snippet), command used,
  and the full error output.
- State your environment: OS, Python version, MinerU version.

### Suggesting enhancements

Open an issue labeled `enhancement`. Describe the problem you're solving and a
concrete sketch of the change. Feature ideas are also tracked in the README
[Roadmap](README.md#roadmap).

### Your first code contribution

Good first issues are labeled `good first issue`. If you're unsure where to
start, ask in the issue — maintainers are happy to guide.

### Pull requests

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests under `tests/`
   (run them with `python -m pytest tests/`).
3. Ensure your code passes `python -m py_compile` on changed files.
4. Update the relevant docs (README / CHANGELOG) if behavior changed.
5. Update `CHANGELOG.md` and `CHANGELOG_zh.md` under a new `[Unreleased]` section.
6. Open the PR. Reference any related issue.

> **Privacy**: this project is open source. Never commit machine-specific absolute
> paths, API keys, or private data. Use env vars (see `paths.py` / `.env.example`).

## Styleguides

### Git commit messages

- Use the conventional commits prefix: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, `test:`, `chore:`.
- Subject line ≤ 72 chars, imperative mood ("add", not "added").
- Body explains the *why*, not just the *what*.

### Python styleguide

- Python 3.10+, follow [PEP 8](https://peps.python.org/pep-0008/).
- Chinese docstrings/comments are welcome (the codebase uses them).
- Keep functions small and single-purpose; no magic numbers — use named constants.
- Prefer `paths.py` for all path resolution (no hard-coded absolute paths).

### Documentation styleguide

- Use [Keep a Changelog](https://keepachangelog.com/) format for `CHANGELOG.md`.
- README: keep EN and ZH in sync when you change either.
- Use tables over prose for structured info (files, env vars, commands).
