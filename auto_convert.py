#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根目录薄入口：转发到 converter/auto_convert.py（保持 `python auto_convert.py` 用法）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter.auto_convert import main

if __name__ == "__main__":
    sys.exit(main())
