#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blocks.py — 块清单读取 + 输出目录计算 + 状态扫描（QA 数据底座）

数据源: plan.json 的 pending_complex / pending_normal
输出目录: 与 converter/mineru_day.py 运行时逻辑一致（单块→根目录，多块→p{start}-{end} 子目录），
          并兼容 plan.json 预存的 out_dir 字段（历史路径漂移兜底）。
"""
import os
import re
import json

from dtmd import config as _paths

PLAN = _paths.PLAN


from dtmd.utils import safe


def load_blocks(scope="all"):
    """按 scope 读取块清单（去重）。

    scope: all=复杂+普通 | complex=仅复杂 | normal=仅普通
    注意: pending_complex 是 pending_normal 的子集（同一块可能同时出现在两份清单），
          scope=all 时按 (file,start,end) 去重，避免同一块被处理两次。
    """
    plan = json.load(open(PLAN, encoding="utf-8"))
    blocks = []
    if scope in ("all", "complex"):
        blocks += plan.get("pending_complex", [])
    if scope in ("all", "normal"):
        blocks += plan.get("pending_normal", [])
    if scope == "all":
        seen = set()
        uniq = []
        for b in blocks:
            k = (b.get("file"), b.get("start"), b.get("end"))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(b)
        blocks = uniq
    if not blocks:
        raise ValueError(
            f"scope={scope} 无可用块（plan.json 缺 pending_complex/pending_normal）")
    return blocks


def build_file_counts(blocks):
    """统计同一源文件被切成几块（用于单块/多块判断）。
    脏数据（缺 file 字段）跳过，不参与统计，避免整批崩溃。
    """
    counts = {}
    for b in blocks:
        f = b.get("file")
        if not f:
            continue
        counts[f] = counts.get(f, 0) + 1
    return counts


def compute_out_dir(block, file_counts):
    """计算块的输出目录（与 mineru_day.py 运行时一致）"""
    orig_dir = os.path.dirname(block["file"])
    base = safe(os.path.splitext(os.path.basename(block["file"]))[0])
    out_root = os.path.join(orig_dir, base + "_mineru")
    multi = file_counts.get(block["file"], 1) > 1
    return os.path.join(out_root, f"p{block['start']}-{block['end']}") if multi else out_root


def _is_done_dir(d):
    """目录里有没有 full.md 或任意 json → 视为已完成"""
    if not os.path.isdir(d):
        return False
    return os.path.exists(os.path.join(d, "full.md")) or any(
        f.lower().endswith(".json") for f in os.listdir(d))


def block_status(block, file_counts):
    """返回 (状态, 实际输出目录)。

    状态: done | missing
    候选目录: 运行时计算值 + plan.json 预存 out_dir（历史路径漂移兜底）
    脏数据（缺必需字段）→ 抛 ValueError，由调用方逐块兜住，避免整批崩溃。
    """
    for key in ("file", "start", "end"):
        if key not in block:
            raise ValueError(f"块数据缺字段 '{key}': {block}")
    candidates = [compute_out_dir(block, file_counts)]
    if block.get("out_dir"):
        candidates.append(block["out_dir"])
    for d in candidates:
        if _is_done_dir(d):
            return "done", d
    return "missing", None
