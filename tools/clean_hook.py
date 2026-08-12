#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_hook.py — 联动 text-cleaning-engine 清洗钩子

把转换出的 full.md 交给 text-cleaning-engine 做规则清洗（去导航/广告/水印/乱码碎片），
输出 full_clean.md。通过子进程调用其 `cleaner.clean_md` 标准接口（`python -m cleaner.clean_md`），
避免依赖注入，输出稳定的 JSON。

前提：
  已 clone text-cleaning-engine 仓库，且 DTM_CLEANER_PATH 指向它。
  未配置时本钩子静默跳过（不阻塞主流程）。

用法（作为模块）:
  from tools.clean_hook import clean_md
  ok, out_path, msg = clean_md(full_md_path)

返回 (ok, out_path, msg)。ok=False 且 msg 含"未配置"表示未启用。
"""
import os
import subprocess
import sys


def _cleaner_path():
    """text-cleaning-engine 路径：每次实时读环境变量（可运行中改 DTM_CLEANER_PATH）。"""
    env = os.environ.get("DTM_CLEANER_PATH", "").strip()
    if env:
        return env
    try:
        import paths as _paths
        return _paths.CLEANER_PATH
    except ImportError:
        return ""


def _cleaner_python():
    """text-cleaning-engine 用的 python（其依赖装在哪个环境就用哪个）。"""
    if not _cleaner_path():
        return ""
    return sys.executable  # 默认当前解释器（假设依赖已装）；可覆盖


def clean_md(full_md_path, anonymize=False, form="markdown"):
    """清洗 full.md，输出同目录 full_clean.md。返回 (ok, out_path, msg)。"""
    if not _cleaner_path():
        return False, None, "未配置 DTM_CLEANER_PATH，清洗跳过（--clean 未生效）"
    if not os.path.exists(full_md_path):
        return False, None, f"文件不存在: {full_md_path}"

    out_path = os.path.splitext(full_md_path)[0] + "_clean.md"
    # 子进程调用 text-cleaning-engine 的 clean_md 标准接口（替代内联 -c 代码，
    # 输出稳定的 JSON，避免引号转义/输出解析脆弱）
    cmd = [sys.executable, "-X", "utf8", "-m", "cleaner.clean_md", full_md_path]
    if anonymize:
        cmd.append("--anonymize")
    if form and form != "markdown":
        cmd += ["--form", form]
    env = dict(os.environ)
    env["PYTHONPATH"] = _cleaner_path() + os.pathsep + env.get("PYTHONPATH", "")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=False, timeout=120, env=env)
    except subprocess.TimeoutExpired:
        return False, None, "清洗超时(120s)"
    except Exception as e:
        return False, None, str(e)

    if proc.returncode != 0:
        return False, None, f"清洗失败: {proc.stderr[-200:].decode('utf-8','replace') if proc.stderr else '无错误'}"

    try:
        import json
        res = json.loads(proc.stdout.decode("utf-8", "replace").strip())
        cleaned = res.get("cleaned_text") or res.get("text") or ""
    except (json.JSONDecodeError, ValueError):
        # 解析失败时退化为原始输出
        cleaned = proc.stdout.decode("utf-8", "replace")

    if not cleaned.strip():
        return False, None, "清洗结果为空"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
    except OSError as e:
        return False, None, f"写入失败: {e}"

    return True, out_path, f"已清洗 → {os.path.basename(out_path)}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tools/clean_hook.py <full.md路径> [--anonymize]")
        sys.exit(1)
    anon = "--anonymize" in sys.argv
    ok, out, msg = clean_md(sys.argv[1], anonymize=anon)
    print(f"[{'OK' if ok else 'FAIL'}] {msg}")
    sys.exit(0 if ok else 1)
