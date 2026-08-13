#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report.py — QA 报告生成（三色分类 + 对应 quality_spec 检查项）

三色:
  ✅ 放心 pass   — L1 干净（不在待复审队列）
  🔧 返工 fail   — L1 高优先 或 L3 fail（需重转）
  ⚠️ 误报/候选 review — L1 低优先候选 或 L3 suspicious（需人工/AI 复审）
"""
import os
import json
from datetime import datetime

from dtmd.quality import blocks

# quality_spec 检查项 → 问题关键词映射
QUALITY_SPEC = {
    "OCR 错别字": ["乱码", "错别字"],
    "表格结构": ["表格", "camelot", "低置信", "列数"],
    "公式 LaTeX": ["公式", "LaTeX", "$ ", "$$"],
    "标题层级": ["md_lint"],
    "图片引用": ["图片引用", "缺失"],
    "每页内容": ["页数", "切片", "内容覆盖", "缺输出", "空白"],
}


def classify_problem(problem):
    """把一条问题归类到 quality_spec 检查项。"""
    for item, kws in QUALITY_SPEC.items():
        if any(k in problem for k in kws):
            return item
    return "其他"


def _key(b):
    return (b.get("file"), b.get("start"), b.get("end"))


def build_report(all_blocks, l1_queue, l2_results=None, l3_results=None):
    """汇总三层结果 → 三色分类。

    返回 {"pass": [...], "fail": [...], "review": [...]}，每项含块信息+问题+spec_items。
    """
    flagged = {_key(it): it for it in l1_queue}
    l2_by_key = {}
    if l2_results:
        for r in l2_results:
            l2_by_key[_key(r.get("block"))] = r.get("issues", [])
    l3_by_key = {}
    if l3_results:
        for r in l3_results:
            l3_by_key[_key(r.get("block"))] = r

    pass_list, fail_list, review_list = [], [], []
    for b in all_blocks:
        k = _key(b)
        it = flagged.get(k)
        rec = {
            "file": b.get("file"),
            "basename": os.path.basename(b.get("file", "")),
            "start": b.get("start"), "end": b.get("end"),
            "kind": b.get("kind"),
            "l1_verdict": it.get("verdict") if it else "pass",
            "problems": (it.get("problems") or []) if it else [],
            "low_problems": (it.get("low_problems") or []) if it else [],
            "l2_issues": l2_by_key.get(k, []),
            "l3_verdict": l3_by_key.get(k, {}).get("verdict"),
            "l3_reasons": l3_by_key.get(k, {}).get("reasons", []),
            "spec_items": sorted({classify_problem(p)
                                  for p in ((it.get("problems") or []) if it else [])
                                  + (l2_by_key.get(k, []))}),
        }
        # 三色分类（L3 判定优先级最高——它是最深层的复审）
        if rec["l3_verdict"] == "fail":
            fail_list.append(rec)
        elif rec["l3_verdict"] == "pass":
            pass_list.append(rec)  # L3 视觉确认通过 → 放心（即使 L1 md_lint 有启发式标红）
        elif rec["l3_verdict"] == "suspicious":
            review_list.append(rec)
        elif rec["l1_verdict"] == "high":
            fail_list.append(rec)  # 无 L3 但 L1 高优先
        elif rec["l1_verdict"] == "low":
            review_list.append(rec)
        else:
            pass_list.append(rec)
    return {"pass": pass_list, "fail": fail_list, "review": review_list}


def write_report(report, json_path, md_path):
    """写 qa_report.json + qa_report.md。返回 None。"""
    os.makedirs(os.path.dirname(os.path.abspath(json_path)) or ".", exist_ok=True)
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "pass": len(report["pass"]), "fail": len(report["fail"]),
        "review": len(report["review"]),
        "fail_items": report["fail"],
        "review_items": report["review"],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 人类可读 md
    lines = [
        "# M.AIStudy 转写质检报告",
        "",
        f"> 生成: {payload['generated']}",
        "",
        f"## 总览（三色）",
        "",
        f"| 分类 | 数量 | 含义 |",
        f"|---|---|---|",
        f"| ✅ 放心 | {len(report['pass'])} | L1 干净 |",
        f"| 🔧 返工 | {len(report['fail'])} | L1高优先/L3 fail，需重转 |",
        f"| ⚠️ 误报/候选 | {len(report['review'])} | L1低优先/L3存疑，需复审 |",
        "",
    ]
    if report["fail"]:
        lines += ["## 🔧 返工清单（需重转）", ""]
        for r in report["fail"]:
            lines.append(f"- **{r['basename']}** p{r['start']}-{r['end']} [{r['kind']}]")
            for p in r["problems"]:
                lines.append(f"  - {p}")
            if r["l2_issues"]:
                lines.append(f"  - L2: {'; '.join(r['l2_issues'])}")
            if r["l3_verdict"]:
                l3flat = []
                for grp in (r["l3_reasons"] or []):
                    l3flat += grp if isinstance(grp, list) else [str(grp)]
                lines.append(f"  - L3: {r['l3_verdict']} - {'; '.join(l3flat[:5])}")
            if r["spec_items"]:
                lines.append(f"  - 对应检查项: {', '.join(r['spec_items'])}")
        lines.append("")
    if report["review"]:
        lines += ["## ⚠️ 误报/候选清单（需复审，多为表格启发式）", ""]
        lines.append(f"共 {len(report['review'])} 块，多为 md_lint 表格启发式误报，"
                     "由 L2/L3 判定。详见 qa_report.json。")
        lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
