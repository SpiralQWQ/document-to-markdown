#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document-to-Markdown 转换完成度检测（文件夹级）
扫描每个含 pdf/ppt/doc 的文件夹，判断其内全部文档是否都已转出 {原名}_mineru/

用法:
  python check_done.py [根目录]      # 列出所有文件夹完成状态（默认 DTM_ROOT）
  python check_done.py --ready       # 只列出「全部完成可删除」的文件夹
"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 根目录：优先命令行参数 → 环境变量 DTM_ROOT → 当前目录
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
ROOT = _args[0] if _args else os.environ.get("DTM_ROOT", os.getcwd())
EXTS = (".pdf", ".ppt", ".pptx", ".doc", ".docx")


def is_converted(folder, doc):
    """该文档是否已转出（存在 {原名}_mineru/ 含 full.md 或 json）"""
    stem = os.path.splitext(doc)[0]
    out = os.path.join(folder, stem + "_mineru")
    return os.path.isdir(out) and (
        os.path.exists(os.path.join(out, "full.md"))
        or any(fn.lower().endswith(".json") for fn in os.listdir(out)))


def main():
    only_ready = "--ready" in sys.argv
    total_done_folders = 0
    for base in sorted(os.listdir(ROOT)):
        bdir = os.path.join(ROOT, base)
        if not os.path.isdir(bdir) or base.startswith("_"):
            continue
        for root, _dirs, fns in os.walk(bdir):
            docs = [f for f in fns if f.lower().endswith(EXTS)]
            if not docs:
                continue
            missing = [f for f in docs if not is_converted(root, f)]
            if not missing:
                total_done_folders += 1
                print(f"✅ [可删] {root}（{len(docs)} 个文档全部转完）")
            elif not only_ready:
                print(f"⏳ [未完] {root}（{len(docs) - len(missing)}/{len(docs)}，缺 {len(missing)} 个）")
                for m in missing[:5]:
                    print(f"       缺: {m}")
    print(f"\n统计: 全部完成可删文件夹 {total_done_folders} 个"
          + ("（其余未完成）" if not only_ready else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
