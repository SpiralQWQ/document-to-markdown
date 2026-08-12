#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
table_recheck.py — 表格复核（camelot 2.x）

对 MinerU 已转换的 full.md，用 camelot 从原 PDF 重新抽取表格，
与 md 中的表格做交叉比对（v0.1.0 补丁 T2）。

核心逻辑：
  1. camelot read_pdf（stream 优先，lattice 兜底）从原 PDF 抽表
  2. 每张表自带 parsing_report.accuracy（0-100，越低越可疑）
  3. accuracy 低于阈值 → 标记"低置信表格"待人工/Claude 复核
  4. 输出 review_hint（与视频转写 review_hint 同思路）

用法（作为模块）:
  from table_recheck import table_recheck
  issues = table_recheck(pdf_path, full_md_path, out_dir)

返回 list[str] 问题描述（空 = 表格无明显异常）。
"""
import os

# 低于此 accuracy 的表格标记为"低置信"（camelot 质量评分）
LOW_CONF_ACCURACY = 80.0
# 单页最多复核的表格数上限（防大文档全表复核拖慢）
MAX_TABLES = 50


def _count_md_tables(full_md_path):
    """统计 full.md 里的表格数量（启发式：含 | 的连续块）"""
    if not os.path.exists(full_md_path):
        return 0
    try:
        with open(full_md_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return 0
    # 统计表格分隔行（|---| 这种），每张表至少 1 个分隔行
    sep = [l for l in text.splitlines() if l.strip().startswith("|") and "--" in l]
    return max(1, len(sep)) if sep else 0


def table_recheck(pdf_path, full_md_path=None, out_dir=None, low_conf=LOW_CONF_ACCURACY):
    """复核 PDF 表格，返回问题列表。"""
    issues = []
    if not os.path.exists(pdf_path):
        return [f"PDF 不存在: {pdf_path}"]

    # 前置：如果 md 里根本没有表格，且 PDF 页数少 → 可能漏表（先跳过，不做重判断）
    md_tables = _count_md_tables(full_md_path) if full_md_path else 0

    try:
        import camelot
    except ImportError:
        return ["camelot 未安装，跳过表格复核"]

    # 只抽前几页复核（复核是抽样不是全量，避免大文档卡死）
    # 用 stream 优先（对无线条表格有效），lattice 兜底
    tables = []
    try:
        tables = camelot.read_pdf(pdf_path, pages="1", flavor="stream",
                                  suppress_stdout=True)
    except Exception:
        try:
            tables = camelot.read_pdf(pdf_path, pages="1", flavor="lattice",
                                      suppress_stdout=True)
        except Exception as e:
            return [f"camelot 读取失败: {str(e)[:120]}"]

    if not tables:
        # 没抽到表：若 md 里确实有表格 → 值得标记（可能漏检）
        if md_tables > 0:
            issues.append(f"PDF 第 1 页 camelot 未抽到表格，但 md 中有 {md_tables} 张表（可能漏检，建议抽查）")
        return issues

    low = []
    for t in tables[:MAX_TABLES]:
        try:
            acc = t.parsing_report.get("accuracy", 100.0)
            if acc < low_conf:
                low.append((acc, t.df.shape))
        except Exception:
            continue

    if low:
        desc = "; ".join(f"acc={a}% shape={s}" for a, s in low)
        issues.append(f"camelot 检出 {len(low)} 个低置信表格（{desc}），建议人工/Claude 复核")

    # 写 review_hint 到输出目录（如有）
    if out_dir and low:
        try:
            hint = os.path.join(out_dir, "table_review_hint.txt")
            with open(hint, "w", encoding="utf-8") as f:
                f.write(f"⚠️ camelot 复核：检出 {len(low)} 个低置信表格，对应知识点处建议复核\n")
        except OSError:
            pass

    return issues


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python table_recheck.py <PDF路径> [full.md路径] [输出目录]")
        sys.exit(1)
    pdf = sys.argv[1]
    md = sys.argv[2] if len(sys.argv) > 2 else None
    out = sys.argv[3] if len(sys.argv) > 3 else None
    issues = table_recheck(pdf, md, out)
    if issues:
        print("[问题]")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
    else:
        print("[OK] 表格无明显异常")
