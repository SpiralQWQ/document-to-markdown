"""test_smart_slice.py — 智能切片引擎穷举测试。

覆盖：
- smart_slice 三档路由（TOC → 字体检测 → 硬切）
- _slice_by_page_list 候选断点切片（窗口内最远断点 / 无候选硬切 / 空候选 None）
- _slice_hard 均分切片（整除 / 余数）
- compute_out_dir 镜像输出（DTM_OUTPUT_ROOT 设置 / 未设置）
- make_slice PDF 切片生成 / is_done 完成判断
"""
import os

import pytest

from dtmd import config
from dtmd.convert.base import (
    MAX_PAGES_PER_FILE,
    compute_out_dir,
    is_done,
    make_slice,
    smart_slice,
    _slice_by_page_list,
    _slice_hard,
)


# ---------- PDF fixture 工厂 ----------

def _mk_pdf(tmp_path, name, pages, toc=None, big_font_page=None):
    """用 fitz 生成测试 PDF。toc=[(1,'第1章',3),...]；big_font_page=页码（0 基）时该页画大字号文本。"""
    import fitz
    fp = str(tmp_path / name)
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        if big_font_page is not None and i == big_font_page:
            page.insert_text((72, 100), f"Chapter {i+1}", fontsize=28)
        # 画 3 行正文（≥3 span，满足检测器的基线要求）
        for row in range(3):
            page.insert_text((72, 250 + row * 20), f"page {i+1} body text line {row}", fontsize=11)
    if toc:
        doc.set_toc(toc)
    doc.save(fp)
    doc.close()
    return fp


# ---------- smart_slice 路由 ----------

class TestSmartSliceRoute:
    def test_small_pdf_single_block(self, tmp_path):
        """≤200 页 → 单块不切"""
        fp = _mk_pdf(tmp_path, "small.pdf", 150)
        blocks = smart_slice(fp, 150)
        assert blocks == [{"file": fp, "kind": "PDF", "start": 1, "end": 150, "pages": 150}]

    def test_exact_boundary_single_block(self, tmp_path):
        """恰好 200 页 → 单块（边界：不超限）"""
        fp = _mk_pdf(tmp_path, "exact.pdf", 200)
        blocks = smart_slice(fp, 200)
        assert len(blocks) == 1 and blocks[0]["pages"] == 200

    def test_no_toc_no_heading_hard_cut(self, tmp_path):
        """无 TOC 无大标题 → 硬切均分"""
        fp = _mk_pdf(tmp_path, "hard.pdf", 450)
        blocks = smart_slice(fp, 450)
        assert len(blocks) == 3
        assert [b["pages"] for b in blocks] == [200, 200, 50]
        assert blocks[0]["start"] == 1 and blocks[0]["end"] == 200
        assert blocks[2]["start"] == 401 and blocks[2]["end"] == 450

    def test_toc_routes_to_chapter_cut(self, tmp_path):
        """有 TOC → 按章节边界切（不硬切 200）"""
        fp = _mk_pdf(tmp_path, "toc.pdf", 300, toc=[(1, "ch1", 1), (1, "ch2", 150), (1, "ch3", 260)])
        blocks = smart_slice(fp, 300)
        # 窗口 1-200 内最远一级断点 150 → 第一块 p1-149；第二块从 150 起窗口 150-349≥300 → 收尾
        assert blocks[0]["end"] == 149
        assert blocks[1]["start"] == 150
        assert sum(b["pages"] for b in blocks) == 300  # 无缝覆盖
        assert all(b["pages"] <= MAX_PAGES_PER_FILE for b in blocks)

    def test_toc_level1_too_few_falls_to_level2(self, tmp_path):
        """一级标题 <2 → 放宽用二级标题"""
        fp = _mk_pdf(tmp_path, "lv2.pdf", 300,
                     toc=[(1, "only", 1), (2, "sec1", 120), (2, "sec2", 240)])
        blocks = smart_slice(fp, 300)
        assert blocks[0]["end"] == 119  # 用了二级断点 120
        assert sum(b["pages"] for b in blocks) == 300

    def test_no_toc_big_font_routes_to_heading(self, tmp_path):
        """无 TOC 但有大字号标题 → 字体检测切片"""
        fp = _mk_pdf(tmp_path, "font.pdf", 300, big_font_page=140)  # 第 141 页大标题
        blocks = smart_slice(fp, 300)
        # 窗口 1-200 内最远断点 141 → 第一块 p1-140
        assert blocks[0]["end"] == 140
        assert sum(b["pages"] for b in blocks) == 300


# ---------- _slice_by_page_list 纯函数 ----------

class TestSliceByPageList:
    FP = "fake.pdf"

    def test_empty_candidates_returns_none(self):
        assert _slice_by_page_list(self.FP, 300, [], 200) is None

    def test_candidates_at_page1_filtered(self):
        """候选全在 p1（1 < p 过滤）→ None"""
        assert _slice_by_page_list(self.FP, 300, [1, 1], 200) is None

    def test_candidates_beyond_total_filtered(self):
        """候选超总页数 → 过滤后空 → None"""
        assert _slice_by_page_list(self.FP, 100, [500, 600], 200) is None

    def test_farthest_candidate_in_window(self):
        """窗口内取最远有效断点（半开区间：断点页归下一块）"""
        blocks = _slice_by_page_list(self.FP, 400, [50, 150, 190, 250], 200)
        assert blocks[0]["end"] == 189  # 断点 190 归下一块
        assert blocks[1]["start"] == 190

    def test_window_without_candidate_hard_cuts(self):
        """窗口内无候选 → 硬切 window_end（半开：window_end 页归下块）"""
        blocks = _slice_by_page_list(self.FP, 400, [150], 200)
        # 第一窗口 1-200 有 150 → p1-149；第二窗口 150-349 无候选 → 硬切 p150-348；余 p349-400
        assert blocks[0]["end"] == 149
        assert blocks[1]["start"] == 150 and blocks[1]["end"] == 348
        assert blocks[2]["start"] == 349 and blocks[2]["end"] == 400
        assert sum(b["pages"] for b in blocks) == 400

    def test_seamless_coverage(self):
        """任意候选组合：块间无缝、无重叠、页数守恒"""
        blocks = _slice_by_page_list(self.FP, 500, [30, 180, 350], 200)
        total = sum(b["pages"] for b in blocks)
        assert total == 500
        for a, b in zip(blocks, blocks[1:]):
            assert b["start"] == a["end"] + 1

    def test_every_block_within_max(self):
        """任意候选：每块 ≤ max_pages"""
        blocks = _slice_by_page_list(self.FP, 600, [10, 20, 399, 401], 200)
        assert all(b["pages"] <= 200 for b in blocks)
        assert sum(b["pages"] for b in blocks) == 600


# ---------- _slice_hard ----------

class TestSliceHard:
    def test_even_split(self):
        blocks = _slice_hard("a.pdf", 400, 200)
        assert [(b["start"], b["end"]) for b in blocks] == [(1, 200), (201, 400)]

    def test_remainder_last_block(self):
        blocks = _slice_hard("a.pdf", 450, 200)
        assert blocks[-1]["pages"] == 50
        assert blocks[-1]["end"] == 450

    def test_single_page(self):
        assert _slice_hard("a.pdf", 1, 200) == [
            {"file": "a.pdf", "kind": "PDF", "start": 1, "end": 1, "pages": 1}]


# ---------- compute_out_dir 镜像输出 ----------

class TestComputeOutDir:
    BLK = {"file": r"E:\src\root\repo\sub\book.pdf", "kind": "PDF",
           "start": 1, "end": 100, "pages": 100}

    def test_default_output_beside_source(self, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_ROOT", "")
        out = compute_out_dir(self.BLK, {})
        assert out.endswith("book_mineru")
        assert r"E:\src\root\repo\sub" in out

    def test_mirror_output_when_root_set(self, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_ROOT", r"E:\out")
        blk = {**self.BLK, "src_rel_dir": os.path.join("repo", "sub")}
        out = compute_out_dir(blk, {})
        assert out.startswith(r"E:\out")
        assert "repo" in out and "sub" in out
        assert out.endswith("book_mineru")
        # 源目录不出现
        assert r"E:\src" not in out

    def test_mirror_no_src_rel_dir_flat(self, monkeypatch):
        """缺 src_rel_dir → 直接放 OUTPUT_ROOT 根"""
        monkeypatch.setattr(config, "OUTPUT_ROOT", r"E:\out")
        out = compute_out_dir(dict(self.BLK), {})
        assert out.startswith(r"E:\out") and out.endswith("book_mineru")

    def test_mirror_multi_block_subdir(self, monkeypatch):
        """多块 → OUTPUT_ROOT 下仍有 p{start}-{end} 子目录"""
        monkeypatch.setattr(config, "OUTPUT_ROOT", r"E:\out")
        blk = {**self.BLK, "src_rel_dir": "repo"}
        out = compute_out_dir(blk, {self.BLK["file"]: 2})
        assert f"p{self.BLK['start']}-{self.BLK['end']}" in out


# ---------- make_slice / is_done ----------

class TestMakeSliceAndIsDone:
    def test_make_slice_pdf_generates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "SLICE_DIR", str(tmp_path / "slices"))
        os.makedirs(str(tmp_path / "slices"), exist_ok=True)
        fp = _mk_pdf(tmp_path, "src.pdf", 300)
        blk = {"file": fp, "kind": "PDF", "start": 1, "end": 200, "pages": 200}
        tmp = make_slice(blk, 0)
        assert os.path.isfile(tmp)
        assert "p1-200" in os.path.basename(tmp)

    def test_make_slice_office_returns_original(self, tmp_path):
        """Office 文件返回原路径，但前提是文件存在（make_slice 先查存在性）"""
        fp = tmp_path / "doc.docx"
        fp.write_bytes(b"fake")
        blk = {"file": str(fp), "kind": "DOC", "start": 1, "end": 1, "pages": 1}
        assert make_slice(blk, 0) == str(fp)  # 不切片

    def test_make_slice_office_missing_source_raises(self):
        """Office 文件不存在 → FileNotFoundError（先查存在性再判 kind）"""
        with pytest.raises(FileNotFoundError):
            make_slice({"file": "不存在.docx", "kind": "DOC",
                        "start": 1, "end": 1, "pages": 1}, 0)

    def test_make_slice_missing_source_raises(self):
        with pytest.raises(FileNotFoundError):
            make_slice({"file": "不存在.pdf", "kind": "PDF",
                        "start": 1, "end": 1, "pages": 1}, 0)

    def test_is_done_with_full_md(self, tmp_path):
        d = tmp_path / "x_mineru"; d.mkdir()
        (d / "full.md").write_text("hi", encoding="utf-8")
        assert is_done(str(d)) is True

    def test_is_done_with_json_only(self, tmp_path):
        d = tmp_path / "y_mineru"; d.mkdir()
        (d / "a_content_list.json").write_text("[]", encoding="utf-8")
        assert is_done(str(d)) is True

    def test_is_done_empty_dir(self, tmp_path):
        d = tmp_path / "z_mineru"; d.mkdir()
        assert is_done(str(d)) is False

    def test_is_done_missing_dir(self, tmp_path):
        assert is_done(str(tmp_path / "nope")) is False
