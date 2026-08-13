#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
l2.py — L2 专项层：表格复核（camelot） + TEDS 打分

L2 只对「表格密集」块跑（md_lint 表格标记多 或 content_list 表格/图表多），
因为 camelot 重解析 PDF 较慢，不能全量跑。

table_recheck 局限：camelot 只抽第 1 页做抽样复核（现有工具行为）。
"""
import os
import json
import io
import contextlib
import warnings

from dtmd.quality import blocks


def table_like_count(item):
    """从 L1 队列项统计 md_lint「表格样式」标记的行数（低优先候选里的表格提示）。"""
    n = 0
    for p in item.get("low_problems", []):
        if "表格样式" in p:
            # 格式: "md_lint候选: 发现 N 行表格样式文本，但未解析出任何表格节点..."
            try:
                n += int(p.split("发现")[1].split("行")[0].strip())
            except Exception:
                n += 1
    return n


def select_l2_targets(queue_items, min_table_like=10):
    """选择 L2 复核目标：表格标记行数 ≥ min_table_like 的块。返回列表。"""
    targets = []
    for it in queue_items:
        n = table_like_count(it)
        if n >= min_table_like:
            it["_table_like"] = n
            targets.append(it)
    targets.sort(key=lambda x: -x["_table_like"])
    return targets


def _find_slice_pdf(out_dir):
    """在输出目录找切片 PDF（{uuid}_origin.pdf 或 origin.pdf）。"""
    if not os.path.isdir(out_dir):
        return None
    for fn in os.listdir(out_dir):
        if fn.endswith("_origin.pdf") or fn == "origin.pdf":
            return os.path.join(out_dir, fn)
    return None


def run_l2(targets, low_conf=80.0, verbose=False):
    """对 L2 目标跑 table_recheck。返回 (summary, results)。

    results 元素: {"block": 队列项, "issues": [问题], "pdf_used": 路径}
    """
    try:
        from dtmd.quality.gates.table_recheck import table_recheck
    except ImportError:
        return {"error": "table_recheck 导入失败"}, []
    results = []
    checked = flagged = skipped = 0
    for it in targets:
        out_dir = it.get("out_dir")
        pdf = _find_slice_pdf(out_dir) or it.get("file")
        full_md = os.path.join(out_dir, "full.md") if out_dir else None
        if not pdf or not os.path.exists(pdf):
            skipped += 1
            continue
        try:
            # 抑制 camelot/pypdf 刷屏警告（Font Type / StandardEncoding 等，无害）
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with contextlib.redirect_stderr(io.StringIO()):
                    issues = table_recheck(
                        pdf,
                        full_md if full_md and os.path.exists(full_md) else None,
                        out_dir if out_dir else None,
                        low_conf=low_conf)
        except Exception as e:
            issues = [f"table_recheck 异常: {e}"]
        checked += 1
        if issues:
            flagged += 1
        results.append({"block": it, "issues": issues, "pdf_used": pdf})
        if verbose:
            print(f"  [L2] {it.get('basename', '?')} p{it.get('start')}-{it.get('end')}"
                  + (f": {'; '.join(issues)}" if issues else ": 通过"))
    return {"checked": checked, "flagged": flagged, "skipped": skipped}, results


def write_l2_results(results, out_path):
    """写出 L2 结果 JSON。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    payload = {"count": len(results), "results": results}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return len(results)
