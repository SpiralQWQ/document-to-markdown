#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md_lint.py — Markdown 语法门禁（mistune 3.x）

对 MinerU 输出的 full.md 做语法体检：
  1. 表格：能正确解析成 table 节点；"像表格但没解析成 table" → 列数不一致/格式损坏
  2. 代码块：能正确解析成 block_code；"像代码块但没解析" → 未闭合
  3. 基础：文件非空、无严重乱码

用法（作为模块）:
  from md_lint import md_lint
  ok, issues = md_lint("path/to/full.md")

返回 (ok: bool, issues: list[str])。ok=False 表示有需要复核的问题。
"""
import os
import re

try:
    import mistune
except ImportError:
    mistune = None

# 可选：低于此警告阈值的 md 文件视为可疑
MIN_MD_SIZE = 100


def _looks_like_table(line):
    """启发式：一行是否像表格（含 | 分隔符）"""
    return "|" in line


def _looks_like_fence(line):
    """启发式：一行是否像代码块围栏（``` 或 ~~~）"""
    return line.strip().startswith("```") or line.strip().startswith("~~~")


def md_lint(md_path, min_size=MIN_MD_SIZE):
    """检查 md 语法质量，返回 (ok, issues)。"""
    issues = []
    if not os.path.exists(md_path):
        return False, [f"文件不存在: {md_path}"]

    try:
        with open(md_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        return False, [f"读取失败: {e}"]

    if not text.strip():
        return False, ["md 内容为空"]
    if len(text) < min_size:
        issues.append(f"md 太小({len(text)}B)")

    # 乱码检测（U+FFFD 替换字符过多 = 编码问题）
    garbled = len(re.findall(r"[�]", text))
    if garbled > 5:
        issues.append(f"大量乱码字符({garbled})")

    # 无 mistune 时降级：仅做行级启发式检查
    if mistune is None:
        # 表格检查：统计含 | 的行，若分隔行(|---|)出现但列数不一致 → 报
        table_lines = [l for l in text.splitlines() if _looks_like_table(l)]
        if table_lines:
            issues.append(f"含表格样式的行 {len(table_lines)} 行，建议人工核对（无 mistune 仅启发式）")
        fence_count = sum(1 for l in text.splitlines() if _looks_like_fence(l))
        if fence_count % 2 != 0:
            issues.append(f"代码块围栏数量为奇数({fence_count})，疑似未闭合")
        return len(issues) == 0, issues

    # 正式 mistune 解析
    try:
        md = mistune.create_markdown(renderer="ast", plugins=["table"])
        tokens = md(text)
    except Exception as e:
        return False, [f"md 解析异常: {e}"]

    # 遍历 AST，统计关键节点
    table_count = 0
    code_count = 0

    def walk(ts):
        nonlocal table_count, code_count
        for t in ts:
            if t.get("type") == "table":
                table_count += 1
            elif t.get("type") == "block_code":
                code_count += 1
            children = t.get("children")
            if children:
                walk(children)

    walk(tokens)

    # 表格一致性：若全文含 | 行但 AST 一个 table 都没有 → 疑似表格损坏
    raw_table_lines = [l for l in text.splitlines() if _looks_like_table(l)]
    if raw_table_lines and table_count == 0:
        issues.append(f"发现 {len(raw_table_lines)} 行表格样式文本，但未解析出任何表格节点（列数不一致/格式损坏）")

    # 代码块闭合：围栏数奇数 = 一定有未闭合（mistune 会宽容自动闭合，靠计数兜底）
    raw_fence_lines = [l for l in text.splitlines() if _looks_like_fence(l)]
    if len(raw_fence_lines) % 2 != 0:
        issues.append(f"代码围栏数量为奇数({len(raw_fence_lines)})，疑似未闭合")

    return len(issues) == 0, issues


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python md_lint.py <full.md路径>")
        sys.exit(1)
    ok, issues = md_lint(sys.argv[1])
    if ok:
        print("[OK] md 语法通过")
    else:
        print("[问题]")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
