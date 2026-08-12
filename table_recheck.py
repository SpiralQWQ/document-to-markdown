#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根目录薄入口：转发到 quality/table_recheck.py（保持 `python table_recheck.py` 用法）。"""
import os, sys, runpy
PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
runpy.run_path(os.path.join(PROJ, 'quality/table_recheck.py'), run_name="__main__")
