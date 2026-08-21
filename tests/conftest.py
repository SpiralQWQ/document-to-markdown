"""conftest — 保证 pytest 能 import 到 src 布局的 dtmd 包（src 布局标准做法）。"""
import os
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# 测试隔离外部依赖：禁用 text-cleaning-engine（渠道水印跳过），让块级清洗单测聚焦、稳定
os.environ["DTM_CLEANER_PATH"] = ""
