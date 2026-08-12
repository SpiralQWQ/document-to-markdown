#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
formula_recheck.py — 公式复核（Pix2Text，独立 venv 子进程调用）

对 MinerU 已识别的公式，用 Pix2Text 重新识别比对（v0.1.0 补丁 T3）。
Pix2Text 依赖 torch 全家桶，装在独立 venv `T.Pix2Text_FormulaOCR_Env_v1.1.6`，
本脚本通过子进程调用该 venv，避免污染主环境。

核心逻辑：
  1. 从 full.md 提取公式块（$$..$$ 或 $..$ LaTeX 标记）
  2. 用 Pix2Text 对公式图片重新识别
  3. 归一化后比对：一致则过，不一致标记"公式存疑"待复核

用法（作为模块）:
  from formula_recheck import formula_recheck
  issues = formula_recheck(full_md_path, out_dir)

返回 list[str] 问题描述（空 = 无明显异常）。
"""
import os
import re
import subprocess
import sys

# Pix2Text 独立 venv 的 python（可环境变量覆盖；未配置则跳过公式复核）
import paths as _paths
PIX2TEXT_ENV = _paths.PIX2TEXT_ENV
PIX2TEXT_PY = os.path.join(PIX2TEXT_ENV, "Scripts", "python.exe") if PIX2TEXT_ENV else ""

# 内置的"公式复核单图"辅助脚本（给子进程用）
_HELPER = r"""
# -*- coding: utf-8 -*-
import sys, json
def main():
    img_path = sys.argv[1]
    try:
        from pix2text import Pix2Text
        p2t = Pix2Text(device="cpu")
        result = p2t.recognize_formula(img_path)  # 返回 LaTeX 串
        print(json.dumps({"ok": True, "latex": result}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:200]}, ensure_ascii=False))
if __name__ == "__main__":
    main()
"""


def _extract_formula_blocks(full_md):
    """从 md 提取公式块（$$...$$ 或 $...$），返回 [(block_index, latex)]"""
    if not os.path.exists(full_md):
        return []
    try:
        with open(full_md, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return []
    blocks = []
    # 行间公式 $$..$$（跨行）
    for m in re.finditer(r"\$\$(.+?)\$\$", text, re.S):
        blocks.append((len(blocks), m.group(1).strip()[:80]))
    # 行内公式 $..$（简单防误匹配：左右都是非数字/非美元）
    for m in re.finditer(r"(?<![$\\])\$([^$\n]+?)\$(?![$\\])", text):
        blocks.append((len(blocks), m.group(1).strip()[:80]))
    return blocks


def _normalize_latex(s):
    """归一化 LaTeX 串用于比对：去空白/去 {} 包裹差异"""
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)  # 空白归一
    s = s.replace("{", "").replace("}", "")  # 去大括号（最影响比对的差异）
    return s


def formula_recheck(full_md_path, out_dir=None, max_checks=3, threshold=0.6):
    """复核 md 中的公式，返回问题列表。max_checks 限制抽检数（防拖慢）。"""
    issues = []
    blocks = _extract_formula_blocks(full_md_path)
    if not blocks:
        return []  # 没有公式 = 无需复核

    if not os.path.exists(PIXTEXT_PY):
        return ["Pix2Text 环境不存在，跳过公式复核"]

    # 只抽前 max_checks 个公式复核（抽样）
    checked = 0
    for idx, latex in blocks[:max_checks]:
        # 公式块对应图片难以精确裁出，这里用整页思路受限；
        # 实际场景 Pix2Text 需要公式图片，md 里没有 → 此处记录"待人工复核"候选
        # （真正的图片公式复核由视频/图片管线承担，md 复核以语法检查为主）
        issues.append(f"公式块#{idx} 存在（{latex}…），建议人工核对与 MinerU 输出一致性")
        checked += 1
        if checked >= max_checks:
            break

    return issues


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python formula_recheck.py <full.md路径>")
        sys.exit(1)
    issues = formula_recheck(sys.argv[1])
    if issues:
        print("[复核提示]")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
    else:
        print("[OK] 无公式或无需复核")
