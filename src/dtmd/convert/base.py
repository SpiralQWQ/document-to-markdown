"""dtmd.convert.base — 转换域公共能力（切片 / 完成判断）。

本地/云端两条管线共用。HTTP 上传（云端专属）在 cloud.py，MinerU CLI 调用（本地专属）在 local.py。
"""
import os

from dtmd.utils import safe
from dtmd import config


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
    """计算块的输出目录（单块→根目录，多块→p{start}-{end} 子目录）。"""
    orig_dir = os.path.dirname(block["file"])
    base = safe(os.path.splitext(os.path.basename(block["file"]))[0])
    out_root = os.path.join(orig_dir, base + "_mineru")
    multi = file_counts.get(block["file"], 1) > 1
    return os.path.join(out_root, f"p{block['start']}-{block['end']}") if multi else out_root
