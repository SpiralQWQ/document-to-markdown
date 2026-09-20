#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dtmd.convert.enrich_wizard — 插图融合/清理的交互向导（产品经理风格）。

设计原则（对齐 _video_tools/wizard.py）：
- 每个问题讲清"干嘛的/选错会怎样/默认是啥"，直接回车用默认
- 单本/批量都先统计再询问，让用户看到代价（图片数）再决定
- 全部交互函数可被 CLI 命令与 convert 收尾钩子复用
"""
from __future__ import annotations

import os
import sys

NOTES_DIR = "images_notes"  # enrich 产物目录（与 enrich.py 保持一致）

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _ask(question: str, options: dict, default_key: str) -> str:
    """产品经理风格提问。options: {key: (label, desc)}；回车=默认。非交互（EOF）→ 默认。"""
    print(f"\n{question}")
    for k, (label, desc) in options.items():
        mark = "（默认）" if k == default_key else ""
        print(f"  {k}. {label} {mark} —— {desc}")
    try:
        ans = input(f"请输入 [{default_key}]: ").strip().upper()
    except EOFError:  # 非交互环境（CI/管道）：用默认，不挂死
        print(f"  [非交互环境] 采用默认 {default_key}")
        return default_key
    if not ans:
        return default_key
    if ans in options:
        return ans
    print(f"  [X] 请输入 {list(options.keys())} 中的一个（或直接回车用默认）")
    return _ask(question, options, default_key)  # 递归重问


def ask_enrich(kind: str, stats: dict, default: str = "B") -> bool:
    """转写后询问：要不要对插图做 OCR+GLM 融合。返回 True=要。

    kind: "single"（单本）| "batch"（批量）
    stats: {"books": n, "images": n}
    """
    scale = "本" if kind == "single" else "批"
    if kind == "single":
        scope = f"这本书共 {stats['images']} 张插图"
    else:
        scope = f"本批 {stats['books']} 本书 / 共 {stats['images']} 张插图"
    if not stats.get("images"):
        print(f"\n[enrich] {scope[:-2]}没有插图，无需融合")
        return False
    choice = _ask(
        f"【插图融合】{scope}。要不要把插图做 OCR + GLM 理解，内容直接写进 md？",
        {
            "A": ("要", "AI 读 md 时连插图内容都能看到；每张约 5s（GLM 免费版），可随时 Ctrl+C 中断，已生成的会记住"),
            "B": ("不要", "保持图片引用不动；之后可用 `dtmd enrich <目录>` 单独补"),
            "C": ("跳过询问", "本批不融合，且本次会话后续批次不再问"),
        },
        default_key=default)
    return choice == "A"


# 会话级"跳过询问"记忆（convert 收尾钩子用，进程内有效）
_SESSION_SKIP = {"skip": False}


def session_skip_enrich() -> bool:
    return _SESSION_SKIP["skip"]


def set_session_skip(skip: bool) -> None:
    _SESSION_SKIP["skip"] = skip


def ask_and_run_enrich(out_dirs: list, kind: str = "single") -> None:
    """询问 → 执行融合（convert 收尾钩子与 dtmd enrich 共用主流程）。

    out_dirs: 一个或多个 _mineru/ 目录
    """
    if _SESSION_SKIP["skip"]:
        return
    from dtmd.convert.enrich import count_images
    total_imgs = 0
    per_dir = {}
    for d in out_dirs:
        n = count_images(d)["count"]
        per_dir[d] = n
        total_imgs += n
    stats = {"books": len(out_dirs), "images": total_imgs}
    if not ask_enrich(kind, stats):
        if not any(k in ("B", "C") for k in ()):
            pass
        return
    _run_enrich(out_dirs)


def _run_enrich(out_dirs: list) -> None:
    """执行融合：逐目录 enrich_dir + embed_notes + 汇总。"""
    from dtmd.convert.enrich import enrich_dir, embed_notes
    glm_ready = bool(os.environ.get("GLM_API_KEY", "").strip())
    if not glm_ready:
        print("\n[enrich] 未配置 GLM_API_KEY → 仅 OCR 模式（图内文字可提取，画面语义无）")
    tot_done = tot_skip = tot_embed = 0
    for d in out_dirs:
        name = os.path.basename(d.rstrip("\\/"))
        print(f"\n[enrich] {name}")
        s = enrich_dir(d, glm=glm_ready)
        e = embed_notes(d)
        print(f"  [enrich] 图片笔记：新增 {s['done']} / 跳过 {s['skipped']} / 空 {s['empty']}"
              f"（共 {s['total']}）")
        print(f"  [enrich] 内嵌 full.md：{e['files']} 个文件 / {e['embedded']} 处"
              + (f" / 缺笔记 {e['missing']}" if e["missing"] else ""))
        tot_done += s["done"]; tot_skip += s["skipped"]; tot_embed += e["embedded"]
    print(f"\n[enrich] 全部完成：新增 {tot_done} / 跳过 {tot_skip} / 内嵌 {tot_embed} 处")


def run_enrich_flow(out_dirs: list, kind: str = "single", assume_yes: bool = False) -> None:
    """对外主入口：assume_yes=True 跳过询问直接融合（CLI --yes 用）。"""
    if assume_yes:
        _run_enrich(out_dirs)
        return
    if _SESSION_SKIP["skip"] and kind == "batch":
        return
    from dtmd.convert.enrich import count_images
    total_imgs = sum(count_images(d)["count"] for d in out_dirs)
    stats = {"books": len(out_dirs), "images": total_imgs}
    if not ask_enrich(kind, stats):
        return
    _run_enrich(out_dirs)


# ═══════════════════════════════════════════════════════════════
# 清理向导（dtmd cleanup）：列清单 → 确认 → 删
# ═══════════════════════════════════════════════════════════════

def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def scan_cleanup(out_dir: str) -> dict:
    """扫描可清理产物，分类计数+大小。不删任何东西。

    json/pdf/slices 类记录【具体文件路径】（按文件删，防止 rmtree 误伤同目录的 full.md）；
    images/notes 类记录【目录路径】（整目录删）。
    """
    plan = {"images": {"dirs": [], "files": 0, "bytes": 0},
            "notes": {"dirs": [], "files": 0, "bytes": 0},
            "json": {"dirs": [], "files": 0, "bytes": 0},
            "pdf": {"dirs": [], "files": 0, "bytes": 0},
            "slices": {"dirs": [], "files": 0, "bytes": 0}}
    if not os.path.isdir(out_dir):
        return plan
    for root, _dirnames, files in os.walk(out_dir):
        base = os.path.basename(root)
        if base == "images":
            imgs = [f for f in files if f.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"))]
            if imgs:
                plan["images"]["dirs"].append(root)
                plan["images"]["files"] += len(imgs)
                plan["images"]["bytes"] += sum(
                    os.path.getsize(os.path.join(root, f)) for f in imgs if os.path.exists(
                        os.path.join(root, f)))
            continue  # images/ 内不会有 json/pdf 值得扫
        if base == NOTES_DIR:
            mds = [f for f in files if f.endswith(".md")]
            if mds:
                plan["notes"]["dirs"].append(root)
                plan["notes"]["files"] += len(mds)
                plan["notes"]["bytes"] += sum(
                    os.path.getsize(os.path.join(root, f)) for f in mds if os.path.exists(
                        os.path.join(root, f)))
            continue
        for f in files:
            sz = 0
            try:
                sz = os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
            low = f.lower()
            fp = os.path.join(root, f)
            if low.endswith(".json"):
                plan["json"]["files"] += 1
                plan["json"]["bytes"] += sz
                plan["json"]["dirs"].append(fp)  # 文件路径
            elif low.endswith(".pdf"):
                plan["pdf"]["files"] += 1
                plan["pdf"]["bytes"] += sz
                plan["pdf"]["dirs"].append(fp)  # 文件路径
            elif low.startswith("tmp_") and low.endswith(".zip"):
                plan["slices"]["files"] += 1
                plan["slices"]["bytes"] += sz
                plan["slices"]["dirs"].append(fp)  # 文件路径
    return plan


def _fmt_mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f}MB" if n >= 1024 * 1024 else f"{n / 1024:.0f}KB"


def run_cleanup_flow(out_dir: str, assume_yes: bool = False) -> int:
    """清理向导：列分类清单 → 确认 → 删（images/notes 先于 json/pdf，可只删一部分）。

    安全护栏：full.md 必须存在且非空才允许删 images/notes（保证融合产物在）。
    返回 0=删了/1=取消。
    """
    plan = scan_cleanup(out_dir)
    cats = [(k, v) for k, v in plan.items() if v["files"]]
    if not cats:
        print(f"[cleanup] {os.path.basename(out_dir)}：无可清理产物")
        return 1
    print(f"\n【清理预览】{out_dir}")
    print("  以下中间产物将可删除（full.md 最终产物保留）：")
    labels = {"images": "插图 images/", "notes": "图片笔记 images_notes/",
              "json": "中间 json", "pdf": "备份 pdf", "slices": "临时 zip"}
    for k, v in cats:
        print(f"    {labels[k]:24s} {v['files']:4d} 个  {_fmt_mb(v['bytes'])}")
    # 护栏
    full_md = os.path.join(out_dir, "full.md")
    if plan["notes"]["files"] and not (os.path.isfile(full_md) and
                                       os.path.getsize(full_md) > 0):
        print("  [X] full.md 缺失或为空，拒绝删除 images_notes（融合成果会丢）")
        return 1
    if not assume_yes:
        choice = _ask(
            "确认删除以上产物？（full.md 不受影响，删除后不可恢复）",
            {"A": ("全部删除", "上面列出的全部中间产物"),
             "B": ("只删图片类", "images/ + images_notes/（已内嵌进 full.md）"),
             "C": ("取消", "什么都不删，保留审核依据")},
            default_key="C")
        if choice == "C":
            print("[cleanup] 已取消，未删除任何文件")
            return 1
        scope = ["images", "notes", "json", "pdf", "slices"] if choice == "A" \
            else ["images", "notes"]
    else:
        scope = ["images", "notes", "json", "pdf", "slices"]
    import shutil
    removed = 0
    for k in scope:
        for d in plan[k]["dirs"]:
            if k in ("images", "notes"):
                shutil.rmtree(d, ignore_errors=True)  # 整目录删
            else:
                try:
                    os.remove(d)  # json/pdf/slices 按文件删（防误伤同目录 full.md）
                except OSError:
                    pass
            removed += 1
    print(f"[cleanup] 已删除 {removed} 项（full.md 保留）")
    return 0
