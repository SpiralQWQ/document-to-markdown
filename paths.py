#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paths.py — 路径解析事实源（单一定义处）

整个项目的数据/文档/日志目录路径都从这里解析，避免各脚本各自定义导致
"子目录里跑找不到 _data" 的路径漂移问题。

目录约定（仓库根 = 本项目根）:
  document-to-markdown/
    ├── _data/    # 数据（plan/进度/心跳）
    ├── _docs/    # 文档（计划/清单）
    ├── _logs/    # 日志
    ├── _slices/  # 临时切片
    ├── _archive/ # 历史归档
    ├── converter/  quality/  export/  cli/  tools/   # 代码包
    └── README.md  CHANGELOG*  LICENSE  ...

环境变量可覆盖（便于任意位置运行）:
  DTM_ROOT    → 仓库根
  DTM_TOOLS   → 工具目录（通常就是仓库根）
  DTM_MINERU_ENV, DTM_PANDOC, DTM_PIX2TEXT_ENV, DTM_CLEANER_PATH
"""
import os

# 仓库根：优先环境变量，否则取本文件所在目录（paths.py 就在根）
_ROOT = os.environ.get("DTM_ROOT", os.path.dirname(os.path.abspath(__file__)))
# 工具目录：通常就是仓库根
TOOLS = os.environ.get("DTM_TOOLS", _ROOT)

# 目录结构（数据/文档/日志 分目录）
DATA_DIR = os.path.join(TOOLS, "_data")
DOCS_DIR = os.path.join(TOOLS, "_docs")
LOGS_DIR = os.path.join(TOOLS, "_logs")
SLICE_DIR = os.path.join(TOOLS, "_slices")
ARCHIVE_DIR = os.path.join(TOOLS, "_archive")

# 数据文件
PLAN = os.path.join(DATA_DIR, "plan.json")
PROGRESS_FILE = os.path.join(DATA_DIR, "auto_progress.json")
HEARTBEAT_FILE = os.path.join(DATA_DIR, "watchdog_heartbeat.json")

# 外部工具（可环境变量覆盖）
MINERU_ENV = os.environ.get("DTM_MINERU_ENV", "")
BRIDGE_DIR = os.environ.get("DTM_BRIDGE_DIR", "")
PIX2TEXT_ENV = os.environ.get("DTM_PIX2TEXT_ENV", "")
CLEANER_PATH = os.environ.get("DTM_CLEANER_PATH", "")


def _detect_pandoc():
    """Pandoc 路径检测：环境变量 → 常见便携版 → PATH 上的 pandoc。"""
    env = os.environ.get("DTM_PANDOC", "").strip()
    if env:
        return env
    # 常见便携版位置（同机开发时的通用候选，不绑定特定用户目录）
    candidates = [
        os.path.join(_ROOT, "..", "T.Pandoc_Convert_Env", "pandoc-3.10.1", "pandoc.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Pandoc", "pandoc.exe"),
        os.path.join(os.path.expanduser("~"), "pandoc", "pandoc.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "pandoc"  # 兜底：PATH 查找


PANDOC = _detect_pandoc()


def mineru_cli():
    """MinerU CLI 路径：优先 DTM_MINERU_ENV，否则找 PATH 上的 mineru。"""
    if MINERU_ENV:
        return os.path.join(MINERU_ENV, "Scripts", "mineru.exe")
    return "mineru"


def mineru_python():
    """MinerU venv 的 python；未配置则用当前解释器。"""
    if MINERU_ENV:
        return os.path.join(MINERU_ENV, "Scripts", "python.exe")
    import sys
    return sys.executable


def proxy_script():
    """GLM 代理脚本路径；未配置则空（跳过代理）。"""
    if BRIDGE_DIR:
        return os.path.join(BRIDGE_DIR, "glm_mineru_proxy.py")
    return ""
