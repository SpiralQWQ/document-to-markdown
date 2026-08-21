"""document-to-markdown — PDF/Word/PPT → AI-ready Markdown 转换与质检工具。

包结构（src 布局）：
    convert/  转换域（本地/云端两条管线）
    quality/  质检域（gates 检查器 + levels 三层质检 + 返工/报告）
    export/   导出域（Pandoc 多格式）
    cli.py    统一 CLI 入口（`python -m dtmd <cmd>`）
    config.py 路径/环境配置（无硬编码绝对路径）
"""
__version__ = "0.5.0"
