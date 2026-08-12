#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_convert 看门狗 — 检测转换是否卡死/推进，写心跳文件供 Monitor 监控

监控指标:
  1. GLM 代理连接数（>0 = 在调 GLM）
  2. 输出目录 full.md 数量（产出增长）
  3. auto_progress converted 计数
  4. auto_convert 进程存活
  5. 心跳时间戳（检测卡死：无心跳超时 = 卡住）

用法: python watchdog.py
"""
import os, sys, json, time, subprocess, glob

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paths as _paths
TOOLS = _paths.TOOLS
DATA_DIR = _paths.DATA_DIR
HEARTBEAT = _paths.HEARTBEAT_FILE
PROGRESS = _paths.PROGRESS_FILE
ROOT = _paths.TOOLS

# 心跳超时（秒）：超过此时间无 GLM 连接且无新产出 = 卡死
STALE_SECONDS = 900  # 15分钟


def check_glm_conns():
    try:
        r = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10)
        # 统计 ESTABLISHED 到 8031 的连接
        conns = 0
        for line in r.stdout.splitlines():
            if "127.0.0.1:8031" in line and "ESTABLISHED" in line:
                conns += 1
        return conns
    except Exception:
        return -1


def count_outputs():
    """统计所有 _mineru 目录里最近的 full.md"""
    try:
        now = time.time()
        fresh = 0
        for md in glob.glob(os.path.join(ROOT, "**", "*_mineru", "full.md"), recursive=True):
            if now - os.path.getmtime(md) < 600:  # 10分钟内的
                fresh += 1
        return fresh
    except Exception:
        return -1


def check_process():
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match 'auto_convert' -and $_.Name -match 'python'} | Select-Object -First 1"],
            capture_output=True, text=True, timeout=15)
        return "ProcessId" in r.stdout
    except Exception:
        return False


def main():
    while True:
        conns = check_glm_conns()
        fresh = count_outputs()
        alive = check_process()
        conv = 0
        if os.path.exists(PROGRESS):
            try:
                conv = json.load(open(PROGRESS, encoding="utf-8")).get("converted", 0)
            except: pass
        status = {
            "ts": time.time(),
            "glm_conns": conns,
            "fresh_outputs_10min": fresh,
            "process_alive": alive,
            "converted": conv,
        }
        json.dump(status, open(HEARTBEAT, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(30)


if __name__ == "__main__":
    main()
