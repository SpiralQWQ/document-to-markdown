#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runner.py — QA 主控（L1/L2/L3 三层 + 返工闭环）

用法:
  python -m dtmd list [--scope all|complex|normal] [--verbose]
  python -m dtmd convert --mode cloud --html <路径>    # HTML 云端转写
  python -m dtmd convert --mode cloud --html-dir <目录> # 目录下所有 HTML
  python -m dtmd clean [--recursive] [--dry-run]       # 块级清洗
  （L1/L2/L3/返工/报告 子命令由后续 Task 增量接入）

参数设计: cmd 为位置参数，--scope/--verbose 在同一解析器上 → 参数位置随意，
          避免 argparse 子解析器默认值覆盖主解析器值的经典坑。
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dtmd.quality import blocks
from dtmd.quality.levels import l1
from dtmd.quality.levels import l2
from dtmd.quality.levels import l3
from dtmd.quality import sample
from dtmd.quality import rework as rework_mod
from dtmd.quality import report
from dtmd import config as _paths


def cmd_list(args):
    """列出块清单与完成状态（Task-01/02 最小验证点）"""
    blks = blocks.load_blocks(args.scope)
    counts = blocks.build_file_counts(blks)
    done = missing = invalid = 0
    for b in blks:
        try:
            st, _ = blocks.block_status(b, counts)
        except (KeyError, ValueError, TypeError) as e:
            invalid += 1
            if args.verbose:
                print(f"  [invalid] {b.get('file', '?')} → {e}")
            continue
        if st == "done":
            done += 1
        else:
            missing += 1
    print(f"[块清单] scope={args.scope}: {len(blks)} 块 | 完成 {done} | 缺失 {missing}"
          + (f" | 脏数据 {invalid}" if invalid else ""))
    if args.verbose:
        for b in blks:
            try:
                st, od = blocks.block_status(b, counts)
            except (KeyError, ValueError, TypeError):
                continue  # 已在上面统计过 invalid
            print(f"  [{st}] {os.path.basename(b['file'])} p{b['start']}-{b['end']}"
                  + (f" → {od}" if st == "done" else ""))


def cmd_l1(args):
    """L1 自动检查：完整性 / 页数核对 / md_lint / 图片引用"""
    blks = blocks.load_blocks(args.scope)
    counts = blocks.build_file_counts(blks)
    summary, issues = l1.run_l1(blks, counts, verbose=args.verbose)
    print(f"[L1] scope={args.scope}: 完成 {summary['done']} | 缺输出 {summary['missing']}"
          f" | 高优先标红 {summary['flagged_high']} | 低优先候选 {summary['flagged_low']}")
    if args.verbose:
        shown = issues[: args.limit] if args.limit else issues
        for it in shown:
            tag = "高优先" if it["problems"] else "低优先候选"
            allp = it["problems"] + it["low_problems"]
            print(f"  [{tag}] {os.path.basename(it['block']['file'])} "
                  f"p{it['block']['start']}-{it['block']['end']}: {'; '.join(allp)}")
    out_path = args.out or os.path.join(_paths.QA_DATA_DIR, "l1_queue.json")
    n = l1.write_l1_queue(issues, out_path)
    print(f"[L1] 待复审队列已写出: {out_path}（{n} 块）")
    return 0


def cmd_l2(args):
    """L2 表格复核（camelot）：对表格密集块跑 table_recheck"""
    import json as _json
    queue_path = args.queue or os.path.join(_paths.QA_DATA_DIR, "l1_queue.json")
    if not os.path.exists(queue_path):
        print(f"[L2] 找不到 L1 队列: {queue_path}（先跑 `l1`）")
        return 1
    items = _json.load(open(queue_path, encoding="utf-8"))["blocks"]
    targets = l2.select_l2_targets(items, min_table_like=args.table_min)
    print(f"[L2] 目标: {len(targets)} 块（表格标记 ≥ {args.table_min} 行）")
    if args.limit:
        targets = targets[: args.limit]
        print(f"[L2] 本次处理: {len(targets)} 块（--limit 截断）")
    if not targets:
        print("[L2] 无目标块")
        return 0
    summary, results = l2.run_l2(targets, verbose=args.verbose)
    if "error" in summary:
        print(f"[L2] {summary['error']}")
        return 1
    print(f"[L2] 完成: 检查 {summary['checked']} | 表格标红 {summary['flagged']}"
          f" | 跳过(无PDF) {summary['skipped']}")
    out_path = args.out or os.path.join(_paths.QA_DATA_DIR, "l2_results.json")
    n = l2.write_l2_results(results, out_path)
    print(f"[L2] 结果已写出: {out_path}（{n} 条）")
    return 0


def cmd_l3(args):
    """L3 复审：--run 执行（花视觉 token）| 默认计划+成本预估"""
    import json as _json
    queue_path = args.queue or os.path.join(_paths.QA_DATA_DIR, "l1_queue.json")
    if not os.path.exists(queue_path):
        print(f"[L3] 找不到 L1 队列: {queue_path}（先跑 `l1`）")
        return 1
    items = _json.load(open(queue_path, encoding="utf-8"))["blocks"]
    plan, summary = sample.build_l3_plan(
        items, pages_per_block=args.pages,
        equation_threshold=args.eq_min, max_high=args.max_high,
        max_formula=args.max_formula)
    if args.run:
        # 执行模式：逐目标逐页跑 A+B 双视觉
        print(f"[L3执行] {summary['targets']} 目标 / {summary['pages']} 页 | "
              f"~{summary['est_vision_calls']} 调用 | 分级 {summary['priority']}")
        results, rsum = l3.run_l3_plan(plan, backend=args.backend,
                                       verbose=True, limit=args.limit)
        print(f"[L3执行] 完成: {rsum['by_block']}")
        out_path = args.out or os.path.join(_paths.QA_DATA_DIR, "l3_results.json")
        n = l3.write_l3_results(results, out_path)
        print(f"[L3执行] 结果已写出: {out_path}（{n} 条）")
        return 0
    # 计划模式
    print(f"[L3计划] 目标 {summary['targets']} 块 / {summary['pages']} 页 | "
          f"预估视觉调用 ~{summary['est_vision_calls']} 次 | 分级 {summary['priority']}")
    if args.verbose:
        shown = plan[: (args.limit or 15)] if args.limit else plan
        for p in shown:
            print(f"  [{p['priority']}] {p['basename'][:35]} p{p['start']}-{p['end']}"
                  f" → {len(p['pages'])}页 {p['pages']}")
    return 0


def cmd_rework(args):
    """返工闭环：生成返工清单（L1 高优先 + L3 fail）+ 重转命令"""
    import json as _json
    queue_path = args.queue or os.path.join(_paths.QA_DATA_DIR, "l1_queue.json")
    if not os.path.exists(queue_path):
        print(f"[返工] 找不到 L1 队列: {queue_path}（先跑 `l1`）")
        return 1
    items = _json.load(open(queue_path, encoding="utf-8"))["blocks"]
    l3res = None
    l3_path = os.path.join(_paths.QA_DATA_DIR, "l3_results.json")
    if os.path.exists(l3_path):
        l3res = _json.load(open(l3_path, encoding="utf-8")).get("results")
    rework, n = rework_mod.build_rework_list(items, l3res)
    print(f"[返工] 清单 {n} 块")
    for r in rework:
        print(f"  - {r['basename'][:38]} p{r['start']}-{r['end']}: {r['reason'][:45]}")
    if args.cmds:
        cmds = rework_mod.gen_rework_commands(rework)
        print(f"[重转命令] {len(cmds)} 条（可用 bash 批量执行）:")
        for c in cmds:
            print(f"  {c}")
    out = args.out or os.path.join(_paths.QA_DATA_DIR, "rework.json")
    n2 = rework_mod.write_rework(rework, out)
    print(f"[返工] 清单已写出: {out}（{n2} 条）")
    return 0


def cmd_report(args):
    """生成三色质检报告（放心/返工/误报）"""
    import json as _json
    allb = blocks.load_blocks("all")
    qp = args.queue or os.path.join(_paths.QA_DATA_DIR, "l1_queue.json")
    if not os.path.exists(qp):
        print(f"[报告] 找不到 L1 队列: {qp}（先跑 `l1`，避免生成误导性的全放心报告）")
        return 1
    l1q = _json.load(open(qp, encoding="utf-8"))["blocks"]
    l2res = l3res = None
    p = os.path.join(_paths.QA_DATA_DIR, "l2_results.json")
    if os.path.exists(p):
        l2res = _json.load(open(p, encoding="utf-8")).get("results")
    p = os.path.join(_paths.QA_DATA_DIR, "l3_results.json")
    if os.path.exists(p):
        l3res = _json.load(open(p, encoding="utf-8")).get("results")
    rep = report.build_report(allb, l1q, l2res, l3res)
    js = args.out or os.path.join(_paths.QA_DATA_DIR, "qa_report.json")
    md = args.md or os.path.join(_paths.QA_DATA_DIR, "qa_report.md")
    report.write_report(rep, js, md)
    print(f"[报告] 三色: 放心 {len(rep['pass'])} | 返工 {len(rep['fail'])} | 候选 {len(rep['review'])}")
    print(f"[报告] JSON: {js}")
    print(f"[报告] MD:   {md}")
    return 0


def cmd_clean(args):
    """clean 命令：块级清洗（剔页眉/页脚/页码噪音），就地覆盖 full.md。

    用法:
      python -m dtmd clean <转写目录...>          # 清洗指定目录
      python -m dtmd clean <根目录> --recursive   # 递归找所有 *_mineru/ 清洗
    """
    from dtmd.clean.block_clean import clean_out_dir
    import glob as _glob
    targets = list(args._extra or [])
    if args.recursive:
        roots = targets or ["."]
        found = []
        for root in roots:
            # 找所有含 full.md 的目录：单块(_mineru 根) + 多块(p{start}-{end} 子目录)都覆盖
            for d in _glob.glob(os.path.join(root, "**"), recursive=True):
                if os.path.isdir(d) and os.path.exists(os.path.join(d, "full.md")):
                    found.append(d)
        targets = sorted(found)
    if not targets:
        print("[clean] 未指定目录（用法: python -m dtmd clean <dir...> 或 --recursive 根目录）")
        return 1
    ok_n = skip_n = fail_n = removed_total = 0
    for d in targets:
        r = clean_out_dir(d, dry_run=args.dry_run)
        if r.get("skipped"):
            skip_n += 1
            if args.verbose:
                print(f"  [跳过] {os.path.basename(d)}: {r.get('reason')}")
        elif r.get("ok"):
            ok_n += 1
            removed_total += r["removed"]
            tag = "预演" if args.dry_run else "OK"
            print(f"  [{tag}] {os.path.basename(d)}: 删 {r['removed']} 行 "
                  f"({r['original_lines']}→{r['clean_lines']})")
        else:
            fail_n += 1
            print(f"  [失败] {os.path.basename(d)}: {r.get('error')}")
    mode = "预演(不写回)" if args.dry_run else "完成"
    print(f"[clean] {mode}: 清洗 {ok_n} | 跳过 {skip_n} | 失败 {fail_n} | 共删 {removed_total} 行")
    return 0 if fail_n == 0 else 1


def cmd_convert(args):
    """convert 命令：转发到本地/云端管线（--mode local|cloud，默认 local）"""
    from dtmd.convert import cloud, local
    main_fn = cloud.main if args.mode == "cloud" else local.main
    extra = list(args._extra or [])
    # 把主解析器已消费的 --limit / --max 拼回，保证转发到管线（终点一致：旧命令 flag 不丢）
    if args.limit is not None and "--limit" not in extra:
        extra += ["--limit", str(args.limit)]
    if args.max is not None and "--max" not in extra:
        extra += ["--max", str(args.max)]
    # HTML 模式：收集文件路径，构造 --html 透传 cloud.py 的 _html_mode()
    if args.html or args.html_dir:
        html_paths = []
        if args.html:
            html_paths.append(args.html)
        if args.html_dir:
            if not os.path.isdir(args.html_dir):
                print(f"[错误] --html-dir 目录不存在: {args.html_dir}")
                return 1
            for root, _dirs, files in os.walk(args.html_dir):
                for f in files:
                    if f.lower().endswith((".html", ".htm")):
                        html_paths.append(os.path.join(root, f))
        if not html_paths:
            print("[错误] 未找到 HTML 文件")
            return 1
        # 去重（--html 和 --html-dir 可能重叠）并转为绝对路径
        html_paths = sorted(set(os.path.abspath(p) for p in html_paths))
        # 透传 --dry-run（被主解析器消费，但 cloud.py 的 _html_mode 需要它）
        extra = ["--html"] + html_paths
        if args.dry_run:
            extra += ["--dry-run"]
        # 透传给 cloud.py：--html 后跟所有文件路径
        return cloud.main(extra)
    return main_fn(extra)


def cmd_plan(args):
    """plan 命令：扫描目录 → 智能切片 → 生成 plan.json。

    用法:
      python -m dtmd plan <目录>                              # 扫描并生成 plan.json（默认 _data/plan.json）
      python -m dtmd plan <目录> --output <路径>               # 指定输出路径
      python -m dtmd plan <目录> --dry-run                     # 只预览，不写文件
      python -m dtmd plan <目录> --budget 3000                 # 设置每日页数预算

    智能切片流程：
      1. 扫描目录下所有 PDF
      2. 对每本 PDF 获取页数 + TOC（目录）
      3. 有 TOC → 按章节边界切（≤200 页/块），保证内容完整
      4. 无 TOC 但有大标题 → 按标题位置切
      5. 都没有 → 硬切 200 页
      6. 所有块统一走云端管线（不分普通/复杂），按天分组
    """
    import json
    import fitz

    from dtmd import config as _paths
    from dtmd.convert.base import smart_slice, MAX_PAGES_PER_FILE

    # 收集参数
    extra = list(args._extra or [])
    targets = [a for a in extra if not a.startswith("-")]
    if not targets:
        print("[plan] 用法: python -m dtmd plan <目录> [--output <路径>] [--dry-run]")
        return 1

    out_path = args.out or _paths.PLAN
    dry_run = args.dry_run
    budget = args.budget or 5000

    # 扫描所有 PDF
    all_pdfs = []
    for target in targets:
        if os.path.isfile(target) and target.lower().endswith(".pdf"):
            all_pdfs.append(target)
        elif os.path.isdir(target):
            for root, _dirs, files in os.walk(target):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        all_pdfs.append(os.path.join(root, f))
        else:
            print(f"  [跳过] 非 PDF 或不存在: {target}")

    if not all_pdfs:
        print("[plan] 未找到 PDF 文件")
        return 1

    all_pdfs.sort()
    print(f"[plan] 扫描到 {len(all_pdfs)} 个 PDF，正在分析页数 + 目录结构...")

    all_blocks = []
    total_pages = 0

    for fp in all_pdfs:
        try:
            doc = fitz.open(fp)
            pages = doc.page_count
            doc.close()
        except Exception:
            print(f"  [跳过] 无法读取: {os.path.basename(fp)}")
            continue

        # 所有文件统一处理：超过 200 页的智能切片，否则单块
        if pages > MAX_PAGES_PER_FILE:
            blocks = smart_slice(fp, pages, MAX_PAGES_PER_FILE)
            print(f"  {os.path.basename(fp)}: {pages}页 → 切 {len(blocks)} 块")
        else:
            blocks = [{"file": fp, "kind": "PDF", "start": 1, "end": pages, "pages": pages}]
            print(f"  {os.path.basename(fp)}: {pages}页 → 1 块")

        total_pages += pages
        all_blocks.extend(blocks)

    # 按天分组（每天 ≤ budget 页）
    days = []
    day_blocks = []
    day_pages = 0
    for b in all_blocks:
        if day_pages + b["pages"] > budget and day_blocks:
            days.append({"day": len(days) + 1, "blocks": day_blocks})
            day_blocks = []
            day_pages = 0
        day_blocks.append(b)
        day_pages += b["pages"]
    if day_blocks:
        days.append({"day": len(days) + 1, "blocks": day_blocks})

    plan = {"days_normal": days}

    block_count = sum(len(d["blocks"]) for d in days)
    block_pages = sum(sum(b["pages"] for b in d["blocks"]) for d in days)
    print(f"\n[plan] 统计: {len(days)} 天, {block_count} 块, {block_pages} 页")

    if dry_run:
        print(f"[plan] DRY-RUN 完成，未写文件")
        return 0

    # 备份旧 plan
    if os.path.exists(out_path):
        import shutil
        bak = out_path.replace(".json", f"_bak_{os.path.basename(targets[0])}_{total_pages}p.json")
        shutil.copy2(out_path, bak)
        print(f"[plan] 旧 plan 已备份: {bak}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"[plan] plan.json 已写入: {out_path}")
    return 0


def cmd_merge(args):
    """merge 命令：合并切片输出（p{start}-{end}/full.md → 完整 full.md）。

    用法:
      python -m dtmd merge <目录>                     # 合并指定 _mineru/ 目录
      python -m dtmd merge <目录> --recursive          # 递归合并所有 _mineru/
      python -m dtmd merge <目录> --dry-run            # 只预览，不写文件
    """
    from dtmd.convert.base import merge_mineru_dir

    extra = list(args._extra or [])
    targets = [a for a in extra if not a.startswith("-")]
    recursive = args.recursive

    if not targets:
        targets = ["."]

    ok_n = skip_n = fail_n = 0
    all_targets = []

    for t in targets:
        if recursive and os.path.isdir(t):
            for root, dirs, _files in os.walk(t):
                for d in dirs:
                    if d.endswith("_mineru"):
                        all_targets.append(os.path.join(root, d))
        elif os.path.isdir(t):
            all_targets.append(t)
        else:
            print(f"  [跳过] 目录不存在: {t}")

    if not all_targets:
        print("[merge] 未找到 _mineru/ 目录")
        return 1

    for d in sorted(set(all_targets)):
        r = merge_mineru_dir(d, dry_run=args.dry_run)
        if r.get("error"):
            if "未找到切片" in r["error"]:
                skip_n += 1
                if args.verbose:
                    print(f"  [跳过] {os.path.basename(d)}: {r['error']}")
            else:
                fail_n += 1
                print(f"  [失败] {os.path.basename(d)}: {r['error']}")
        else:
            ok_n += 1
            tag = "预演" if args.dry_run else "合并"
            print(f"  [{tag}] {os.path.basename(d)}: {r['merged']} 片 → {r['output']}")

    mode = "预演(不写回)" if args.dry_run else "完成"
    print(f"[merge] {mode}: 合并 {ok_n} | 跳过 {skip_n} | 失败 {fail_n}")
    return 0 if fail_n == 0 else 1


COMMANDS = {
    "list": (cmd_list, "列出块清单与完成状态"),
    "plan": (cmd_plan, "扫描目录 → 智能切片 → 生成 plan.json"),
    "merge": (cmd_merge, "合并切片输出（p{start}-{end}/full.md → 完整 full.md）"),
    "l1": (cmd_l1, "L1 自动检查（完整性/页数/md_lint/图片引用）"),
    "l2": (cmd_l2, "L2 表格复核（camelot）"),
    "l3": (cmd_l3, "L3 复审计划（选目标+选页+成本预估）"),
    "rework": (cmd_rework, "返工闭环（生成返工清单+重转命令）"),
    "report": (cmd_report, "生成三色质检报告"),
    "convert": (cmd_convert, "转换管线（--mode local|cloud，默认 local）"),
    "clean": (cmd_clean, "块级清洗（剔除转写产物页眉/页脚/页码噪音）"),
}


def build_parser():
    ap = argparse.ArgumentParser(
        prog="dtmd",
        description="document-to-markdown：PDF/Word/PPT → AI-ready Markdown（转换 + 三层质检）")
    ap.add_argument("cmd", nargs="?", default=None,
                    choices=sorted(COMMANDS), help="子命令")
    from dtmd import __version__
    ap.add_argument("--version", action="version", version=f"dtmd {__version__}")
    ap.add_argument("--scope", choices=["all", "complex", "normal"], default="all",
                    help="扫描范围（默认 all=复杂+普通）")
    ap.add_argument("--verbose", action="store_true", help="详细输出")
    ap.add_argument("--limit", type=int, default=None,
                    help="详细输出时最多显示 N 条（防刷屏）")
    ap.add_argument("--out", default=None,
                    help="输出路径（默认 _data/qa/l1_queue.json）")
    ap.add_argument("--queue", default=None,
                    help="L1 队列路径（l2 用，默认 _data/qa/l1_queue.json）")
    ap.add_argument("--table-min", type=int, default=10,
                    help="L2 表格标记行数阈值（l2 用，默认 10）")
    ap.add_argument("--pages", type=int, default=3,
                    help="L3 每块抽页数（l3 用，默认 3）")
    ap.add_argument("--eq-min", type=int, default=20,
                    help="L3 公式密集阈值（l3 用，默认 20）")
    ap.add_argument("--max-high", type=int, default=None,
                    help="L3 高优先目标上限（l3 用）")
    ap.add_argument("--max-formula", type=int, default=10,
                    help="L3 公式密集代表上限（l3 用，默认 10）")
    ap.add_argument("--cmds", action="store_true",
                    help="生成重转命令（rework 用）")
    ap.add_argument("--md", default=None,
                    help="报告 md 输出路径（report 用）")
    ap.add_argument("--run", action="store_true",
                    help="L3 执行模式（跑视觉，花 token）")
    ap.add_argument("--backend", default="parallel",
                    choices=["parallel", "qwen", "glm", "gemini", "openai"],
                    help="L3 视觉后端（默认 parallel 双视觉）")
    ap.add_argument("--mode", default="local", choices=["local", "cloud"],
                    help="convert 管线（默认 local）")
    ap.add_argument("--max", type=int, default=None, dest="max",
                    help="convert 用：最多转 N 块（local 管线）")
    ap.add_argument("--budget", type=int, default=None,
                    help="plan 用：每日页数预算（默认 5000）")
    ap.add_argument("--recursive", action="store_true",
                    help="clean 用：递归查找根目录下所有 *_mineru/ 转写目录")
    ap.add_argument("--dry-run", action="store_true",
                    help="clean 用：预演模式，只统计删除行数不写回 full.md")
    ap.add_argument("--html", default=None,
                    help="convert 用：上传单个 HTML 文件到云端转写（--mode cloud 时有效）")
    ap.add_argument("--html-dir", default=None,
                    help="convert 用：上传目录下所有 HTML 文件到云端转写（--mode cloud 时有效）")
    return ap


def main(argv=None):
    ap = build_parser()
    args, unknown = ap.parse_known_args(argv)
    args._extra = unknown  # convert 的额外参数（day/--dry-run 等）透传
    # 数值参数防呆：负数/非法范围直接报错
    for name, val in (("--limit", args.limit), ("--table-min", args.table_min),
                      ("--pages", args.pages), ("--eq-min", args.eq_min),
                      ("--max-formula", args.max_formula), ("--max", args.max), ("--max-high", args.max_high)):
        if val is not None and val < 0:
            ap.error(f"{name} 不能为负（收到 {val}）")
    if not args.cmd or args.cmd not in COMMANDS:
        ap.print_help()
        return 1
    try:
        return COMMANDS[args.cmd][0](args)
    except (FileNotFoundError, RuntimeError) as e:
        # 防呆：缺数据/源文件（含 fitz 抛的 RuntimeError 子类）给友好提示，不裸 traceback
        print(f"[错误] 找不到数据/源文件: {e}\n"
              f"  提示: plan.json 是你的私有数据，不随仓库发布。见 README「准备数据目录」")
        return 1
    except ValueError as e:
        # 防呆：plan.json 缺字段/格式问题
        print(f"[错误] 数据格式问题: {e}\n"
              f"  提示: 检查 _data/plan.json 是否包含 pending_normal/pending_complex 字段")
        return 1


if __name__ == "__main__":
    sys.exit(main())
