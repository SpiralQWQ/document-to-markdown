#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根目录薄入口：转发到 export/export_md.py（保持 `python export_md.py` 用法）。"""
import os, sys, runpy
PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
runpy.run_path(os.path.join(PROJ, 'export/export_md.py'), run_name="__main__")
