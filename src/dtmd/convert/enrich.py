#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dtmd.convert.enrich — 插图融合：把 MinerU 抽出的插图做 OCR+GLM 理解，内容内嵌进 full.md。

背景
----
MinerU 转写 PDF 时，纯插图（封面/图标/照片/图表截图）原样留在 images/，
full.md 里只有死引用 ![](images/xx.jpg)——图里的信息 AI 读不到。

本模块三步解决：
  1. enrich_image():  单张图 → OCR(免费) + GLM 视觉理解(可选) → images_notes/xx.md
  2. enrich_dir():    整个 _mineru/ 遍历 images/ 全量转（断点续跑：已有 md 跳过）
  3. embed_notes():   full.md 的图片引用 → 替换为笔记全文（"## 插图笔记：xx"）

调用
----
    from dtmd.convert.enrich import enrich_dir, embed_notes, count_images
    stats = enrich_dir(out_dir, glm=True, delay=5.0)   # 逐张转写
    stats = embed_notes(out_dir)                        # 内嵌进 full.md（就地覆盖）

设计
----
- GLM 不可用（未配 GLM_API_KEY）→ 自动降级纯 OCR，不阻塞
- GLM 限流(429) → 持续重试直到成功（免费版 flashx 建议 delay≥5s）
- 断点续跑：images_notes/xx.md 已存在且非空 → 跳过
- embed 就地覆盖 full.md（原始 MinerU 输出 {原名}.md 未动，可回溯）
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
NOTES_DIR = "images_notes"          # 图片笔记输出目录（与 images/ 同级）
GLM_MODEL = "glm-4.6v-flashx"       # 免费稳定版；限流重试内置
GLM_PROMPT = ("请描述这张图片的内容（主体/场景/图表/界面/代码/文字信息），"
              "用于辅助制作学习笔记。简洁准确。")
# 限流重试上限（防死循环：连续 N 次失败后放弃该图，GLM 段留空）
GLM_MAX_ATTEMPTS = 5


def _err(msg):
    print(f"[错误] {msg}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
# GLM 视觉理解（单文件实现，不依赖归档工具）
# ═══════════════════════════════════════════════════════════════

def glm_describe(image_path: str, delay: float = 5.0, retry_delay: float = 30.0) -> str:
    """GLM 看图返回描述；限流重试；失败返回空串（调用方降级）。"""
    api_key = os.environ.get("GLM_API_KEY", "").strip()
    if not api_key:
        return ""
    if delay > 0:
        time.sleep(delay)
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except OSError as e:
        _err(f"读取图片失败 {image_path}: {e}")
        return ""
    ext = os.path.splitext(image_path)[1].lstrip(".").lower()
    if ext == "jpg":
        ext = "jpeg"
    body = {
        "model": GLM_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{b64}"}},
                {"type": "text", "text": GLM_PROMPT},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    for attempt in range(1, GLM_MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:  # 限流：等待重试
                print(f"    [限流] 429，等待 {retry_delay}s 重试（第{attempt}/{GLM_MAX_ATTEMPTS}次）")
                time.sleep(retry_delay)
                continue
            print(f"    [GLM] HTTP {e.code}，放弃该图")
            return ""
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            print(f"    [GLM] {type(e).__name__}，等待重试（第{attempt}/{GLM_MAX_ATTEMPTS}次）")
            time.sleep(retry_delay)
    return ""  # 重试耗尽


# ═══════════════════════════════════════════════════════════════
# OCR（本地 RapidOCR，免费；引擎不可用时降级为空）
# ═══════════════════════════════════════════════════════════════

_ocr_engine = None
_ocr_failed = False


def _get_ocr():
    """懒加载本地 RapidOCR；加载失败返回 None（纯 GLM 模式）。"""
    global _ocr_engine, _ocr_failed
    if _ocr_engine is not None or _ocr_failed:
        return _ocr_engine
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
        _ocr_engine = RapidOCR()
    except Exception as e:
        print(f"[enrich] 本地 OCR 不可用（{type(e).__name__}），将仅用 GLM")
        _ocr_failed = True
    return _ocr_engine


def ocr_image(image_path: str) -> str:
    """单张图 OCR；引擎不可用/无文字 → 空串。"""
    engine = _get_ocr()
    if engine is None:
        return ""
    try:
        result, _ = engine(image_path)
        if not result:
            return ""
        # RapidOCR 返回 [[box, text, score], ...]；按 y 坐标排序保持阅读顺序
        items = sorted(result, key=lambda r: (min(p[1] for p in r[0]), min(p[0] for p in r[0])))
        return "\n".join(str(r[1]) for r in items).strip()
    except Exception as e:
        print(f"    [OCR] 失败 {os.path.basename(image_path)}: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════
# 统计 / 单图 / 整本
# ═══════════════════════════════════════════════════════════════

def count_images(out_dir: str) -> dict:
    """统计 out_dir 下所有 images/ 目录（含切片子目录）的图片数。"""
    total = 0
    dirs = []
    for root, dirnames, filenames in os.walk(out_dir):
        dirnames[:] = [d for d in dirnames if d != NOTES_DIR]
        if os.path.basename(root) == "images":
            n = sum(1 for f in filenames if f.lower().endswith(IMG_EXTS))
            if n:
                total += n
                dirs.append(root)
    return {"count": total, "dirs": dirs}


def _write_note(note_path: str, stem: str, ocr_text: str, glm_text: str) -> None:
    parts = [f"# {stem}", "", "## 图片内容（OCR）", "", ocr_text or "（无文字）"]
    if glm_text:
        parts += ["", "## GLM 画面理解", "", glm_text]
    with open(note_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def enrich_image(images_dir: str, filename: str, glm: bool = True,
                 delay: float = 5.0, retry_delay: float = 30.0) -> str:
    """单张图 → images_notes/同名.md。返回 "done" | "skipped" | "empty"。"""
    notes_dir = os.path.join(os.path.dirname(os.path.abspath(images_dir)), NOTES_DIR)
    os.makedirs(notes_dir, exist_ok=True)
    stem = os.path.splitext(filename)[0]
    note_path = os.path.join(notes_dir, stem + ".md")
    if os.path.exists(note_path) and os.path.getsize(note_path) > 0:
        return "skipped"  # 断点续跑
    img_path = os.path.join(images_dir, filename)
    ocr_text = ocr_image(img_path)
    glm_text = ""
    if glm and os.environ.get("GLM_API_KEY", "").strip():
        glm_text = glm_describe(img_path, delay, retry_delay)
        if not glm_text:
            print(f"    [GLM] {filename} 未获取到描述（仅 OCR）")
    _write_note(note_path, stem, ocr_text, glm_text)
    return "done" if (ocr_text or glm_text) else "empty"


def enrich_dir(out_dir: str, glm: bool = True, delay: float = 5.0,
               retry_delay: float = 30.0, verbose: bool = True) -> dict:
    """整个 _mineru/（含切片子目录）的插图批量转写。返回统计 dict。

    断点续跑：已存在的同名笔记跳过。GLM 失败的图仍写 OCR-only 笔记，不阻塞。
    """
    info = count_images(out_dir)
    stats = {"total": info["count"], "done": 0, "skipped": 0, "empty": 0, "dirs": info["dirs"]}
    if not info["dirs"]:
        return stats
    for images_dir in info["dirs"]:
        imgs = sorted(f for f in os.listdir(images_dir) if f.lower().endswith(IMG_EXTS))
        for i, fn in enumerate(imgs, 1):
            if verbose:
                tag = f"{os.path.basename(out_dir)}[{i}/{len(imgs)}]"
                print(f"  [enrich] {tag} {fn}")
            r = enrich_image(images_dir, fn, glm=glm, delay=delay, retry_delay=retry_delay)
            stats[r] += 1
    return stats


# ═══════════════════════════════════════════════════════════════
# 内嵌：full.md 图片引用 → 笔记全文
# ═══════════════════════════════════════════════════════════════

def _find_note(md_dir: str, stem: str) -> str | None:
    """找图片对应笔记（切片书场景全覆盖）：
    1. md 同级 images_notes/{stem}.md
    2. 向上找父级链的 images_notes/（切片子块 → 书根）
    3. 向下递归当前树（嵌套结构兜底）
    """
    d = os.path.abspath(md_dir)
    direct = os.path.join(d, NOTES_DIR, stem + ".md")
    if os.path.isfile(direct):
        return direct
    # 向上找（限 5 层，防跑出书目录）
    p = os.path.dirname(d)
    for _ in range(5):
        cand = os.path.join(p, NOTES_DIR, stem + ".md")
        if os.path.isfile(cand):
            return cand
        nxt = os.path.dirname(p)
        if nxt == p:
            break
        p = nxt
    # 向下递归当前树
    for root, _dirs, _files in os.walk(md_dir):
        cand = os.path.join(root, NOTES_DIR, stem + ".md")
        if os.path.isfile(cand):
            return cand
    return None


def embed_notes(out_dir: str, dry_run: bool = False) -> dict:
    """把 images_notes/ 内容内嵌进该目录树所有 full.md 的图片引用处（就地覆盖）。

    多块书：p{start}-{end}/full.md 各自内嵌（笔记跨子目录找）。
    返回 {"files": n, "embedded": n, "missing": n}。
    """
    result = {"files": 0, "embedded": 0, "missing": 0}
    for root, _dirs, files in os.walk(out_dir):
        if "full.md" not in files:
            continue
        md_path = os.path.join(root, "full.md")
        with open(md_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        pat = re.compile(r"!\[[^\]]*\]\(images/([^)\s]+)\)")
        found = pat.findall(content)
        if not found:
            continue
        result["files"] += 1
        if dry_run:
            result["embedded"] += len(found)
            continue
        missing = []

        def repl(m):
            fname = m.group(1)
            stem = os.path.splitext(fname)[0]
            note = _find_note(root, stem)
            if note is None:
                missing.append(fname)
                return m.group(0)  # 无笔记保留原引用
            with open(note, encoding="utf-8") as f:
                body = f.read()
            lines = body.splitlines()
            if lines and lines[0].startswith("# "):
                lines = lines[1:]  # 去掉 "# stem" 首行防一级标题冲突
            block = "\n".join(lines).strip()
            return f"\n\n## 插图笔记：{stem}\n\n{block}\n"

        new_content = pat.sub(repl, content)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        result["embedded"] += len(found) - len(missing)
        result["missing"] += len(missing)
    return result
