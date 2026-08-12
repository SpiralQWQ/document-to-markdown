"""T5 export_md 测试 — 多格式导出。

验证 export_md 能：支持格式判定、文件缺失处理、不支持格式报错。
（实际 Pandoc 导出依赖系统装了 Pandoc，未装时跳过。）
"""
import os
import sys
import tempfile

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJ)

from export.export_md import export_md, SUPPORTED


def test_supported_formats():
    """支持的格式应包含 docx/html/epub/pptx/pdf。"""
    assert {"docx", "html", "epub", "pptx", "pdf"} <= set(SUPPORTED)


def test_missing_md():
    """不存在的 md 应返回失败。"""
    ok, _, err = export_md("/nonexistent/full.md", "docx")
    assert ok is False
    assert "不存在" in err


def test_unsupported_format():
    """不支持的格式应报错。"""
    with tempfile.TemporaryDirectory() as tmp:
        md = os.path.join(tmp, "full.md")
        open(md, "w", encoding="utf-8").write("# 标题\n\n正文" * 30)
        ok, _, err = export_md(md, "xyz")
        assert ok is False
        assert "不支持" in err


if __name__ == "__main__":
    for fn in [test_supported_formats, test_missing_md, test_unsupported_format]:
        try:
            fn()
            print(f"  ✅ {fn.__name__}")
        except AssertionError as e:
            print(f"  ❌ {fn.__name__}: {e}")
