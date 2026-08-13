#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
l3.py — L3 复审层：公式密集标记 / 文本层检查 / 视觉层 / 判定

L3 不做公式工具(Pix2Text 环境缺失已否决)，公式质量由视觉层(Qwen-VL+GLM)看。
本模块先做：公式密集标记(Task-09) + 文本层检查(Task-10)。
视觉层/判定 由后续 Task 接入。
"""
import os
import json
import re

from dtmd import config as _paths


def equation_count(out_dir):
    """从 content_list.json 统计公式(equation)元素数量。返回 int。"""
    if not os.path.isdir(out_dir):
        return 0
    for fn in os.listdir(out_dir):
        if fn.endswith("_content_list.json"):
            try:
                d = json.load(open(os.path.join(out_dir, fn), encoding="utf-8"))
                if isinstance(d, list):
                    return sum(1 for e in d
                               if isinstance(e, dict) and e.get("type") == "equation")
            except Exception:
                continue
    return 0


def latex_markers_count(out_dir):
    """统计 full.md 里 LaTeX 公式标记数（$$ 对计 2，行内 $ 计 1，$$ 内的 $ 不重复计）。"""
    full_md = os.path.join(out_dir, "full.md")
    if not os.path.exists(full_md):
        return 0
    try:
        text = open(full_md, encoding="utf-8").read()
    except Exception:
        return 0
    dd_pairs = text.count("$$") // 2
    single = len(re.findall(r"(?<!\\)\$(?!\$)", text))
    return dd_pairs * 2 + single


def mark_formula_dense(queue_items, equation_threshold=20):
    """标记公式密集块（equation 元素数 ≥ 阈值），供 L3 抽样。

    返回已标记列表（带 _formula_dense 字段，按密集度降序）。
    """
    marked = []
    for it in queue_items:
        out_dir = it.get("out_dir")
        if not out_dir:
            continue
        n = equation_count(out_dir)
        it["_formula_dense"] = n
        if n >= equation_threshold:
            marked.append(it)
    marked.sort(key=lambda x: -x["_formula_dense"])
    return marked


def check_latex_balance(out_dir):
    """文本层：LaTeX 公式配平检查。返回 (hard, soft) 两组问题。

    hard: $$ 失衡（块公式破坏，真实问题）→ 可判 fail
    soft: 单 $ 奇数（代码/公式混合书难分，需视觉确认）→ 判 suspicious
    """
    full_md = os.path.join(out_dir, "full.md")
    if not os.path.exists(full_md):
        return ["full.md 缺失"], []
    try:
        text = open(full_md, encoding="utf-8").read()
    except Exception as e:
        return [f"读取失败: {e}"], []
    hard, soft = [], []
    dd = text.count("$$")
    if dd % 2 != 0:
        hard.append(f"$$ 数量为奇数({dd})，疑似未闭合公式")
    # 单 $ 仅在确有公式时才提示（避免纯代码书误报），且归为 soft
    eq_count = equation_count(out_dir)
    single_dollar = len(re.findall(r"(?<!\\)\$", text.replace("$$", "")))
    if single_dollar % 2 != 0 and (eq_count > 0 or dd > 0):
        soft.append(f"$ 数量为奇数({single_dollar})，疑似未闭合行内公式（需视觉确认）")
    return hard, soft


def check_content_consistency(out_dir):
    """文本层：content_list 元素数 vs full.md 实际结构的一致性。

    只做粗粒度核对：公式/表格/图片 在 content_list 有记录，full.md 也有对应标记。
    返回 (hard, soft)。hard=内容疑似丢失（真实问题）。
    """
    full_md = os.path.join(out_dir, "full.md")
    if not os.path.exists(full_md):
        return [], []
    try:
        text = open(full_md, encoding="utf-8").read()
    except Exception:
        return [], []
    hard, soft = [], []
    # 公式：content_list equation 数 vs md $$ 块数（粗略）
    eq = equation_count(out_dir)
    md_eq = len(re.findall(r"\$\$", text)) // 2
    if eq > 0 and md_eq == 0:
        hard.append(f"content_list 有 {eq} 个公式，但 full.md 无 $$ 公式块（可能丢失）")
    # 图片：content_list image/chart 数 vs md 图片引用数（粗略）
    img_count = 0
    for fn in os.listdir(out_dir):
        if fn.endswith("_content_list.json"):
            try:
                d = json.load(open(os.path.join(out_dir, fn), encoding="utf-8"))
                if isinstance(d, list):
                    img_count = sum(1 for e in d
                                    if isinstance(e, dict) and e.get("type") in ("image", "chart"))
            except Exception:
                pass
    md_img = len(re.findall(r"!\[", text))
    if img_count > 0 and md_img == 0:
        hard.append(f"content_list 有 {img_count} 个图，但 full.md 无图片引用（可能丢失）")
    return hard, soft


def run_text_layer(out_dir):
    """L3 文本层：对单个输出目录跑全部文本检查。

    返回 (hard, soft) 两组问题。hard=真实问题(fail)，soft=存疑(suspicious)。
    """
    hard, soft = [], []
    h1, s1 = check_latex_balance(out_dir)
    hard += h1; soft += s1
    h2, s2 = check_content_consistency(out_dir)
    hard += h2; soft += s2
    return hard, soft


# ── Task-13/14: A+B 组合审（B 区域先审 → A 整页兜底） ──────────────────

def get_page_elements(out_dir, page_idx):
    """从 content_list 取某页的 equation/image/table/chart 元素（带 bbox）。"""
    elements = []
    if not os.path.isdir(out_dir):
        return elements
    for fn in os.listdir(out_dir):
        if fn.endswith("_content_list.json"):
            try:
                d = json.load(open(os.path.join(out_dir, fn), encoding="utf-8"))
                if isinstance(d, list):
                    for e in d:
                        if (isinstance(e, dict) and e.get("page_idx") == page_idx
                                and e.get("type") in ("equation", "image", "table", "chart")
                                and e.get("bbox")):
                            elements.append(e)
            except Exception:
                continue
    return elements


def build_region_prompt(elem):
    """按元素类型生成区域审提示词（对应 quality_spec 检查项）。"""
    t = elem.get("type")
    if t == "equation":
        return ("这是PDF中一个公式区域。请识别该公式的数学表达式，判断："
                "1)公式是否完整无截断 2)是否有乱码 3)能否辨认清楚。")
    if t == "table":
        return ("这是PDF中一个表格区域。请判断：1)表格结构是否完整对齐 "
                "2)行列是否清晰 3)是否有明显错位或乱码。")
    if t in ("image", "chart"):
        return ("这是PDF中一张图片/图表。请描述内容，判断："
                "1)图片是否清晰完整 2)是否有明显失真或截断。")
    return "请描述该区域内容并判断是否清晰可读。"


def build_page_prompt():
    """整页审提示词。"""
    return ("这是PDF完整一页。请判断：1)整体布局是否正常(无大面积空白/错乱) "
            "2)是否有明显的内容丢失或乱码 3)标题/正文/图表是否结构正常。")


def review_page(out_dir, page_idx, backend="parallel", max_region=5):
    """对单页做 A+B 组合审。

    B(区域): 对该页 equation/image/table/chart 元素逐个 bbox 裁切审
    A(整页): 渲染整页做布局兜底审
    返回 dict（region_results + page_verdict），由 Task-14 判定。
    """
    from dtmd.quality import vision
    pdf = vision.find_slice_pdf(out_dir)
    if not pdf:
        return {"page_idx": page_idx, "error": "无切片 PDF"}
    elements = get_page_elements(out_dir, page_idx)
    region_results = []
    for e in elements[:max_region]:
        ok, img, err = vision.render_page(pdf, page_idx, bbox=e["bbox"], zoom=3.0)
        if not ok:
            region_results.append({"type": e["type"], "ok": False, "err": err})
            continue
        ok2, res, err2 = vision.analyze_image(img, build_region_prompt(e), backend=backend)
        region_results.append({"type": e["type"], "bbox": e["bbox"],
                               "ok": ok2, "result": res, "err": err2})
    # A 整页审
    page_verdict = None
    ok, img, err = vision.render_page(pdf, page_idx, zoom=1.5)
    if ok:
        ok2, res, err2 = vision.analyze_image(img, build_page_prompt(), backend=backend)
        page_verdict = {"ok": ok2, "result": res, "err": err2}
    return {"page_idx": page_idx, "elements_n": len(elements),
            "region_results": region_results, "page_verdict": page_verdict}


# ── Task-14: 判定规则 ─────────────────────────────────────────────

NEG_KEYWORDS = ["异常", "乱码", "截断", "错位", "丢失", "不是表格",
                "失真", "模糊", "缺失", "损坏", "空白", "不完整", "无法辨认"]
POS_KEYWORDS = ["正常", "清晰", "完整", "可读", "结构正常", "无", "没有", "清晰可读"]


def _senti(text):
    """粗略情感：文本里负面/正面关键词计数。"""
    neg = sum(1 for k in NEG_KEYWORDS if k in text)
    pos = sum(1 for k in POS_KEYWORDS if k in text)
    return neg, pos


def judge_page(page_review, text_hard, text_soft=None):
    """判定单页。返回 (verdict, reasons)。

    verdict: pass(通过) | suspicious(存疑,需人工) | fail(硬伤,返工)
    规则:
      - 文本层 hard（$$ 失衡/内容丢失/页审错误）→ fail
      - 文本层 soft（$ 奇数等需视觉确认）+ 区域/整页视觉异常 → suspicious
      - 全部正常 → pass
    """
    reasons = []
    if page_review.get("error"):
        return "fail", [page_review["error"]]
    if text_hard:
        return "fail", text_hard
    if text_soft:
        reasons += text_soft
    for rr in page_review.get("region_results", []):
        if not rr.get("ok"):
            reasons.append(f"区域视觉调用失败({rr['type']})")
            continue
        for _model, txt in (rr.get("result") or {}).items():
            if isinstance(txt, str):
                neg, pos = _senti(txt)
                if neg > pos:
                    reasons.append(f"区域[{rr['type']}]异常: {txt[:50]}")
    pv = page_review.get("page_verdict")
    if pv:
        if pv.get("ok"):
            for _model, txt in (pv.get("result") or {}).items():
                if isinstance(txt, str):
                    neg, pos = _senti(txt)
                    if neg > pos:
                        reasons.append(f"整页异常: {txt[:50]}")
        else:
            reasons.append(f"整页视觉调用失败: {pv.get('err')}")
    if reasons:
        return "suspicious", reasons
    return "pass", []


# ── Task-01/02(执行): 跑 L3 复审计划 ─────────────────────────────

def run_l3_plan(plan, backend="parallel", verbose=False, limit=None,
                retries=3, resume=True, progress_every=1):
    """执行 L3 复审计划（逐块逐页 A+B 双视觉）。

    健壮性:
      - retries: 视觉调用失败重试次数（默认 3 轮）
      - resume: 断点续跑，跳过已有 l3_results 中已审的目标
    块级 verdict: 任一页 fail→fail；任一页 suspicious→suspicious；否则 pass。
    返回 (results, summary)。
    """
    from collections import Counter

    done_keys = set()
    if resume:
        # 读取已有结果（断点续跑），跳过已审目标
        try:
            rp = os.path.join(_paths.QA_DATA_DIR, "l3_results.json")
            if os.path.exists(rp):
                prev = json.load(open(rp, encoding="utf-8")).get("results", [])
                for r in prev:
                    b = r.get("block") or {}
                    done_keys.add((b.get("basename"), b.get("start"), b.get("end")))
        except Exception:
            pass

    results = []
    if limit:
        plan = plan[:limit]
    total = len(plan)
    for i, item in enumerate(plan, 1):
        k = (item.get("basename"), item.get("start"), item.get("end"))
        if resume and k in done_keys:
            if verbose:
                print(f"  [跳过·已审] {item.get('basename', '?')[:35]} "
                      f"p{item.get('start')}-{item.get('end')}")
            continue
        out_dir = item.get("out_dir")
        pages = item.get("pages", [])
        if not out_dir or not pages:
            continue
        block_details = []
        for pg in pages:
            verdict, reasons = "fail", ["页审失败"]
            for attempt in range(1, retries + 1):
                try:
                    page_rev = review_page(out_dir, pg, backend=backend)
                    text_hard, text_soft = run_text_layer(out_dir)
                    verdict, reasons = judge_page(page_rev, text_hard, text_soft)
                    break  # 成功
                except Exception as e:
                    if attempt < retries:
                        if verbose:
                            print(f"    [重试{attempt}] 页{pg} 视觉失败: {str(e)[:40]}")
                        continue
                    verdict, reasons = "fail", [f"视觉重试{retries}轮仍失败: {e}"]
            block_details.append({"page": pg, "verdict": verdict, "reasons": reasons})
        if any(r["verdict"] == "fail" for r in block_details):
            bv = "fail"
        elif any(r["verdict"] == "suspicious" for r in block_details):
            bv = "suspicious"
        else:
            bv = "pass"
        results.append({
            "block": {kk: item.get(kk) for kk in
                      ("basename", "file", "start", "end", "out_dir", "priority")},
            "verdict": bv,
            "pages_reviewed": len(block_details),
            "page_details": block_details,
            "reasons": [r for r in (r["reasons"] for r in block_details) if r],
        })
        if verbose:
            print(f"  [{i}/{total}][{bv}] {item.get('basename', '?')[:35]} "
                  f"p{item.get('start')}-{item.get('end')} ({len(pages)}页)")
    summary = {"by_block": dict(Counter(r["verdict"] for r in results)),
               "blocks": len(results), "skipped_resume": len(done_keys)}
    return results, summary


def write_l3_results(results, out_path, merge=True):
    """写出 L3 结果 JSON（默认合并已有结果去重，支持断点续跑）。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    existing = []
    if merge and os.path.exists(out_path):
        try:
            existing = json.load(open(out_path, encoding="utf-8")).get("results", [])
        except Exception:
            pass
    seen = set()
    merged = []
    for r in existing + results:
        b = r.get("block") or {}
        k = (b.get("basename"), b.get("start"), b.get("end"))
        if k in seen:
            continue
        seen.add(k)
        merged.append(r)
    payload = {"count": len(merged), "results": merged}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return len(merged)
