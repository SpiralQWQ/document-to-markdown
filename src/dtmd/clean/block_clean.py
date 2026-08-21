#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""block_clean.py — 块级清洗：剔除 MinerU 转写产物的页眉/页脚/页码等结构噪音。

背景
----
MinerU 转写产物 full.md 会混入页面结构噪音：
  - 页眉：书名、章节名、渠道广告水印（如"欢迎加入QQ群783462347…500+本Python书"）
  - 页脚：版权行、购书账号水印、页码
content_list.json 里 MinerU 已把每个内容块标了类型（header / footer / page_number /
page_footnote / aside_text / text / code …）。本模块按「类型 + 跨页重复」双确认，
把这些噪音块从 full.md 剔除，不依赖外部清洗引擎，纯标准库。

调用
----
    from dtmd.clean.block_clean import clean_out_dir
    stats = clean_out_dir(out_dir)          # 自动定位 content_list + full.md，就地清洗

    from dtmd.clean.block_clean import clean_full_md
    stats = clean_full_md(cl_path, md_path) # 显式指定，就地覆盖 full.md

产物：就地覆盖 full.md（原始版请自行备份）。无 content_list 时返回 skipped，不抛异常。
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter

# MinerU 明确标注为页面结构噪音的类型（100% 非正文）
NOISE_TYPES = {"header", "footer", "page_footnote", "page_number"}
# 旁注/边栏：可能是广告，也可能是真注释；跨页重复 ≥ ASIDE_MIN_PAGES 才当噪音删
ASIDE_TYPES = {"aside_text"}
ASIDE_MIN_PAGES = 4
# 跨页重复至少出现 N 页才确认是水印/页眉页脚（防误删只出现一次的标题）
DEFAULT_MIN_PAGES = 3


def norm(text: str) -> str:
    """归一化：去空白/标点/全角空格，小写。用于跨页模糊匹配（水印文本 OCR 有细微差异）。"""
    s = text.replace("　", " ").replace("﻿", "")
    s = re.sub(r"[\s\.\.,，。！!？?、；;：:()（）\[\]【】\"'“”‘’·…\-—_=+*★☆●○■□]", "", s)
    return s.lower()


def find_content_list(out_dir: str) -> str | None:
    """在输出目录找 content_list.json（MinerU 块级中间产物，含 type/bbox 坐标）。

    优先精确 `*_content_list.json`（排除 `_v2`/嵌套副本）。
    """
    if not os.path.isdir(out_dir):
        return None
    for pat in (os.path.join(out_dir, "*_content_list.json"),
                os.path.join(out_dir, "*.content_list.json")):
        hits = [p for p in glob.glob(pat) if "_v2" not in os.path.basename(p)]
        if hits:
            return hits[0]
    return None


def find_origin_pdf(content_list_path: str) -> str | None:
    """定位与 content_list 同批的 origin.pdf（用于读页高，做位置感知）。

    优先同名 UUID（{uuid}_content_list.json → {uuid}_origin.pdf），退化找任意 *_origin.pdf。
    """
    d = os.path.dirname(content_list_path)
    stem = os.path.splitext(os.path.basename(content_list_path))[0]  # {uuid}_content_list
    cand = os.path.join(d, stem.replace("_content_list", "_origin") + ".pdf")
    if os.path.exists(cand):
        return cand
    for p in glob.glob(os.path.join(d, "*_origin.pdf")):
        return p
    return None


def _load_page_heights(origin_pdf: str | None) -> dict | None:
    """读 origin.pdf 每页高度（MinerU bbox 是页内坐标，需页高算相对位置）。失败返回 None。"""
    if not origin_pdf or not os.path.exists(origin_pdf):
        return None
    try:
        import fitz
    except ImportError:
        return None
    try:
        doc = fitz.open(origin_pdf)
        h = {i: doc[i].rect.height for i in range(len(doc))}
        doc.close()
        return h
    except Exception:
        return None


def _collect_noise_keys(blocks: list, min_pages: int = DEFAULT_MIN_PAGES,
                        page_h: dict | None = None) -> set[str]:
    """从 content_list 收集噪音块文本（归一化），跨页重复 ≥ min_pages 才确认。

    - NOISE_TYPES：MinerU 明确标为页眉/页脚/页码/脚注 → 直接收集
    - ASIDE_TYPES：旁注/边栏，跨页重复 ≥ ASIDE_MIN_PAGES 才删（保守）
    - text 类型 + 位置感知：正文块落在页面顶部 12% / 底部 12% 且跨页重复
      → 是 MinerU 未标 header 的页眉/页脚水印（不同文档识别不一致，兜底）
    """
    noise_counter: Counter = Counter()
    aside_counter: Counter = Counter()
    pos_counter: Counter = Counter()
    for b in blocks:
        t = b.get("type")
        txt = (b.get("text") or "").strip()
        key = norm(txt)
        if not key:
            continue
        if t in NOISE_TYPES:
            noise_counter[key] += 1
        elif t in ASIDE_TYPES and len(key) >= 3:
            aside_counter[key] += 1
        elif t == "text" and page_h:
            p = b.get("page_idx", 0)
            h = page_h.get(p)
            if h:
                try:
                    _x0, y0, _x1, y1 = b["bbox"]
                except (KeyError, TypeError, ValueError):
                    continue
                # 过滤越界/异常 bbox（y 超出合理范围视为数据异常，不参与位置判定）
                if y0 < 0 or y1 < 0 or y0 > h * 1.05 or y1 > h * 1.05:
                    continue
                # 页眉 = 贴顶矮块（y0<8% 且块高<10%）；页脚水印由 footer/page_number 类型直接收集
                # （实测会员账号水印 188/190 被标 footer，无需位置感知兜底底部）
                top = y0 < h * 0.08 and (y1 - y0) < h * 0.10
                if top:
                    pos_counter[key] += 1

    wm_keys = {k for k, v in noise_counter.items() if v >= min_pages}
    # 短噪音（页码/纯数字类）出现频次高但未必每页一个 → 阈值放宽
    for k, v in noise_counter.items():
        if v >= 5 and len(k) <= 6:
            wm_keys.add(k)
    for k, v in aside_counter.items():
        if v >= ASIDE_MIN_PAGES:
            wm_keys.add(k)
    # 位置感知兜底：text 但落在页眉位置（贴顶矮块）且跨页重复 → 页眉水印
    for k, v in pos_counter.items():
        if v >= min_pages:
            wm_keys.add(k)
    # 短 key 过滤：长度 <4 的噪音（页码"5"、判断题"对/错"、页眉"前言"）不用于全文删除，
    # 否则会把正文里的同文本短词连带删除（真实案例：试题库"对/错/5"误删）。
    # 宁留勿错：短噪音残留无害，误删正文不可逆。
    wm_keys = {k for k in wm_keys if len(k) >= 4}
    return wm_keys


def clean_full_md(content_list_path: str, full_md_path: str,
                  min_pages: int = DEFAULT_MIN_PAGES, dry_run: bool = False,
                  text_watermark: bool = True) -> dict:
    """清洗单个文档：读 content_list 收集噪音 key，从 full.md 剔除，就地覆盖。

    Args:
        content_list_path: MinerU 块级中间产物（含 type/bbox）。
        full_md_path: 目标 full.md 路径。
        min_pages: 跨页重复阈值（默认 3）。
        dry_run: True 只统计不写回（预演），output 置空。
        text_watermark: 块级清洗后是否追加"渠道水印"精准清除（调 text-cleaning-engine
            --watermark-only，剥 QQ群/微信/邮箱等文字特征水印）。未配置 DTM_CLEANER_PATH
            时自动跳过（fail-open）。dry_run 时不调用。

    返回 {"ok", "wm_keys", "removed", "original_lines", "clean_lines", "output", "error",
          "watermark"}。任何异常不抛：以 ok=False + error 返回（转写管线内调用失败不阻塞主流程）。
    """
    result = {"ok": False, "wm_keys": [], "removed": 0,
              "original_lines": 0, "clean_lines": 0, "output": "", "error": ""}
    try:
        with open(content_list_path, encoding="utf-8") as f:
            blocks = json.load(f)
        with open(full_md_path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except (OSError, ValueError) as e:
        result["error"] = f"读取失败: {e}"
        return result

    wm_keys = _collect_noise_keys(blocks, min_pages, _load_page_heights(find_origin_pdf(content_list_path)))
    lines = raw.splitlines()
    removed: list[str] = []
    out: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped or stripped.startswith("```"):
            out.append(ln)
            continue
        ln_key = norm(stripped)
        hit = None
        if ln_key in wm_keys:
            hit = stripped
        else:
            # 行内含水印且行较短（水印占主）→ 删；长行(含正文)保留。
            # 仅长 key(≥6) 允许"行内含"匹配——短 key 只整行精确匹配，防误删正文短词。
            for wk in wm_keys:
                if len(wk) >= 6 and len(ln_key) <= len(wk) + 8 and wk in ln_key:
                    hit = stripped
                    break
        if hit:
            removed.append(hit)
            continue
        out.append(ln)

    # 清理删行后残留的空代码块标记（两个 ``` 相邻 = 空块，成对丢弃）
    cleaned_lines: list[str] = []
    i = 0
    n = len(out)
    while i < n:
        ln = out[i]
        if ln.strip() == "```" and i + 1 < n and out[i + 1].strip() == "```":
            i += 2  # 空代码块的开头+闭合成对丢弃，不残留孤 ```
            continue
        cleaned_lines.append(ln)
        i += 1

    cleaned = "\n".join(cleaned_lines)
    if not dry_run:
        with open(full_md_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        # 渠道水印（tce 精准，可选）：块级清洗后剥 QQ群/微信/邮箱等文字特征水印
        if text_watermark:
            try:
                from dtmd.tools.clean_hook import clean_watermark_md
                _ok, _out, _msg = clean_watermark_md(full_md_path)
                result["watermark"] = {"ok": _ok, "msg": _msg}
            except Exception as e:
                result["watermark"] = {"ok": False, "msg": str(e)}

    result.update({
        "ok": True,
        "wm_keys": sorted(wm_keys),
        "removed": len(removed),
        "original_lines": len(lines),
        "clean_lines": len(cleaned_lines),
        "output": full_md_path if not dry_run else "",
        "dry_run": dry_run,
    })
    return result


def clean_out_dir(out_dir: str, min_pages: int = DEFAULT_MIN_PAGES,
                  dry_run: bool = False, text_watermark: bool = True) -> dict:
    """对已转写目录做块级清洗：自动定位 content_list + full.md，就地覆盖 full.md。

    无 content_list / 无 full.md → 返回 skipped（不抛异常，供批量扫描跳过）。
    dry_run=True 时只统计不写回（预演审查）。text_watermark 追加渠道水印精准清除。
    """
    cl = find_content_list(out_dir)
    if not cl:
        return {"ok": False, "skipped": True, "reason": "无 content_list.json", "out_dir": out_dir}
    full_md = os.path.join(out_dir, "full.md")
    if not os.path.exists(full_md):
        return {"ok": False, "skipped": True, "reason": "无 full.md", "out_dir": out_dir}
    stats = clean_full_md(cl, full_md, min_pages=min_pages, dry_run=dry_run,
                          text_watermark=text_watermark)
    stats["out_dir"] = out_dir
    return stats


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    r = clean_out_dir(sys.argv[1])
    if r.get("skipped"):
        print(f"[跳过] {r.get('reason')}: {sys.argv[1]}")
    elif r.get("ok"):
        print(f"[OK] {os.path.basename(sys.argv[1])}: 删除 {r['removed']} 行 "
              f"({r['original_lines']} → {r['clean_lines']})")
    else:
        print(f"[失败] {r.get('error')}")
        sys.exit(1)
