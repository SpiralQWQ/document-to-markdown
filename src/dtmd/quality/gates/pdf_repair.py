#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_repair.py — 坏 PDF 急救（pikepdf）

对加密/损坏的 PDF 做修复，修复后可供 MinerU 正常解析（v0.1.0 补丁 T4）。

核心逻辑：
  1. 尝试打开 PDF，失败 → 判断是加密还是损坏
  2. 加密（PasswordError）→ 尝试空密码解密并重新保存（去加密）
  3. 损坏 → 尝试 pikepdf 规范化重存（能救回部分结构）
  4. 真加密（非空密码）→ 返回失败，标记待人工
  5. 修复产物写为 .repaired.pdf，供后续切片/上传使用

用法（作为模块）:
  from pdf_repair import repair_pdf
  ok, repaired_path, msg = repair_pdf(src_path, dst_path)

返回 (ok, repaired_path, msg)。ok=False 且 msg 含 "真加密" 表示需人工。
"""
import os


def repair_pdf(src, dst):
    """修复 PDF，返回 (ok, dst, msg)。"""
    if not os.path.exists(src):
        return False, dst, f"源文件不存在: {src}"
    try:
        import pikepdf
    except ImportError:
        return False, dst, "pikepdf 未安装"

    try:
        # 尝试直接打开（正常/空密码加密）
        with pikepdf.open(src) as pdf:
            # 去加密 + 规范化重存
            pdf.save(dst, encryption=False)
            return True, dst, "修复成功（去加密/规范化）"
    except pikepdf.PasswordError:
        return False, dst, "真加密（非空密码），需人工处理"
    except Exception as e:
        # 损坏 PDF：尝试恢复模式打开
        try:
            with pikepdf.open(src, attempt_recovery=True, suppress_warnings=True) as pdf:
                pdf.save(dst, encryption=False)
                return True, dst, f"修复成功（损坏恢复）: {str(e)[:60]}"
        except Exception as e2:
            return False, dst, f"无法修复: {str(e2)[:100]}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python pdf_repair.py <src.pdf> [dst.pdf]")
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".repaired.pdf"
    ok, out, msg = repair_pdf(src, dst)
    print(f"[{'OK' if ok else 'FAIL'}] {msg}")
    if ok:
        print(f"  修复产物: {out}")
    sys.exit(0 if ok else 1)
