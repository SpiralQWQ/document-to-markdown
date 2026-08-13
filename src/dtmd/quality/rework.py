#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rework.py — 返工闭环（生成返工清单 + 复查）

流程（用户确认）:
  1. L1 高优先 / L3 fail 块 → 返工清单
  2. 对返工块重新转换（复用 mineru_day 的 --only/--force）
  3. 复查：重转后重新跑 L1/L3 验证
"""
import os
import json


def build_rework_list(l1_queue, l3_results=None):
    """生成返工清单。

    - L1 verdict==high 的块
    - L3 verdict==fail 的块（若提供 l3_results）
    返回 (list, 数量)。每项含 file/start/end/basename/原因。
    """
    rework = []
    seen = set()
    for it in l1_queue:
        if it.get("verdict") == "high":
            k = (it.get("file"), it.get("start"), it.get("end"))
            if k in seen:
                continue
            seen.add(k)
            rework.append({
                "file": it.get("file"),
                "basename": it.get("basename"),
                "start": it.get("start"),
                "end": it.get("end"),
                "out_dir": it.get("out_dir"),
                "reason": "; ".join(it.get("problems", [])) or "L1 高优先",
            })
    if l3_results:
        for r in l3_results:
            if r.get("verdict") != "fail":
                continue
            b = r.get("block") or {}
            k = (b.get("file"), b.get("start"), b.get("end"))
            if k in seen:
                continue
            seen.add(k)
            rework.append({
                "file": b.get("file"),
                "basename": b.get("basename"),
                "start": b.get("start"),
                "end": b.get("end"),
                "out_dir": b.get("out_dir"),
                "reason": "; ".join(r.get("reasons", [])) or "L3 fail",
            })
    return rework, len(rework)


def gen_rework_commands(rework):
    """生成重转命令（云端管线 --only 逐文件）。

    注意: --only 仅在云端管线生效；返工块都在 pending_complex 清单。
    命令统一走 `python -m dtmd convert --mode cloud`（根壳 mineru_day.py 已随 v0.4.0 删除）。
    """
    cmds = []
    seen_files = set()
    for r in rework:
        fn = os.path.splitext(os.path.basename(r.get("file") or ""))[0]
        if fn in seen_files:
            continue
        seen_files.add(fn)
        cmds.append(f'python -m dtmd convert --mode cloud --complex --force --only "{fn}" --budget 999999')
    return cmds


def write_rework(rework, out_path):
    """写出返工清单 JSON。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    payload = {"count": len(rework), "items": rework}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return len(rework)
