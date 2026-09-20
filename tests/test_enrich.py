"""test_enrich.py — 插图融合穷举测试（S2：路径 + 边界 + 终点一致性）。

覆盖：
- enrich_image 单图：断点跳过 / OCR-only / GLM 降级 / 空图
- enrich_dir 整本：多图 / 无图 / 切片子目录
- embed_notes 内嵌：引用替换 / 无笔记保留 / 切片子目录跨找 / dry-run
- 向导：_ask 默认 / 非交互 EOF / 统计询问 / cleanup 清单+护栏+取消
- CLI：enrich/cleanup 注册 + dry-run + 用法提示
（GLM/OCR 全 mock，不出网、不花钱）
"""
import io
import json
import os
import sys
import subprocess

import pytest

from dtmd.convert import enrich
from dtmd.convert import enrich_wizard as wiz

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))


def _run_dtmd(*args):
    env = dict(os.environ, PYTHONPATH=SRC)
    p = subprocess.run([sys.executable, "-m", "dtmd", *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=120,
                       input="\n")  # 回车=默认（非交互防挂）
    return p.returncode, p.stdout, p.stderr


def _mk_mineru(tmp_path, name="book_mineru", n_imgs=3, sliced=False):
    """构造 _mineru/：full.md + images/若干图 + 可选切片结构。返回 (root, images_dir)。

    图片名 a.jpg/b.jpg/...（n_imgs≤3）与 full.md 引用一一对应（embed 找同名笔记）。
    """
    root = tmp_path / name
    imgs = root / "images"
    imgs.mkdir(parents=True)
    names = ["a.jpg", "b.jpg", "c.jpg"]
    if sliced:
        sub = root / "p1-2"
        sub.mkdir()
        (sub / "full.md").write_text("正文 ![](images/pic.jpg) 结尾", encoding="utf-8")
        # 切片场景：引用的图 pic.jpg 也在根 images/
        (imgs / "pic.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpg")
    (root / "full.md").write_text(
        "开头\n![](images/a.jpg)\n中间 ![](images/b.jpg)\n结尾", encoding="utf-8")
    for i in range(min(n_imgs, len(names))):
        (imgs / names[i]).write_bytes(b"\xff\xd8\xff\xe0fakejpg")
    return root, imgs


# ---------- enrich_image ----------

class TestEnrichImage:
    def test_ocr_only_creates_note(self, tmp_path, monkeypatch):
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        monkeypatch.delenv("GLM_API_KEY", raising=False)
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "图上文字")
        r = enrich.enrich_image(str(imgs), "img0.jpg", glm=False)
        assert r == "done"
        note = root / "images_notes" / "img0.md"
        assert note.exists() and "图上文字" in note.read_text(encoding="utf-8")

    def test_breakpoint_skip(self, tmp_path, monkeypatch):
        """已有非空笔记 → skipped（不重跑）"""
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        notes = root / "images_notes"
        notes.mkdir()
        (notes / "img0.md").write_text("旧内容", encoding="utf-8")
        calls = []
        monkeypatch.setattr(enrich, "ocr_image", lambda p: calls.append(p) or "x")
        r = enrich.enrich_image(str(imgs), "img0.jpg", glm=False)
        assert r == "skipped" and not calls  # OCR 都没跑

    def test_glm_text_written(self, tmp_path, monkeypatch):
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "ocr")
        monkeypatch.setattr(enrich, "glm_describe", lambda p, d=5, r=30: "glm描述")
        r = enrich.enrich_image(str(imgs), "img0.jpg", glm=True)
        assert r == "done"
        note = (root / "images_notes" / "img0.md").read_text(encoding="utf-8")
        assert "GLM 画面理解" in note and "glm描述" in note

    def test_empty_image_marked(self, tmp_path, monkeypatch):
        """OCR 无文字 + 无 GLM → empty"""
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "")
        r = enrich.enrich_image(str(imgs), "img0.jpg", glm=False)
        assert r == "empty"


# ---------- enrich_dir ----------

class TestEnrichDir:
    def test_multi_images(self, tmp_path, monkeypatch):
        root, imgs = _mk_mineru(tmp_path, n_imgs=3)
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "t")
        s = enrich.enrich_dir(str(root), glm=False, verbose=False)
        assert s["total"] == 3 and s["done"] == 3 and s["skipped"] == 0

    def test_no_images(self, tmp_path):
        root = tmp_path / "empty_mineru"
        root.mkdir()
        (root / "full.md").write_text("纯文字", encoding="utf-8")
        s = enrich.enrich_dir(str(root), glm=False, verbose=False)
        assert s["total"] == 0 and not s["dirs"]

    def test_resume_mixed(self, tmp_path, monkeypatch):
        """b.jpg 已有笔记 → 2 done + 1 skipped"""
        root, imgs = _mk_mineru(tmp_path, n_imgs=3)
        notes = root / "images_notes"
        notes.mkdir()
        (notes / "b.md").write_text("已有", encoding="utf-8")
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "t")
        s = enrich.enrich_dir(str(root), glm=False, verbose=False)
        assert s["done"] == 2 and s["skipped"] == 1


# ---------- embed_notes ----------

class TestEmbedNotes:
    def test_embed_replaces_refs(self, tmp_path, monkeypatch):
        root, imgs = _mk_mineru(tmp_path, n_imgs=2)
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "文字X")
        enrich.enrich_dir(str(root), glm=False, verbose=False)
        e = enrich.embed_notes(str(root))
        assert e["files"] == 1 and e["embedded"] == 2 and e["missing"] == 0
        md = (root / "full.md").read_text(encoding="utf-8")
        assert "![](images/a.jpg)" not in md
        assert "## 插图笔记：a" in md and "文字X" in md

    def test_missing_note_keeps_ref(self, tmp_path):
        """无笔记的引用保留原样"""
        root, _imgs = _mk_mineru(tmp_path, n_imgs=0)
        (root / "full.md").write_text("文 ![](images/ghost.jpg) 尾", encoding="utf-8")
        e = enrich.embed_notes(str(root))
        assert e["missing"] == 1
        md = (root / "full.md").read_text(encoding="utf-8")
        assert "![](images/ghost.jpg)" in md

    def test_dry_run_no_write(self, tmp_path, monkeypatch):
        root, imgs = _mk_mineru(tmp_path, n_imgs=2)
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "t")
        enrich.enrich_dir(str(root), glm=False, verbose=False)
        orig = (root / "full.md").read_text(encoding="utf-8")
        e = enrich.embed_notes(str(root), dry_run=True)
        assert e["embedded"] == 2
        assert (root / "full.md").read_text(encoding="utf-8") == orig

    def test_sliced_subdir_finds_note(self, tmp_path, monkeypatch):
        """切片书：p1-2/full.md 引用根 images/ 的图，笔记在根 images_notes/ → 跨找成功。

        fixture 的根 full.md 也引用 a/b（有笔记）→ files=2（根 + p1-2 子块）。
        """
        root, imgs = _mk_mineru(tmp_path, sliced=True, n_imgs=2)
        monkeypatch.setattr(enrich, "ocr_image", lambda p: "切片图文字")
        enrich.enrich_dir(str(root), glm=False, verbose=False)
        e = enrich.embed_notes(str(root))
        assert e["files"] == 2  # 根 full.md + p1-2/full.md
        sub_md = (root / "p1-2" / "full.md").read_text(encoding="utf-8")
        assert "切片图文字" in sub_md
        assert "![](images/pic.jpg)" not in sub_md


# ---------- 向导 ----------

class TestWizard:
    def test_ask_default_no(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *_: "")  # 回车
        assert wiz.ask_enrich("single", {"books": 1, "images": 88}) is False

    def test_ask_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *_: "A")
        assert wiz.ask_enrich("single", {"books": 1, "images": 88}) is True

    def test_ask_eof_uses_default(self, monkeypatch):
        def boom(*a):
            raise EOFError
        monkeypatch.setattr("builtins.input", boom)
        assert wiz.ask_enrich("batch", {"books": 12, "images": 340}) is False

    def test_ask_invalid_then_valid(self, monkeypatch):
        answers = iter(["Z", "A"])
        monkeypatch.setattr("builtins.input", lambda *_: next(answers))
        assert wiz.ask_enrich("single", {"books": 1, "images": 3}) is True

    def test_ask_zero_images_no_prompt(self, monkeypatch, capsys):
        called = []
        monkeypatch.setattr("builtins.input", lambda *_: called.append(1) or "")
        assert wiz.ask_enrich("single", {"books": 1, "images": 0}) is False
        assert not called  # 没图根本不问

    def test_cleanup_cancel_default(self, tmp_path, monkeypatch, capsys):
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        monkeypatch.setattr("builtins.input", lambda *_: "")  # 回车=C 取消
        rc = wiz.run_cleanup_flow(str(root))
        assert rc == 1
        assert (root / "images").exists()  # 什么都没删

    def test_cleanup_guard_no_fullmd(self, tmp_path, monkeypatch):
        """notes 存在但 full.md 缺失 → 拒绝删"""
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        notes = root / "images_notes"; notes.mkdir()
        (notes / "x.md").write_text("n", encoding="utf-8")
        (root / "full.md").unlink()
        monkeypatch.setattr("builtins.input", lambda *_: "A")
        rc = wiz.run_cleanup_flow(str(root))
        assert rc == 1 and (root / "images").exists()

    def test_cleanup_images_only(self, tmp_path, monkeypatch):
        """选 B 只删图片类，json/pdf 保留（审核依据）"""
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        (root / "x_content_list.json").write_text("[]", encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda *_: "B")
        rc = wiz.run_cleanup_flow(str(root))
        assert rc == 0
        assert not (root / "images").exists()
        assert (root / "x_content_list.json").exists()  # json 保留

    def test_cleanup_all(self, tmp_path, monkeypatch):
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        (root / "x_content_list.json").write_text("[]", encoding="utf-8")
        (root / "x_origin.pdf").write_bytes(b"%PDF")
        monkeypatch.setattr("builtins.input", lambda *_: "A")
        rc = wiz.run_cleanup_flow(str(root))
        assert rc == 0
        assert not (root / "images").exists()
        assert not (root / "x_content_list.json").exists()
        assert (root / "full.md").exists()  # full.md 永远保留


# ---------- CLI ----------

class TestEnrichCLI:
    def test_enrich_registered(self):
        sys.path.insert(0, SRC)
        from dtmd.cli import COMMANDS
        assert "enrich" in COMMANDS and "cleanup" in COMMANDS

    def test_enrich_no_args(self):
        rc, out, _ = _run_dtmd("enrich")
        assert rc == 1 and "用法" in out

    def test_enrich_dry_run(self, tmp_path):
        root, imgs = _mk_mineru(tmp_path, n_imgs=2)
        rc, out, _ = _run_dtmd("enrich", str(root), "--dry-run")
        assert rc == 0 and "2 张" in out
        assert not (root / "images_notes").exists()  # 没执行

    def test_enrich_decline_default(self, tmp_path):
        """回车=拒绝 → 不创建 notes"""
        root, imgs = _mk_mineru(tmp_path, n_imgs=2)
        rc, out, _ = _run_dtmd("enrich", str(root))
        assert rc == 0
        assert not (root / "images_notes").exists()

    def test_cleanup_preview_then_cancel(self, tmp_path):
        root, imgs = _mk_mineru(tmp_path, n_imgs=1)
        (root / "a_model.json").write_text("{}", encoding="utf-8")
        rc, out, _ = _run_dtmd("cleanup", str(root))
        assert rc == 1  # 取消
        assert (root / "a_model.json").exists()
        assert "full.md" in out  # 预览里说明 full.md 保留
