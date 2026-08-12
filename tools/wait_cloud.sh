#!/bin/bash
# 日志路径：可环境变量 DTM_CLOUD_LOG 覆盖，默认指向运行目录的 _logs
LOG="${DTM_CLOUD_LOG:-$(dirname "$0")/_logs/cloud_run.log}"
for i in $(seq 1 120); do
  ALIVE=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*mineru_day*' } | Measure-Object).Count" 2>/dev/null | tr -d '[:space:]')
  if [ -z "$ALIVE" ] || [ "$ALIVE" = "0" ]; then
    echo "CLOUD_END: 云端转写进程结束"
    exit 0
  fi
  # 日志进度
  if [ -f "$LOG" ]; then
    LAST=$(tail -2 "$LOG" 2>/dev/null | tr '\n' ' ')
    echo "PROGRESS: $LAST"
  fi
  sleep 60
done
echo "TIMEOUT: 2小时"
