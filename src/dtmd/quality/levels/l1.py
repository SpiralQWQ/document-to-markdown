#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
l1.py — L1 自动层：完整性 / 页数核对 / md_lint / 图片引用

所有检查结果统一为 "问题列表"（空 = 通过）。标红=待复审候选，不直接判失败
（数学 |V| 会被 md_lint 误报为表格，故标红需 L2/L3 复审）。
"""
import os
import json
import re
from datetime import datetime

from dtmd.quality import blocks


def page_count_from_content_list(out_dir):
    """从 content_list.json 读实际转换页数（max page_idx+1）。返回 int 或 None。"""
    if not os.path.isdir(out_dir):
        return None
    for fn in os.listdir(out_dir):
        if fn.endswith("_content_list.json"):
            try:
                d = json.load(open(os.path.join(out_dir, fn), encoding="utf-8"))
                if isinstance(d, list) and d:
                    pgs = [e.get("page_idx", 0) for e in d if isinstance(e, dict)]
                    if pgs:
                        return max(pgs) + 1
            except Exception:
                continue
    return None


def page_count_from_origin_pdf(out_dir):
    """切片实际页数（fitz）。云端命名是 {uuid}_origin.pdf，本地是 origin.pdf，都兼容。"""
    if not os.path.isdir(out_dir):
        return None
    try:
        import fitz
        for fn in os.listdir(out_dir):
            if fn.endswith("_origin.pdf") or fn == "origin.pdf":
                return fitz.open(os.path.join(out_dir, fn)).page_count
    except Exception:
        pass
    return None


def check_completeness(block, file_counts):
    """完整性：块是否有产出。返回 (ok, out_dir)。"""
    st, od = blocks.block_status(block, file_counts)
    return st == "done", od


def check_page_count(block, out_dir):
    """页数核对。返回 (ok, expected, slice_pages, content_pages, note)。

    双层校验:
      - 硬: origin.pdf（切片实际页数）≠ 期望 → 切片/转换异常
      - 软: content_list（有内容页数）显著少于切片页数（差>1）→ 可能缺页
    容 1 页差异（末尾空白页无内容元素，content_list 不索引）。
    """
    expected = block["end"] - block["start"] + 1
    slice_pages = page_count_from_origin_pdf(out_dir)
    content_pages = page_count_from_content_list(out_dir)
    is_pdf = block.get("kind", "PDF") == "PDF"
    notes = []
    if not is_pdf:
        # Office 整份转换，start/end=1/1 不代表页数；只查有无转换产物
        if slice_pages is None and content_pages is None:
            return False, expected, None, None, "Office 块无转换产物"
        return True, expected, slice_pages, content_pages, ""
    if slice_pages is not None and slice_pages != expected:
        notes.append(f"切片页数异常：origin.pdf={slice_pages} ≠ 期望{expected}")
    # 软检查：有内容页数 vs 基准（slice 缺失时用 expected 兜底，避免漏报）
    if content_pages is not None:
        base = slice_pages if slice_pages is not None else expected
        if content_pages < base - 1:
            notes.append(f"内容覆盖不足：content={content_pages} < 基准{base}（可能缺页）")
    if slice_pages is None and content_pages is None:
        notes.append("无法读取页数(origin.pdf/content_list 均缺失)")
    return len(notes) == 0, expected, slice_pages, content_pages, "; ".join(notes)


def check_md_lint(block, out_dir):
    """md_lint 语法体检。返回 (high, low) 两组问题。

    high: 真实问题（空文件/乱码/未闭合代码块/缺文件）→ 驱动 L3 复审
    low:  表格样式未解析（| 启发式，数学 |V| 常误报）→ 仅作低优先级候选
    """
    try:
        from dtmd.quality.gates.md_lint import md_lint as _md_lint
        full_md = os.path.join(out_dir, "full.md")
        if not os.path.exists(full_md):
            return ["full.md 缺失"], []
        _ok, issues = _md_lint(full_md)
    except ImportError:
        return [], []  # md_lint 缺失时静默降级（与 auto_convert 一致）
    except Exception as e:
        return [f"md_lint 异常: {e}"], []
    high, low = [], []
    for i in issues:
        if i.startswith("发现") and "表格样式" in i:
            low.append(f"md_lint候选: {i}")
        else:
            high.append(f"md_lint: {i}")
    return high, low


def check_image_refs(block, out_dir):
    """图片引用完整性（Task-05 接入）：full.md 的 ![](images/xxx) 指向的文件必须存在。"""
    full_md = os.path.join(out_dir, "full.md")
    if not os.path.exists(full_md):
        return []
    try:
        text = open(full_md, encoding="utf-8").read()
    except Exception as e:
        return [f"读取 full.md 失败: {e}"]
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    missing = []
    for ref in refs:
        if ref.startswith("http"):
            continue  # 外部链接跳过
        p = os.path.join(out_dir, ref)
        if not os.path.exists(p):
            missing.append(ref)
    return [f"图片引用缺失: {m}" for m in missing[:10]] if missing else []


def run_l1(blocks, file_counts, verbose=False):
    """执行 L1 检查（完整性+页数+md_lint+图片引用）。

    返回 (summary, issues)。issues 元素:
      {"block":..., "problems":[高优先级], "low_problems":[低优先级候选]}
    summary: {done, missing, flagged_high, flagged_low}
    """
    issues = []
    done = missing = flagged_high = flagged_low = 0
    for b in blocks:
        try:
            ok, od = check_completeness(b, file_counts)
        except (KeyError, ValueError) as e:
            flagged_high += 1
            issues.append({"block": b, "problems": [f"脏数据: {e}"], "low_problems": []})
            continue
        if not ok:
            missing += 1
            flagged_high += 1
            issues.append({"block": b, "out_dir": od, "problems": ["缺输出(full.md/json 均无)"], "low_problems": []})
            continue
        done += 1
        probs = []
        low_probs = []
        _pok, _exp, _slice, _content, note = check_page_count(b, od)
        if note:
            probs.append(note)
        high_md, low_md = check_md_lint(b, od)
        probs += high_md
        low_probs += low_md
        probs += check_image_refs(b, od)
        if probs:
            flagged_high += 1
        elif low_probs:
            flagged_low += 1
        if probs or low_probs:
            issues.append({"block": b, "out_dir": od, "problems": probs, "low_problems": low_probs})
    return {"done": done, "missing": missing,
            "flagged_high": flagged_high, "flagged_low": flagged_low}, issues


def write_l1_queue(issues, out_path):
    """把 L1 标红块序列化为待复审队列 JSON（供 L2/L3 消费）。返回队列块数。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    queue = []
    for it in issues:
        b = it["block"]
        queue.append({
            "file": b.get("file"),
            "basename": os.path.basename(b.get("file", "")),
            "start": b.get("start"),
            "end": b.get("end"),
            "pages": b.get("pages"),
            "kind": b.get("kind"),
            "out_dir": it.get("out_dir") or b.get("out_dir"),
            "verdict": "high" if it["problems"] else "low",
            "problems": it["problems"],
            "low_problems": it["low_problems"],
        })
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "count": len(queue),
        "blocks": queue,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return len(queue)
