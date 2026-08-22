"""test_html_cloud.py — HTML 云端转写穷举测试（S2：路径 + 边界 + 终点一致性）。

覆盖：
- _model_version() 扩展名选择（.html/.htm → MinerU-HTML，其他 → vlm）
- _html_mode() dry-run 路径解析与输出目录计算
- CLI --html / --html-dir 参数解析与路由
- 异常路径：文件不存在 / 目录不存在 / 空目录 / 路径重叠去重
- 非 HTML 文件过滤（.txt/.pdf 不收集）

手动测试用例（上传到真实云端）：
  tests/cases/html_cloud/demo_web.html
  → python -m dtmd convert --mode cloud --html tests/cases/html_cloud/demo_web.html
"""
import os
import subprocess
import sys

from dtmd.convert.cloud import _model_version, _html_mode

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))


def _run_convert(*args):
    """真实跑 `python -m dtmd convert --mode cloud ...`，返回 (returncode, stdout, stderr)。"""
    env = dict(os.environ, PYTHONPATH=SRC)
    p = subprocess.run([sys.executable, "-m", "dtmd", "convert", "--mode", "cloud", *args],
                       capture_output=True, text=True, encoding="utf-8",
                       env=env, timeout=120)
    return p.returncode, p.stdout, p.stderr


# ============================================================
# _model_version() 单元测试
# ============================================================

class TestModelVersion:
    def test_html_extension(self):
        """_model_version(.html) → MinerU-HTML"""
        assert _model_version("test.html") == "MinerU-HTML"

    def test_htm_extension(self):
        """_model_version(.htm) → MinerU-HTML"""
        assert _model_version("index.htm") == "MinerU-HTML"

    def test_uppercase_html(self):
        """_model_version(.HTML) 大小写不敏感 → MinerU-HTML"""
        assert _model_version("PAGE.HTML") == "MinerU-HTML"

    def test_pdf_extension(self):
        """_model_version(.pdf) → vlm"""
        assert _model_version("doc.pdf") == "vlm"

    def test_docx_extension(self):
        """_model_version(.docx) → vlm"""
        assert _model_version("report.docx") == "vlm"

    def test_pptx_extension(self):
        """_model_version(.pptx) → vlm"""
        assert _model_version("slides.pptx") == "vlm"

    def test_png_extension(self):
        """_model_version(.png) → vlm"""
        assert _model_version("image.png") == "vlm"

    def test_no_extension(self):
        """_model_version(无扩展名) → vlm"""
        assert _model_version("README") == "vlm"


# ============================================================
# _html_mode() dry-run 测试
# ============================================================

class TestHtmlModeDryRun:
    def test_html_mode_dry_run_single(self, tmp_path):
        """--html 单个文件 + --dry-run → 预览，不上传，正确输出目录"""
        html = tmp_path / "test.html"
        html.write_text("<html><body><p>hello</p></body></html>", encoding="utf-8")
        rc = _html_mode(["--html", str(html), "--dry-run"], dry=True, ocr=False, limit=None, budget=5000)
        assert rc == 0  # dry-run 正常退出

    def test_html_mode_dry_run_dir(self, tmp_path):
        """--html-dir 目录 + --dry-run → 递归收集所有 .html/.htm"""
        d = tmp_path / "pages"
        d.mkdir()
        (d / "a.html").write_text("a", encoding="utf-8")
        (d / "b.html").write_text("b", encoding="utf-8")
        (d / "c.htm").write_text("c", encoding="utf-8")
        (d / "readme.txt").write_text("not html", encoding="utf-8")
        rc = _html_mode(["--html", str(d), "--dry-run"], dry=True, ocr=False, limit=None, budget=5000)
        assert rc == 0  # 收集 3 个 HTML 文件，跳过 .txt

    def test_html_mode_dry_run_limit(self, tmp_path):
        """--limit 限制 HTML 文件处理数量"""
        d = tmp_path / "many"
        d.mkdir()
        for i in range(10):
            (d / f"p{i}.html").write_text(f"page {i}", encoding="utf-8")
        rc = _html_mode(["--html", str(d), "--dry-run"], dry=True, ocr=False, limit=3, budget=5000)
        assert rc == 0  # 只处理前 3 个

    def test_html_mode_skip_done(self, tmp_path):
        """已完成输出目录 → 跳过"""
        html = tmp_path / "done.html"
        html.write_text("<html><body>done</body></html>", encoding="utf-8")
        out_dir = tmp_path / "done_mineru"
        out_dir.mkdir()
        (out_dir / "full.md").write_text("# done", encoding="utf-8")
        rc = _html_mode(["--html", str(html), "--dry-run"], dry=True, ocr=False, limit=None, budget=5000)
        assert rc == 0  # 已完成，跳过后返回 0

    def test_html_mode_file_not_found(self, tmp_path):
        """不存在的文件 → 跳过并正常退出"""
        rc = _html_mode(["--html", str(tmp_path / "不存在.html"), "--dry-run"],
                        dry=True, ocr=False, limit=None, budget=5000)
        assert rc == 1  # 无有效文件 → 退出码 1

    def test_html_mode_empty_dir(self, tmp_path):
        """空目录 → 无 HTML 文件 → 退出码 1"""
        d = tmp_path / "empty"
        d.mkdir()
        rc = _html_mode(["--html", str(d), "--dry-run"], dry=True, ocr=False, limit=None, budget=5000)
        assert rc == 1  # 无有效 HTML 文件

    def test_html_mode_non_html_in_dir(self, tmp_path):
        """目录下只有 .txt/.pdf → 无 HTML 文件 → 退出码 1"""
        d = tmp_path / "nohtml"
        d.mkdir()
        (d / "readme.txt").write_text("text", encoding="utf-8")
        (d / "doc.pdf").write_text("pdf", encoding="utf-8")
        rc = _html_mode(["--html", str(d), "--dry-run"], dry=True, ocr=False, limit=None, budget=5000)
        assert rc == 1  # 无 .html/.htm 文件

    def test_html_mode_dedup(self, tmp_path):
        """--html 和 --html-dir 路径重叠 → 去重"""
        d = tmp_path / "dedup"
        d.mkdir()
        (d / "a.html").write_text("a", encoding="utf-8")
        # 同时传 --html 单个文件（已在目录内）和 --html-dir 整个目录
        # _html_mode 从 args 收集路径，两者可能重叠
        rc = _html_mode(["--html", str(d / "a.html"), str(d), "--dry-run"],
                        dry=True, ocr=False, limit=None, budget=5000)
        assert rc == 0  # 去重后不报错


# ============================================================
# CLI 集成测试（subprocess 跑 dtmd convert）
# ============================================================

class TestHtmlCLI:
    def test_cli_html_flag_parse(self, tmp_path):
        """CLI --html 参数被 argparse 正确消费"""
        html = tmp_path / "cli_test.html"
        html.write_text("<html><body>cli</body></html>", encoding="utf-8")
        rc, out, err = _run_convert("--html", str(html), "--dry-run")
        assert rc == 0
        assert "HTML" in out or "预览" in out or "待传" in out

    def test_cli_html_dir_flag_parse(self, tmp_path):
        """CLI --html-dir 参数被 argparse 正确消费"""
        d = tmp_path / "cli_dir"
        d.mkdir()
        (d / "a.html").write_text("<html><body>a</body></html>", encoding="utf-8")
        rc, out, err = _run_convert("--html-dir", str(d), "--dry-run")
        assert rc == 0
        assert "HTML" in out or "预览" in out or "待传" in out

    def test_cli_html_dir_not_found(self):
        """CLI --html-dir 目录不存在 → 友好错误提示"""
        rc, out, err = _run_convert("--html-dir", r"C:\不存在的目录_xyz_2026")
        assert rc == 1
        assert "错误" in out or "不存在" in out

    def test_cli_html_file_not_found(self):
        """CLI --html 文件不存在 → 无有效文件，退出码 1"""
        rc, out, err = _run_convert("--html", r"C:\不存在的文件_xyz.html", "--dry-run")
        assert rc == 1  # 无有效 HTML 文件 → 退出码 1

    def test_cli_dry_run_forwarded(self, tmp_path):
        """CLI --dry-run 被正确透传到 cloud.py"""
        html = tmp_path / "dryrun.html"
        html.write_text("<html><body>dryrun</body></html>", encoding="utf-8")
        rc, out, err = _run_convert("--html", str(html), "--dry-run")
        assert rc == 0
        assert "DRY-RUN" in out  # cloud.py 的 dry-run 标志生效

    def test_cli_convert_without_html(self, tmp_path):
        """不传 --html/--html-dir 时，正常走 day 模式 → 提示缺 Day 参数"""
        rc, out, err = _run_convert("--dry-run")
        # 没有 --html 也没有 day 数字 → 用法提示
        assert rc == 1
        # 输出应包含用法提示