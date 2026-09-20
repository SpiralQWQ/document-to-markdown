"""test_merge_plan_cli.py — dtmd merge / dtmd plan 命令穷举测试。

覆盖：
- merge_mineru_dir：合并排序 / dry-run / 无切片 / 目录不存在 / 读取失败
- dtmd plan CLI：无参提示 / 单文件输入 / 目录扫描（PDF+Office）/ dry-run 不写
- plan 生成块含 src_rel_dir（镜像输出前置）
- 边界：空目录 / 非 PDF 混入 / 损坏 PDF 跳过
"""
import json
import os
import subprocess
import sys

import pytest

from dtmd.convert.base import merge_mineru_dir

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))


def _run_dtmd(*args):
    """真实跑 `python -m dtmd ...`，返回 (returncode, stdout, stderr)。"""
    env = dict(os.environ, PYTHONPATH=SRC)
    p = subprocess.run([sys.executable, "-m", "dtmd", *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=180)
    return p.returncode, p.stdout, p.stderr


def _mk_pdf(tmp_path, name, pages=3):
    import fitz
    fp = str(tmp_path / name)
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 300), "body", fontsize=11)
    doc.save(fp)
    doc.close()
    return fp


# ============================================================
# merge_mineru_dir 核心函数
# ============================================================

class TestMergeMineruDir:
    def _mk_slices(self, root, slices):
        """构造 p{start}-{end}/full.md 结构，内容含起始页标记。"""
        for s, e in slices:
            d = root / f"p{s}-{e}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "full.md").write_text(f"CONTENT_PAGE_{s}", encoding="utf-8")

    def test_merge_sorted_by_start_page(self, tmp_path):
        root = tmp_path / "book_mineru"
        # 故意乱序创建
        self._mk_slices(root, [(201, 376), (1, 200)])
        r = merge_mineru_dir(str(root))
        assert r["ok"] is True and r["merged"] == 2
        merged = (root / "full.md").read_text(encoding="utf-8")
        # 顺序必须是 p1 在前
        assert merged.index("CONTENT_PAGE_1") < merged.index("CONTENT_PAGE_201")

    def test_merge_dry_run_no_write(self, tmp_path):
        root = tmp_path / "book_mineru"
        self._mk_slices(root, [(1, 100), (101, 200)])
        r = merge_mineru_dir(str(root), dry_run=True)
        assert r["ok"] is True and r["merged"] == 2
        assert not (root / "full.md").exists()  # 未写回

    def test_merge_ignores_non_slice_dirs(self, tmp_path):
        """images/ 等非 p{} 目录被忽略"""
        root = tmp_path / "book_mineru"
        self._mk_slices(root, [(1, 50)])
        (root / "images").mkdir()
        (root / "images" / "full.md").write_text("noise", encoding="utf-8")
        r = merge_mineru_dir(str(root))
        assert r["ok"] is True and r["merged"] == 1

    def test_merge_no_slices(self, tmp_path):
        root = tmp_path / "empty_mineru"
        root.mkdir()
        r = merge_mineru_dir(str(root))
        assert r["ok"] is False and "未找到切片" in r["error"]

    def test_merge_dir_not_exist(self, tmp_path):
        r = merge_mineru_dir(str(tmp_path / "nope"))
        assert r["ok"] is False and "目录不存在" in r["error"]

    def test_merge_skip_dir_without_full_md(self, tmp_path):
        """p{} 子目录存在但缺 full.md → 只合并有 full.md 的"""
        root = tmp_path / "book_mineru"
        self._mk_slices(root, [(1, 100)])
        (root / "p101-200").mkdir()  # 无 full.md
        r = merge_mineru_dir(str(root))
        assert r["ok"] is True and r["merged"] == 1


# ============================================================
# dtmd plan CLI
# ============================================================

class TestPlanCLI:
    def test_plan_no_args_shows_usage(self):
        rc, out, _ = _run_dtmd("plan")
        assert rc == 1
        assert "用法" in out

    def test_plan_nonexistent_target(self):
        rc, out, _ = _run_dtmd("plan", "E:\\不存在的目录_xyz_2026")
        assert rc == 1
        assert "未找到文档" in out

    def test_plan_dry_run_single_pdf(self, tmp_path):
        fp = _mk_pdf(tmp_path, "single.pdf", 10)
        rc, out, _ = _run_dtmd("plan", fp, "--dry-run", "--out", str(tmp_path / "p.json"))
        assert rc == 0
        assert "1 块" in out
        assert not (tmp_path / "p.json").exists()  # dry-run 不写

    def test_plan_dry_run_dir_mixed(self, tmp_path):
        """目录扫描：PDF + Office 混合，均识别"""
        _mk_pdf(tmp_path, "a.pdf", 5)
        (tmp_path / "b.docx").write_bytes(b"PK\x03\x04fake")  # 假 docx（不读取页数）
        rc, out, _ = _run_dtmd("plan", str(tmp_path), "--dry-run",
                               "--out", str(tmp_path / "p.json"))
        assert rc == 0
        assert "Office" in out

    def test_plan_writes_plan_json(self, tmp_path):
        fp = _mk_pdf(tmp_path, "w.pdf", 7)
        out_json = tmp_path / "plan.json"
        rc, out, _ = _run_dtmd("plan", fp, "--out", str(out_json))
        assert rc == 0
        assert out_json.exists()
        plan = json.loads(out_json.read_text(encoding="utf-8"))
        assert "days_normal" in plan
        blk = plan["days_normal"][0]["blocks"][0]
        assert blk["file"].endswith("w.pdf")
        assert blk["pages"] == 7

    def test_plan_blocks_have_src_rel_dir(self, tmp_path):
        """镜像输出前置：块必须携带 src_rel_dir 字段"""
        sub = tmp_path / "repo1"; sub.mkdir()
        _mk_pdf(sub, "in_sub.pdf", 5)
        out_json = tmp_path / "plan.json"
        rc, _, _ = _run_dtmd("plan", str(tmp_path), "--out", str(out_json))
        assert rc == 0
        plan = json.loads(out_json.read_text(encoding="utf-8"))
        blk = plan["days_normal"][0]["blocks"][0]
        assert "src_rel_dir" in blk

    def test_plan_skips_broken_pdf(self, tmp_path):
        """损坏 PDF → 报「无法读取」跳过不崩"""
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"%PDF-1.4 broken content")
        rc, out, _ = _run_dtmd("plan", str(bad), "--dry-run",
                               "--out", str(tmp_path / "p.json"))
        # 损坏 PDF 走「无法读取」分支被跳过；单文件全跳过 → 未找到文档 → 退出 1
        assert rc == 1
        assert "无法读取" in out

    def test_plan_skips_mineru_dirs(self, tmp_path):
        """_mineru/ 内的 _origin.pdf 不被扫入（按文件名判断，避开 pytest tmp_path 含目录名的干扰）"""
        _mk_pdf(tmp_path, "real.pdf", 3)
        inner = tmp_path / "real_mineru"
        inner.mkdir()
        (inner / "xxx_origin.pdf").write_bytes(b"%PDF-1.4 fake")
        out_json = tmp_path / "plan.json"
        rc, _, _ = _run_dtmd("plan", str(tmp_path), "--out", str(out_json))
        assert rc == 0
        plan = json.loads(out_json.read_text(encoding="utf-8"))
        names = [os.path.basename(b["file"]) for d in plan["days_normal"] for b in d["blocks"]]
        assert all("origin" not in n.lower() for n in names)  # 中间产物被排除
        assert "real.pdf" in names

    def test_plan_budget_splits_days(self, tmp_path):
        """--budget 分天：单文件页数超过预算也至少排一天"""
        fp = _mk_pdf(tmp_path, "tiny.pdf", 3)
        out_json = tmp_path / "plan.json"
        rc, out, _ = _run_dtmd("plan", fp, "--budget", "2", "--out", str(out_json))
        assert rc == 0
        plan = json.loads(out_json.read_text(encoding="utf-8"))
        assert len(plan["days_normal"]) == 1  # 3页>预算2 但 day_blocks 空时仍排入

    def test_plan_backs_up_existing(self, tmp_path):
        """已有 plan → 自动备份 _bak_ 文件"""
        fp = _mk_pdf(tmp_path, "bk.pdf", 3)
        out_json = tmp_path / "plan.json"
        out_json.write_text("{}", encoding="utf-8")
        rc, out, _ = _run_dtmd("plan", fp, "--out", str(out_json))
        assert rc == 0
        bak = list(tmp_path.glob("plan_bak_*.json"))
        assert len(bak) == 1 and bak[0].read_text(encoding="utf-8") == "{}"


# ============================================================
# dtmd merge CLI
# ============================================================

class TestMergeCLI:
    def test_merge_no_targets_uses_cwd(self):
        """无参数 → 默认当前目录；仓库根下无含切片的 _mineru → 退出 1"""
        # 仓库根的 _mineru 输出目录不在 CWD 子树（在用户资料区），本测试环境无切片可合并
        rc, out, _ = _run_dtmd("merge", "--dry-run")
        assert rc in (0, 1)  # CWD 有可合并切片则 0，无则 1——两种都合法
        assert "合并" in out

    def test_merge_single_dir(self, tmp_path):
        root = tmp_path / "book_mineru"
        for s, e in [(1, 100), (101, 150)]:
            d = root / f"p{s}-{e}"; d.mkdir(parents=True)
            (d / "full.md").write_text(f"P{s}", encoding="utf-8")
        rc, out, _ = _run_dtmd("merge", str(root))
        assert rc == 0
        assert "合并 1" in out
        assert (root / "full.md").exists()

    def test_merge_dry_run(self, tmp_path):
        root = tmp_path / "book_mineru"
        d = root / "p1-100"; d.mkdir(parents=True)
        (d / "full.md").write_text("P1", encoding="utf-8")
        rc, out, _ = _run_dtmd("merge", str(root), "--dry-run")
        assert rc == 0 and "预演" in out
        assert not (root / "full.md").exists()

    def test_merge_recursive_finds_mineru_dirs(self, tmp_path):
        a = tmp_path / "a" / "x_mineru" / "p1-10"
        b = tmp_path / "b" / "y_mineru" / "p1-10"
        for d in (a, b):
            d.mkdir(parents=True)
            (d / "full.md").write_text("X", encoding="utf-8")
        rc, out, _ = _run_dtmd("merge", str(tmp_path), "--recursive")
        assert rc == 0 and "合并 2" in out

    def test_merge_dir_without_slices_skipped(self, tmp_path):
        root = tmp_path / "plain_mineru"
        root.mkdir()  # 无切片
        rc, out, _ = _run_dtmd("merge", str(root), "--verbose")
        assert rc == 1  # 全部跳过 → 未找到 _mineru 目录含切片
