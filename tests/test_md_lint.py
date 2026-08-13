"""T1 md_lint 测试 — Markdown 语法门禁。

验证 md_lint 能正确判定：正常文档通过、坏表格/未闭合代码块/空文件/乱码被标记。
"""
import os
import sys
import tempfile

PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJ, "src"))

from dtmd.quality.gates.md_lint import md_lint


def _write(tmp, name, content):
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


def test_normal_md_passes():
    """正常文档（含表格+代码块）应通过。"""
    with tempfile.TemporaryDirectory() as tmp:
        md = _write(tmp, "normal.md", """# 标题

正文内容，足够长避免太小警告。这是第二行用来凑字数。

| 名称 | 数值 |
|---|---|
| A | 1 |
| B | 2 |

```python
print("hi")
```
""")
        ok, issues = md_lint(md)
        assert ok is True, f"正常文档应通过，但 issues={issues}"


def test_bad_table_detected():
    """列数不一致的表格应被标记。"""
    with tempfile.TemporaryDirectory() as tmp:
        md = _write(tmp, "bad.md", """# 标题

正文内容足够长避免太小警告，用来凑字数防止误报。

| 名称 | 数值 |
|---|---|
| A | 1 |
| B | 2 | 3 |

表格列数不一致。
""")
        ok, issues = md_lint(md)
        assert ok is False, "坏表格应被标记"
        assert any("表格" in i for i in issues), f"应提示表格问题: {issues}"


def test_unclosed_code_detected():
    """未闭合代码块应被标记（围栏奇数）。"""
    with tempfile.TemporaryDirectory() as tmp:
        md = _write(tmp, "code.md", """# 标题

正文内容足够长避免太小警告，用来凑字数防止误报。

```python
print("hi")
""")
        ok, issues = md_lint(md)
        assert ok is False, "未闭合代码块应被标记"
        assert any("围栏" in i for i in issues), f"应提示围栏问题: {issues}"


def test_empty_file_detected():
    """空文件应被标记。"""
    with tempfile.TemporaryDirectory() as tmp:
        md = _write(tmp, "empty.md", "")
        ok, issues = md_lint(md)
        assert ok is False, "空文件应被标记"


def test_missing_file_detected():
    """不存在的文件应返回错误。"""
    ok, issues = md_lint("/nonexistent/path.md")
    assert ok is False, "缺失文件应返回失败"


def test_plain_text_passes():
    """纯文本（无表格无代码块）应通过。"""
    with tempfile.TemporaryDirectory() as tmp:
        md = _write(tmp, "plain.md", "# 标题\n\n" + "纯文本内容。" * 50)
        ok, issues = md_lint(md)
        assert ok is True, f"纯文本应通过，但 issues={issues}"


if __name__ == "__main__":
    for fn in [test_normal_md_passes, test_bad_table_detected,
               test_unclosed_code_detected, test_empty_file_detected,
               test_missing_file_detected, test_plain_text_passes]:
        try:
            fn()
            print(f"  ✅ {fn.__name__}")
        except AssertionError as e:
            print(f"  ❌ {fn.__name__}: {e}")
