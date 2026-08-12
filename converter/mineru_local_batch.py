#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU 本地批量转换脚本（PDF → MD）
使用本地环境（CUDA加速），按页范围拆分 + 串行执行，限制并发度

用法:
  python mineru_local_batch.py               # 转所有未转PDF
  python mineru_local_batch.py --limit N      # 只转前N个文件
  python mineru_local_batch.py --day D        # 仅转计划中 DayD 的块
  python mineru_local_batch.py --dry-run      # 只预览，不执行

输出: {原文件所在目录}/{原名}_mineru/p{start}-{end}/full.md+images+json
单块文件: {原文件所在目录}/{原名}_mineru/full.md+images+json
"""
import os, sys, json, time, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paths as _paths
ROOT = _paths.TOOLS
TOOLS = _paths.TOOLS
DATA_DIR = _paths.DATA_DIR
PLAN = _paths.PLAN
MINERU_ENV = _paths.MINERU_ENV
PYTHON = os.path.join(MINERU_ENV, "Scripts", "python.exe") if MINERU_ENV else sys.executable
MINERU_CLI = os.path.join(MINERU_ENV, "Scripts", "mineru.exe") if MINERU_ENV else "mineru"
OUTPUT_DIR = os.path.join(ROOT, "_output")  # 原始 PDF 切片存放处

EXTS = ('.pdf', '.pptx', '.doc', '.docx')
MAX_CONCURRENT = 1  # vlm-engine吃显存，单任务保稳定（给 Claude 留资源）
TIMEOUT_PER_PAGE = 15  # 每页最长处理秒数（防卡死）
DEFAULT_BACKEND = "vlm-engine"  # 最高精度本地引擎


def safe(name):
    """文件名安全替换"""
    import re
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def is_done(out_dir):
    """该输出已存在 full.md 或 json → 跳过"""
    if not os.path.isdir(out_dir):
        return False
    if os.path.exists(os.path.join(out_dir, "full.md")):
        return True
    return any(fn.lower().endswith(".json") for fn in os.listdir(out_dir))


def chunk_large_pdf(filepath):
    """对 >200MB 的 PDF 先用 fitz 切片成小文件，返回临时文件列表"""
    try:
        import fitz
    except ImportError:
        print("[WARN] PyMuPDF 不可用，大文件跳过切片"); return []

    size_mb = os.path.getsize(filepath) / 1048576
    if size_mb <= 200:
        return [filepath]

    base = os.path.splitext(safe(os.path.basename(filepath)))[0]
    src = fitz.open(filepath)
    total_pages = src.page_count
    # 按每 190 页切一块
    slice_size = 190
    temp_files = []
    num_slices = (total_pages + slice_size - 1) // slice_size
    for i in range(num_slices):
        out_name = f"d_{base}_p{i*slice_size + 1}-{min((i+1)*slice_size, total_pages)}.pdf"
        out_path = os.path.join(OUTPUT_DIR, out_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        dst = fitz.open()
        from_page = i * slice_size
        to_page = min(from_page + slice_size, total_pages) - 1
        dst.insert_pdf(src, from_page=from_page, to_page=to_page)
        dst.save(out_path)
        dst.close()
        temp_files.append(out_path)
    src.close()
    return temp_files or [filepath]


def convert_single(pdf_path, out_dir, backend="vlm-engine"):
    """调用 MinerU CLI 转换单个 PDF"""
    cmd = [
        MINERU_CLI,
        "-p", pdf_path,
        "-o", out_dir,
        "-m", "auto",
        "-b", backend,
        "-f", "true",
        "-t", "true",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=max(int(len(pdf_path.split()) * TIMEOUT_PER_PAGE), 300))
        if proc.returncode != 0:
            stderr = proc.stderr[-200:] if proc.stderr else "no output"
            print(f"[ERROR] 转换失败 {os.path.basename(pdf_path)}: {stderr}")
            return False
        print(f"[OK] {os.path.basename(pdf_path)} → {out_dir}")
        return True
    except subprocess.TimeoutExpired:
        print(f"[ERROR] 超时: {os.path.basename(pdf_path)}")
        return False


def main():
    args = [a for a in sys.argv[1:]]
    dry_run = "--dry-run" in args
    limit = None
    day = None
    backend = DEFAULT_BACKEND

    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--day" in args:
        day = int(args[args.index("--day") + 1])
    if "--backend" in args:
        backend = args[args.index("--backend") + 1]

    # 加载计划
    plan = json.load(open(PLAN, encoding="utf-8"))
    blocks = []
    if day:
        blocks = plan["days"][day - 1]["blocks"]
    else:
        # 扫描所有天，收集待转块
        for d in plan["days"]:
            for b in d["blocks"]:
                blocks.append(b)

    # 生成任务清单（跳过已完成 + 源文件不存在）
    tasks = []
    for i, b in enumerate(blocks):
        if not os.path.exists(b["file"]):
            print(f"  跳过(源文件删除): {os.path.basename(b['file'])} p{b['start']}-{b['end']}")
            continue
        orig_dir = os.path.dirname(b["file"])
        base = safe(os.path.splitext(os.path.basename(b["file"]))[0])
        out_root = os.path.join(orig_dir, base + "_mineru")
        multi = len([x for x in blocks if x["file"] == b["file"]]) > 1
        out_dir = os.path.join(out_root, f"p{b['start']}-{b['end']}") if multi else out_root
        if is_done(out_dir):
            print(f"  跳过(已完成): {os.path.basename(b['file'])} p{b['start']}-{b['end']}")
            continue
        tasks.append({"block": b, "tmp_file": None, "out": out_dir})

    if not tasks:
        print("[Day] 全部已完成"); return 0
    if limit:
        tasks = tasks[:limit]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_pages = sum(t["block"]["pages"] for t in tasks)
    print(f"[本地批量] {len(tasks)} 个任务 / {total_pages} 页 / 后端 {backend}")
    print(f"[限制] 最多并发 {MAX_CONCURRENT} 个（给 Claude 留资源）\n")

    if dry_run:
        for t in tasks:
            bf = t["block"]; tmp = chunk_large_pdf(bf["file"])
            print(f"  [DRY-RUN] {os.path.basename(bf['file'])} → {t['out']}")
            for tf in tmp:
                print(f"    切片: {os.path.basename(tf)} ({bf['pages']}页)")
        print("\n[DRY-RUN] 完成，未执行。去掉 --dry-run 开始转换"); return 0

    # 预处理：切片大文件
    for t in tasks:
        bf = t["block"]
        tmp = chunk_large_pdf(bf["file"])
        t["tmp_file"] = tmp

    # 串行执行，每次最多 MAX_CONCURRENT 并发
    success_count = 0
    fail_count = 0
    skipped = sum(1 for t in tasks if is_done(t["out"]))
    pending = len(tasks) - skipped

    print(f"\n[执行] {pending} 个待转任务...\n")
    for idx, t in enumerate(tasks, 1):
        bf = t["block"]
        tmp_files = t["tmp_file"] if t["tmp_file"] else [bf["file"]]

        for j, tmp in enumerate(tmp_files):
            result = convert_single(tmp, t["out"], backend)
            if result:
                success_count += 1
            else:
                fail_count += 1

        if idx % 5 == 0 or idx == len(tasks):
            elapsed = time.time()
            print(f"\n进度: {idx}/{len(tasks)} 已完成, 成功 {success_count}, 失败 {fail_count}\n")

    # 清理切片临时文件
    try:
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for f in files:
                fp = os.path.join(root, f)
                os.remove(fp)
        print("\n[清理] 切片临时文件已清除")
    except OSError as e:
        print(f"\n[WARN] 清理失败: {e}")

    print(f"\n[总结] 成功 {success_count}, 失败 {fail_count}, 跳过 {skipped}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    main()
