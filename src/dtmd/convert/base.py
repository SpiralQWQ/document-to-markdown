"""dtmd.convert.base — 转换域公共能力（切片 / 完成判断 / 智能切片 / 合并）。

本地/云端两条管线共用。HTTP 上传（云端专属）在 cloud.py，MinerU CLI 调用（本地专属）在 local.py。

MinerU API 限额（精准解析 API）：
    - 单文件页数上限：200 页（超出必须切片，由本模块 make_slice 处理）
    - 单文件大小上限：200 MB
    - 每日文件数上限：约 5000 个（错误码 -60018）
    - 每日高优额度：1000 页，超额降级排队
"""
import os
import re

from dtmd.utils import safe
from dtmd import config

MAX_PAGES_PER_FILE = 200  # MinerU API 单文件页数上限


def make_slice(block, idx):
    """生成上传文件：PDF 切片成独立小 PDF；PPT/DOC 用原文件。返回 tmp 路径。

    从原 converter/mineru_day.py 收敛（converter 迁移后统一用此份）。
    """
    if not os.path.exists(block["file"]):
        raise FileNotFoundError(f"源文件不存在: {block['file']}")
    if block["kind"] == "PDF":
        fn = safe(os.path.splitext(os.path.basename(block["file"]))[0])
        tmp = os.path.join(config.SLICE_DIR,
                           f"d{idx:03d}_{fn}_p{block['start']}-{block['end']}.pdf")
        if not os.path.exists(tmp):
            import fitz
            src = fitz.open(block["file"])
            out = fitz.open()
            out.insert_pdf(src, from_page=block["start"] - 1, to_page=block["end"] - 1)
            out.save(tmp)
            out.close()
            src.close()
        return tmp
    return block["file"]  # PPT / DOC / 单块整文件


def is_done(out_dir):
    """输出目录已有 full.md 或任意 json → 视为已完成（本地/云端统一判断）。"""
    if not os.path.isdir(out_dir):
        return False
    return os.path.exists(os.path.join(out_dir, "full.md")) or any(
        f.lower().endswith(".json") for f in os.listdir(out_dir))


def compute_out_dir(block, file_counts):
    """计算块的输出目录（单块→根目录，多块→p{start}-{end} 子目录）。

    默认输出到源文件旁 {源目录}/{basename}_mineru。
    若配置 DTM_OUTPUT_ROOT：输出到 {OUTPUT_ROOT}/{src_rel_dir}/{basename}_mineru
    （镜像源目录结构，不污染源目录；src_rel_dir 由 plan 生成时写入块）。
    """
    from dtmd import config as _cfg
    base = safe(os.path.splitext(os.path.basename(block["file"]))[0])
    if _cfg.OUTPUT_ROOT:
        rel_dir = block.get("src_rel_dir", "")
        out_root = os.path.join(_cfg.OUTPUT_ROOT, rel_dir, base + "_mineru")
    else:
        orig_dir = os.path.dirname(block["file"])
        out_root = os.path.join(orig_dir, base + "_mineru")
    multi = file_counts.get(block["file"], 1) > 1
    return os.path.join(out_root, f"p{block['start']}-{block['end']}") if multi else out_root


# ═══════════════════════════════════════════════════════════════
# 智能切片（plan 生成用）
# ═══════════════════════════════════════════════════════════════

def smart_slice(fp, pages, max_pages=MAX_PAGES_PER_FILE):
    """智能切片：按优先级尝试 TOC → 字体检测 → 硬切，返回块列表。

    每块 ≤ max_pages 页，优先在章节/标题边界断开，避免内容断连。

    Args:
        fp: PDF 文件路径
        pages: 总页数
        max_pages: 每块最大页数（默认 200，MinerU API 限制）

    Returns:
        [{"file": fp, "kind": "PDF", "start": s, "end": e, "pages": n}, ...]
    """
    if pages <= max_pages:
        return [{"file": fp, "kind": "PDF", "start": 1, "end": pages, "pages": pages}]

    import fitz
    doc = fitz.open(fp)

    # 1) 尝试 TOC（目录）：只取一级标题（章/篇），避免节/小节导致切片过碎
    toc = doc.get_toc()
    if toc:
        chapter_pages = sorted(set(t[2] for t in toc if t[0] == 1))
        # 如果一级标题太少（<2 个），放宽到二级
        if len(chapter_pages) < 2:
            chapter_pages = sorted(set(t[2] for t in toc if t[0] <= 2))
        blocks = _slice_by_page_list(fp, pages, chapter_pages, max_pages)
        if blocks:
            doc.close()
            return blocks

    # 2) 尝试字体大小检测（大字号 → 标题）
    heading_pages = _detect_heading_pages(doc, max_pages)
    doc.close()
    if heading_pages:
        blocks = _slice_by_page_list(fp, pages, heading_pages, max_pages)
        if blocks:
            return blocks

    # 3) 硬切（兜底）
    return _slice_hard(fp, pages, max_pages)


def _slice_by_page_list(fp, total_pages, break_candidates, max_pages):
    """按候选断点列表切片：每块 ≤ max_pages，优先在候选断点处断开。

    Args:
        fp: 文件路径
        total_pages: 总页数
        break_candidates: 候选断点页码列表（章节/标题起始页）
        max_pages: 每块最大页数

    Returns:
        块列表，或 None（候选断点不够时）
    """
    candidates = sorted(set(p for p in break_candidates if 1 < p <= total_pages))
    if not candidates:
        return None

    blocks = []
    current_start = 1
    while current_start <= total_pages:
        window_end = current_start + max_pages - 1
        if window_end >= total_pages:
            # 最后一块
            blocks.append({"file": fp, "kind": "PDF",
                           "start": current_start, "end": total_pages,
                           "pages": total_pages - current_start + 1})
            break
        # 在窗口内找最接近的候选断点（不超过 window_end）
        valid = [p for p in candidates if current_start < p <= window_end]
        if valid:
            split_at = max(valid)  # 最远的有效断点
        else:
            split_at = window_end  # 窗口内无候选 → 硬切
        blocks.append({"file": fp, "kind": "PDF",
                       "start": current_start, "end": split_at - 1,
                       "pages": split_at - current_start})
        current_start = split_at
    return blocks


def _detect_heading_pages(doc, max_pages):
    """通过字体大小检测章节标题位置，返回候选断点页码列表。

    扫描每页的文字块，找出大字号（>20pt 且比该页平均字号大 1.5 倍）的文本
    所在页码，作为候选断点。只扫描前几页 + 每段窗口边界附近，避免全量扫描。
    """
    heading_pages = set()
    total = doc.page_count

    # 全量扫描：真实章节标题散布全书各处，只扫边界会漏掉中间标题 → 退化成硬切（内容断连）。
    # 性能权衡：plan 阶段一次性，每页 get_text 约 5-20ms，数百页可接受。
    scan_pages = range(total)

    for page_num in sorted(scan_pages):
        page = doc[page_num]
        try:
            blocks = page.get_text("dict")["blocks"]
        except Exception:
            continue
        sizes = []
        for block in blocks:
            if block.get("type") != 0:  # 非文字块
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(span["size"])
        if len(sizes) < 3:  # 字符太少（如纯标题页）无法算基线 → 跳过
            continue
        # 基线用中位数：比均值抗干扰（少数大字号不会拉高基线）
        sizes_sorted = sorted(sizes)
        mid = len(sizes_sorted) // 2
        baseline = sizes_sorted[mid]
        # 大字号：> 20pt 且 > 基线（中位数）的 1.5 倍
        max_size = max(sizes)
        if max_size > 20 and max_size > baseline * 1.5:
            heading_pages.add(page_num + 1)  # 转为 1-indexed

    return sorted(heading_pages)


def _slice_hard(fp, total_pages, max_pages):
    """硬切：超出 max_pages 的 PDF 按 max_pages 均分。"""
    blocks = []
    for s in range(1, total_pages + 1, max_pages):
        e = min(s + max_pages - 1, total_pages)
        blocks.append({"file": fp, "kind": "PDF",
                       "start": s, "end": e, "pages": e - s + 1})
    return blocks


# ═══════════════════════════════════════════════════════════════
# 合并切片输出（转写后调用）
# ═══════════════════════════════════════════════════════════════

def merge_mineru_dir(out_dir, dry_run=False):
    """合并 _mineru/ 目录下所有切片 full.md，按页码顺序写入根目录 full.md。

    查找 p{start}-{end}/full.md → 按 start 排序 → 拼接 → 写入 {out_dir}/full.md。

    Args:
        out_dir: _mineru/ 输出目录
        dry_run: 只预览不写回

    Returns:
        {"ok": bool, "merged": int, "output": str, "error": str}
    """
    result = {"ok": False, "merged": 0, "output": "", "error": ""}

    if not os.path.isdir(out_dir):
        result["error"] = f"目录不存在: {out_dir}"
        return result

    # 查找所有 p{start}-{end}/full.md
    pattern = re.compile(r"^p(\d+)-\d+$")
    slices = []
    for entry in os.listdir(out_dir):
        m = pattern.match(entry)
        if not m:
            continue
        sub = os.path.join(out_dir, entry, "full.md")
        if os.path.isfile(sub):
            slices.append((int(m.group(1)), sub))

    if not slices:
        result["error"] = "未找到切片 full.md"
        return result

    slices.sort(key=lambda x: x[0])  # 按起始页排序
    merged_lines = []
    merged_count = 0

    for start, path in slices:
        if dry_run:
            merged_count += 1
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            merged_lines.append(content)
            merged_count += 1
        except OSError as e:
            result["error"] = f"读取失败 {path}: {e}"
            return result

    if dry_run:
        result["ok"] = True
        result["merged"] = merged_count
        result["output"] = os.path.join(out_dir, "full.md")
        return result

    # 写入合并后的 full.md
    merged_text = "\n\n".join(merged_lines)
    out_path = os.path.join(out_dir, "full.md")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged_text)
    except OSError as e:
        result["error"] = f"写入失败 {out_path}: {e}"
        return result

    result["ok"] = True
    result["merged"] = merged_count
    result["output"] = out_path
    return result
