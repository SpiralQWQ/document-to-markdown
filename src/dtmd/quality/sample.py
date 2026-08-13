#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample.py — L3 抽样策略（选目标 + 选页 + 成本预估）

原则（用户确认）:
  - 高优先 L1 标红块：必查
  - 公式密集块（content_list equation ≥ 阈值）：查
  - L2 表格标红块：查
  - 再按代表类型抽几本，控制总视觉调用量（不穷举）
"""
import os
import json

from dtmd.quality.levels import l3


def select_l3_targets(l1_queue, equation_threshold=20, max_high=None, max_formula=10):
    """选择 L3 复审目标块。

    策略（用户确认的"抽代表"）:
      - 高优先 L1 标红块：全部必查（max_high 可截断）
      - 公式密集块：按密集度取前 max_formula 个代表（不全查，控成本）
    返回 (targets, 分级统计 dict)。
    """
    from collections import Counter
    high = [it for it in l1_queue if it["verdict"] == "high"]
    if max_high:
        high = high[:max_high]
    formula = l3.mark_formula_dense(l1_queue, equation_threshold=equation_threshold)
    if max_formula:
        formula = formula[:max_formula]
    seen = set()
    targets = []
    for it in high:
        k = (it.get("file"), it.get("start"), it.get("end"))
        if k in seen:
            continue
        seen.add(k)
        it["_l3_priority"] = "high"
        targets.append(it)
    for it in formula:
        k = (it.get("file"), it.get("start"), it.get("end"))
        if k in seen:
            continue
        seen.add(k)
        it["_l3_priority"] = "formula"
        targets.append(it)
    stats = dict(Counter(t.get("_l3_priority") for t in targets))
    return targets, stats


def pick_pages(out_dir, n=3):
    """从 content_list 选 n 个代表页（有内容的页，均匀分散）。返回页码列表。"""
    pages = set()
    if not os.path.isdir(out_dir):
        return []
    for fn in os.listdir(out_dir):
        if fn.endswith("_content_list.json"):
            try:
                d = json.load(open(os.path.join(out_dir, fn), encoding="utf-8"))
                if isinstance(d, list):
                    for e in d:
                        if isinstance(e, dict) and e.get("page_idx") is not None:
                            pages.add(e["page_idx"])
            except Exception:
                continue
            break
    plist = sorted(pages)
    if not plist:
        return []
    if n <= 1:
        return plist[:1]  # 抽 1 页不返回首尾两页
    if len(plist) <= n:
        return plist
    # 均匀取 n 个：首、中、尾
    idx = sorted(set([0, len(plist) - 1] +
                     [round((len(plist) - 1) * i / (n - 1)) for i in range(1, n - 1)]))
    return [plist[i] for i in idx]


def build_l3_plan(l1_queue, pages_per_block=3, equation_threshold=20,
                  max_high=None, max_formula=10):
    """生成 L3 执行计划（含成本预估）。返回 (plan, summary)。"""
    targets, stats = select_l3_targets(l1_queue, equation_threshold, max_high, max_formula)
    plan = []
    total_pages = 0
    for it in targets:
        od = it.get("out_dir")
        if not od or not os.path.isdir(od):
            continue
        pages = pick_pages(od, n=pages_per_block)
        total_pages += len(pages)
        plan.append({
            "file": it.get("file"),
            "basename": it.get("basename"),
            "start": it.get("start"),
            "end": it.get("end"),
            "priority": it.get("_l3_priority"),
            "out_dir": od,
            "pages": pages,
        })
    # 预估视觉调用：每页 (区域元素数 + 1 整页) 次，粗估每页 ≤6 元素
    est_calls = total_pages * 7  # 保守：每页最多 6 区域 + 1 整页
    summary = {"targets": len(plan), "pages": total_pages,
               "est_vision_calls": est_calls, "priority": stats}
    return plan, summary
