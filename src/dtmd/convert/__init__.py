"""dtmd.convert — 转换域（本地/云端两条管线 + 公共基础）。

本地管线（MinerU 本地解析）与云端管线（MinerU API）共享的公共能力放 base.py：
  切片 / 完成判断。HTTP 上传是云端专属（cloud.py），MinerU CLI 调用是本地专属（local.py）。
"""
