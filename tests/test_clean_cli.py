"""test_clean_cli.py — CLI `dtmd clean` 穷举测试（S2：边界 + 防呆 + 终点一致性）。

覆盖：无参数 / 清洗单目录 / 目录不存在 / dry-run 不写回 / recursive 嵌套 /
多目录混合 / 传入文件路径（非目录）等异常路径。
"""
import json
import os
import subprocess
import sys

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))


def _run_cli(*args):
    """真实跑 `python -m dtmd clean ...`，返回 (returncode, stdout, stderr)。"""
    env = dict(os.environ, PYTHONPATH=SRC)
    p = subprocess.run([sys.executable, "-m", "dtmd", "clean", *args],
                       capture_output=True, text=True, encoding="utf-8",
                       env=env, timeout=120)
    return p.returncode, p.stdout, p.stderr


def _mk_case(tmp_path, name="out", cl=True, md="欢迎加入QQ群123456\n正文\n"):
    """构造一个转写目录（full.md + content_list，header 型水印）。"""
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "full.md").write_text(md, encoding="utf-8")
    if cl:
        (d / "abc_content_list.json").write_text(json.dumps([
            {"type": "header", "text": "欢迎加入QQ群123456",
             "bbox": [0, 0, 0, 0], "page_idx": i} for i in range(5)
        ]), encoding="utf-8")
    return d


class TestCleanCLI:
    def test_无参数_提示并退出1(self):
        rc, out, _ = _run_cli()
        assert rc == 1
        assert "未指定目录" in out

    def test_清洗单目录_水印清除(self, tmp_path):
        d = _mk_case(tmp_path)
        rc, out, _ = _run_cli(str(d))
        assert rc == 0
        assert "清洗 1" in out
        assert "QQ群" not in (d / "full.md").read_text(encoding="utf-8")
        assert "正文" in (d / "full.md").read_text(encoding="utf-8")

    def test_目录不存在_跳过不失败(self):
        rc, out, _ = _run_cli(r"C:\不存在的目录_xyz_2026")
        assert rc == 0
        assert "跳过 1" in out

    def test_dry_run_不写回(self, tmp_path):
        d = _mk_case(tmp_path)
        md_orig = (d / "full.md").read_text(encoding="utf-8")
        rc, out, _ = _run_cli("--dry-run", str(d))
        assert rc == 0
        assert "预演" in out
        assert (d / "full.md").read_text(encoding="utf-8") == md_orig  # 未写回

    def test_recursive_多目录(self, tmp_path):
        a = _mk_case(tmp_path, name="a_mineru")
        b = _mk_case(tmp_path, name="a_mineru", md="欢迎加入QQ群123456\n第二正文\n")
        # 构造嵌套：a_mineru 是目录名，但需要两个不同目录
        import shutil
        b = tmp_path / "b_mineru"
        shutil.copytree(str(a), str(b))
        (b / "full.md").write_text("欢迎加入QQ群123456\n嵌套正文\n", encoding="utf-8")
        rc, out, _ = _run_cli("--recursive", str(tmp_path))
        assert rc == 0
        assert "清洗 2" in out
        assert "QQ群" not in (a / "full.md").read_text(encoding="utf-8")
        assert "QQ群" not in (b / "full.md").read_text(encoding="utf-8")

    def test_混合_有content和无content(self, tmp_path):
        d1 = _mk_case(tmp_path, name="has_cl")       # 有 content_list → 清洗
        d2 = _mk_case(tmp_path, name="no_cl", cl=False)  # 无 content_list → 跳过
        rc, out, _ = _run_cli(str(d1), str(d2))
        assert rc == 0
        assert "清洗 1" in out and "跳过 1" in out

    def test_传入文件路径_不崩(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        rc, out, _ = _run_cli(str(f))
        assert rc == 0  # 非目录 → skipped（find_content_list 对文件返回 None）
        assert "跳过" in out
