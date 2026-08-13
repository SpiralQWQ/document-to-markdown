#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vision.py — L3 视觉层：fitz 渲染源页 + vision_analyzer 双视觉集成

- render_page: 用 fitz 把 PDF 页渲染成 PNG（整页 或 bbox 区域裁切）
- analyze_image: 调 vision_analyzer.py（Qwen-VL + GLM-4.6V 双视觉）
"""
import os
import sys
import json
import tempfile
import subprocess

# vision_analyzer.py 位置（全局工具，用户环境）
VISION_ANALYZER = os.environ.get("DTM_VISION_ANALYZER", "vision_analyzer.py")  # 环境变量可指向本机路径


def find_slice_pdf(out_dir):
    """在输出目录找切片 PDF（{uuid}_origin.pdf 或 origin.pdf）。"""
    if not os.path.isdir(out_dir):
        return None
    for fn in os.listdir(out_dir):
        if fn.endswith("_origin.pdf") or fn == "origin.pdf":
            return os.path.join(out_dir, fn)
    return None


def render_page(pdf_path, page_idx, bbox=None, out_path=None, zoom=2.0):
    """用 fitz 渲染 PDF 页面为 PNG。

    参数:
      page_idx: 0-based 页码
      bbox: (x0, y0, x1, y1) PDF 页面坐标，指定则只裁该区域
      zoom: 渲染缩放（2.0 = 2x，区域裁切更清晰）
    返回: (ok, out_path, err)
    """
    try:
        import fitz
    except ImportError as e:
        return False, None, f"fitz 不可用: {e}"
    try:
        doc = fitz.open(pdf_path)
        if page_idx < 0 or page_idx >= doc.page_count:
            total = doc.page_count  # 先取值再关，避免关闭后访问
            doc.close()
            return False, None, f"页码越界: {page_idx}（共 {total} 页）"
        page = doc[page_idx]
        if out_path is None:
            out_path = os.path.join(tempfile.gettempdir(),
                                    f"qa_render_p{page_idx}.png")
        mat = fitz.Matrix(zoom, zoom)
        if bbox:
            pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(*bbox))
        else:
            pix = page.get_pixmap(matrix=mat)
        pix.save(out_path)
        doc.close()
        return True, out_path, None
    except Exception as e:
        try:
            doc.close()
        except Exception:
            pass
        return False, None, str(e)


def analyze_image(image_path, prompt, backend="parallel", timeout=180):
    """调 vision_analyzer.py 分析图片。

    参数:
      image_path: 图片路径（png/jpg 等）
      prompt: 视觉提示词
      backend: parallel(双视觉) | qwen | glm | gemini | openai
    返回: (ok, result, err)
      result: parallel 模式为 {"qwen3_vl_flash":..., "glm_4_6v_flashx":...}
    """
    if not os.path.exists(image_path):
        return False, None, f"图片不存在: {image_path}"
    if not os.path.exists(VISION_ANALYZER):
        print("  [提示] 找不到 vision_analyzer.py，请设置环境变量 "
              "DTM_VISION_ANALYZER=/path/to/vision_analyzer.py（L3 视觉质检必需）")
        return False, None, f"vision_analyzer 不存在: {VISION_ANALYZER}"
    cmd = [sys.executable, VISION_ANALYZER, image_path, prompt, backend]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, None, f"vision_analyzer 超时(>{timeout}s)"
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        return False, None, f"vision_analyzer 退出码 {r.returncode}: {(r.stderr or '')[:200]}"
    try:
        d = json.loads(out)
        return True, d, None
    except json.JSONDecodeError:
        return True, {"text": out}, None
