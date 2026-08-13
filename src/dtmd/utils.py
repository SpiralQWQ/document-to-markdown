"""dtmd.utils — 纯工具函数（无业务逻辑，可被任何域引用）。

按目录契约：utils 只放纯函数工具；业务逻辑归属对应域（convert/quality/export）。
"""
import re


def safe(name):
    """Windows 非法字符替换（文件名用），全部模块共用同一份定义。

    原散落在 converter/auto_convert.py、converter/mineru_day.py、
    converter/mineru_local_batch.py、qa/blocks.py 四处，迁移后统一收敛到此处。
    """
    return re.sub(r'[<>:"/\\|?*]', "_", name)
