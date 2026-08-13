#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_md.py — Markdown 多格式导出（Pandoc）

把 MinerU 输出的 full.md 导出为 docx / pdf / html / pptx 等多种格式（v0.1.0 补丁 T5）。

核心逻辑：
  1. 用 Pandoc 转换
  2. 转换前 cd 到 full.md 所在目录，保证 images/ 相对路径正确
  3. 支持格式：docx（Word）/ html / epub / pptx（课件）/ pdf（需 LaTeX 引擎）

用法（CLI）:
  python export_md.py <full.md路径> [--to docx] [--out 输出路径]

示例:
  python export_md.py full.md --to docx            → full.docx
  python export_md.py full.md --to html            → full.html
  python export_md.py full.md --to pptx            → full.pptx
"""
import os
import shutil
import subprocess
import sys

# Pandoc 路径：优先环境变量 DTM_PANDOC，否则用系统 PATH 中的 pandoc
from dtmd import config as _paths
PANDOC = _paths.PANDOC

# 支持的目标格式 → 扩展名
SUPPORTED = {
    "docx": "docx",
    "html": "html",
    "epub": "epub",
    "pptx": "pptx",
    "pdf": "pdf",
}


def export_md(md_path, to="docx", out_path=None):
    """导出 full.md 为指定格式。返回 (ok, 输出路径, 错误信息)。"""
    if not os.path.exists(md_path):
        return False, None, f"文件不存在: {md_path}"
    if to not in SUPPORTED:
        return False, None, f"不支持的格式: {to}（支持: {', '.join(SUPPORTED)}）"
    # Pandoc 存在性：裸命令名（PATH 查找）用 shutil.which；含路径用 os.path.exists
    if not (shutil.which(PANDOC) if os.sep not in PANDOC and not os.path.isabs(PANDOC)
            else os.path.exists(PANDOC)):
        return False, None, f"Pandoc 不存在: {PANDOC}"

    md_dir = os.path.dirname(os.path.abspath(md_path))
    base = os.path.splitext(os.path.basename(md_path))[0]
    out_path = out_path or os.path.join(md_dir, f"{base}.{SUPPORTED[to]}")
    out_path = os.path.abspath(out_path)

    # cd 到 md 目录，保证 images/ 相对路径正确；输出用绝对路径（可跨目录）
    cmd = [PANDOC, os.path.basename(md_path), "-o", out_path]
    if to == "pptx":
        cmd.append("--to=pptx")
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=md_dir, timeout=300, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, None, "导出超时(5分钟)"
    except Exception as e:
        return False, None, str(e)

    # 图片缺失 warning 不算失败（图片路径可能被移动）；真错误才失败
    if proc.returncode != 0:
        return False, None, proc.stderr[-300:] if proc.stderr else "未知错误"

    if not os.path.exists(out_path):
        return False, None, f"输出未生成: {out_path}"
    return True, out_path, ""


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    md = args[0]
    to = "docx"
    out = None
    if "--to" in args:
        to = args[args.index("--to") + 1]
    if "--out" in args:
        out = args[args.index("--out") + 1]
    ok, path, err = export_md(md, to, out)
    if ok:
        print(f"[OK] 已导出: {path}")
    else:
        print(f"[失败] {err}")
        sys.exit(1)
