"""dtmd.config — 路径/环境配置（单一事实源，无硬编码绝对路径）

仓库根解析：config.py 位于 src/dtmd/config.py → 上溯 3 级到仓库根。
数据/文档/日志/切片/归档/QA 目录 + 数据文件 + 外部工具路径，均可用环境变量覆盖。

目录约定（仓库根）:
  document-to-markdown/
    ├── _data/    # 数据（plan/进度/心跳/qa 产物）
    ├── _docs/    # 文档
    ├── _logs/    # 日志
    ├── _slices/  # 临时切片
    ├── _archive/ # 历史归档
    ├── src/dtmd/ # 源码包
    └── README.md  CHANGELOG*  LICENSE  ...

环境变量:
  DTM_ROOT → 仓库根 | DTM_TOOLS → 工具目录
  DTM_MINERU_ENV, DTM_PANDOC, DTM_PIX2TEXT_ENV, DTM_CLEANER_PATH, DTM_BRIDGE_DIR
  DTM_OUTPUT_ROOT → 转写输出根目录（非空时输出到 {OUTPUT_ROOT}/<相对路径>/xxx_mineru，
                    空时默认输出到源文件旁，保持旧行为）
"""
import os

# 仓库根：优先环境变量 DTM_ROOT，否则从本文件上溯（src/dtmd/config.py → 仓库根）
_FILE_DIR = os.path.dirname(os.path.abspath(__file__))        # .../src/dtmd
_SRC_DIR = os.path.dirname(_FILE_DIR)                          # .../src
_ROOT = os.environ.get("DTM_ROOT", os.path.dirname(_SRC_DIR))  # 仓库根
# 工具目录：通常就是仓库根
TOOLS = os.environ.get("DTM_TOOLS", _ROOT)

# 目录结构（数据/文档/日志 分目录）
DATA_DIR = os.path.join(TOOLS, "_data")
DOCS_DIR = os.path.join(TOOLS, "_docs")
LOGS_DIR = os.path.join(TOOLS, "_logs")
SLICE_DIR = os.path.join(TOOLS, "_slices")
ARCHIVE_DIR = os.path.join(TOOLS, "_archive")
# QA 产物目录（L1 待复审队列 / L2 / L3 / 报告）
QA_DATA_DIR = os.path.join(DATA_DIR, "qa")

# 数据文件
PLAN = os.path.join(DATA_DIR, "plan.json")
PROGRESS_FILE = os.path.join(DATA_DIR, "auto_progress.json")
HEARTBEAT_FILE = os.path.join(DATA_DIR, "watchdog_heartbeat.json")

# 外部工具（可环境变量覆盖，无硬编码绝对路径）
MINERU_ENV = os.environ.get("DTM_MINERU_ENV", "")
BRIDGE_DIR = os.environ.get("DTM_BRIDGE_DIR", "")
PIX2TEXT_ENV = os.environ.get("DTM_PIX2TEXT_ENV", "")
CLEANER_PATH = os.environ.get("DTM_CLEANER_PATH", "")
# 转写输出根目录：非空时输出到 {OUTPUT_ROOT}/<src_rel_dir>/xxx_mineru（镜像源结构，不污染源目录）
OUTPUT_ROOT = os.environ.get("DTM_OUTPUT_ROOT", "").strip()
# GLM 代理端口（单一事实源：local.py / glm_mineru_proxy.py / watchdog 统一读取）
try:
    PROXY_PORT = int(os.environ.get("DTM_PROXY_PORT", "8031"))
except ValueError:
    PROXY_PORT = 8031  # 非法端口值兜底，避免三文件 import 崩溃


def _detect_pandoc():
    """Pandoc 路径检测：环境变量 DTM_PANDOC → 常见通用位置 → PATH 上的 pandoc。

    不含机器专属路径（本机便携 Pandoc 目录）；本机位置用 DTM_PANDOC 指定。
    """
    env = os.environ.get("DTM_PANDOC", "").strip()
    if env:
        return env
    candidates = [
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
