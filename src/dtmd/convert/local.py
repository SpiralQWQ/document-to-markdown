#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document-to-Markdown 自动持续转换脚本（本地 + 云端复杂分流）

流程:
  1. 按 plan.json 逐天转普通文档（本地 hybrid 互补，不占 mineru 额度）
  2. 每转 10 块暂停，等人工检查（格式/内容/规则/复杂标记）
  3. 复杂文档自动标记跳过，留给云端 1000 页额度
  4. 断点续跑：已完成块自动跳过

用法:
  python -m dtmd convert --mode local                # 自动转换（每10块检查）
  python -m dtmd convert --mode local --no-check     # 不检查，连续转
  python -m dtmd convert --mode local --max N        # 最多转 N 块后停止
"""
import os, sys, json, time, subprocess, socket

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 路径统一走 dtmd.config（仓库根为基准，环境变量可覆盖）
from dtmd import config as _paths
ROOT = _paths.TOOLS
TOOLS = _paths.TOOLS
DATA_DIR = _paths.DATA_DIR
DOCS_DIR = _paths.DOCS_DIR
LOGS_DIR = _paths.LOGS_DIR
MINERU_ENV = _paths.MINERU_ENV
BRIDGE_DIR = _paths.BRIDGE_DIR
PYTHON = _paths.mineru_python()
MINERU_CLI = _paths.mineru_cli()
PROXY_SCRIPT = _paths.proxy_script()
PROXY_PORT = _paths.PROXY_PORT  # 单一事实源（dtmd.config）
SLICE_DIR = _paths.SLICE_DIR
PLAN = _paths.PLAN
PROGRESS_FILE = _paths.PROGRESS_FILE

# 每转 N 块检查一次
CHECK_INTERVAL = 10
BACKEND = "pipeline"  # 纯本地免费（PaddleOCR+版面+表格+公式），不烧 GLM/不占云端额度


from dtmd.utils import safe


from dtmd.convert.base import is_done


def read_glm_key():
    val = os.environ.get("GLM_API_KEY", "").strip()
    if val:
        return val
    if sys.platform == "win32":
        try:
            r = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                                "[Environment]::GetEnvironmentVariable('GLM_API_KEY','User')"],
                               capture_output=True, text=True, timeout=15)
            return r.stdout.strip()
        except Exception:
            pass
    return ""


def ensure_proxy():
    key = read_glm_key()
    if not key:
        print("[错误] 未设置 GLM_API_KEY"); sys.exit(1)
    os.environ["GLM_API_KEY"] = key
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", PROXY_PORT)); s.close()
        print(f"[代理] 已在运行 (127.0.0.1:{PROXY_PORT})")
    except OSError:
        print(f"[代理] 启动 GLM 代理...")
        subprocess.Popen([PYTHON, PROXY_SCRIPT],
                         stdout=open(os.path.join(LOGS_DIR, "proxy.log"), "a", encoding="utf-8"),
                         stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        for _ in range(20):
            time.sleep(0.5)
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s2.connect(("127.0.0.1", PROXY_PORT)); s2.close()
                print("[代理] 已就绪"); break
            except OSError:
                pass
        else:
            print("[错误] 代理启动超时"); sys.exit(1)
    os.environ["MINERU_VL_SERVER"] = f"http://127.0.0.1:{PROXY_PORT}"
    os.environ["MINERU_VL_API_KEY"] = key
    # 模型名统一走环境变量（与 glm_mineru_proxy 的 GLM_MODEL 同源，避免硬编码漂移）
    os.environ["MINERU_VL_MODEL_NAME"] = os.environ.get("GLM_MODEL", "glm-4.6v-flashx")
    # === 串行稳定配置（实测：内存稳定不爆，代价是慢） ===
    os.environ["MINERU_DEVICE_MODE"] = "cpu"          # 设备用 CPU
    os.environ["MINERU_LMDEPLOY_DEVICE"] = "cpu"      # lmdeploy 用 CPU
    os.environ["CUDA_VISIBLE_DEVICES"] = ""           # 强制禁用 GPU，避免 torch/PaddleOCR 占显存 OOM
    os.environ["MINERU_PROCESSING_WINDOW_SIZE"] = "2"  # 每次只处理 2 页（小窗口低内存峰值）
    os.environ["MINERU_API_MAX_CONCURRENT_REQUESTS"] = "1"  # 并发请求 1（串行）
    os.environ["MINERU_PDF_RENDER_THREADS"] = "1"     # PDF 渲染单线程
    os.environ["OMP_NUM_THREADS"] = "1"               # CPU 单线程
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        os.environ.pop(k, None)


def convert_block(block, out_dir, backend=BACKEND, ocr=False):
    """转换单块，返回 (ok, error_msg)"""
    # 坏 PDF 急救（v0.1.0 补丁 T4）：PDF 打不开（加密/损坏）先修复
    tmp = block["file"]
    if block.get("kind") == "PDF" and os.path.exists(block["file"]):
        try:
            from dtmd.quality.gates.pdf_repair import repair_pdf
            # 先探测能否直接打开（用 pikepdf 快速检查）
            import pikepdf as _pk
            try:
                with _pk.open(block["file"], suppress_warnings=True):
                    pass  # 能打开，无需修复
            except _pk.PasswordError:
                # 空密码加密 → 修复去加密
                _repair_src = os.path.join(SLICE_DIR, "repaired_" + safe(os.path.basename(block["file"])))
                os.makedirs(SLICE_DIR, exist_ok=True)
                _ok, _rp, _msg = repair_pdf(block["file"], _repair_src)
                if _ok:
                    tmp = _rp
                    print(f"  [急救] PDF 加密已修复: {_msg}")
                else:
                    print(f"  [跳过] {_msg}"); return False, "pdf-password-need-human"
            except Exception:
                # 损坏 → 尝试恢复
                _repair_src = os.path.join(SLICE_DIR, "repaired_" + safe(os.path.basename(block["file"])))
                os.makedirs(SLICE_DIR, exist_ok=True)
                _ok, _rp, _msg = repair_pdf(block["file"], _repair_src)
                if _ok:
                    tmp = _rp
                    print(f"  [急救] PDF 损坏已修复: {_msg}")
                else:
                    print(f"  [跳过] {_msg}"); return False, "pdf-unrepairable"
        except ImportError:
            pass  # pdf_repair 缺失时静默跳过（不阻塞）
    # 切片大文件
    size_mb = block.get("size_mb", 0)
    # 仅 PDF 才走 fitz 切片（非 PDF 大文件直接透传原文件给 mineru CLI）；缺源提前返回
    if not os.path.exists(block["file"]):
        return False, f"源文件不存在: {block['file']}"
    if block["kind"] == "PDF" and (size_mb > 200 or block["pages"] > 190):
        # 切片
        try:
            import fitz
            base = safe(os.path.splitext(os.path.basename(block["file"]))[0])
            os.makedirs(SLICE_DIR, exist_ok=True)
            tmp = os.path.join(SLICE_DIR, f"auto_{base}_p{block['start']}-{block['end']}.pdf")
            if not os.path.exists(tmp):
                src = fitz.open(block["file"])
                out = fitz.open()
                out.insert_pdf(src, from_page=block["start"]-1, to_page=block["end"]-1)
                out.save(tmp); out.close(); src.close()
        except ImportError:
            print(f"  [WARN] PyMuPDF 不可用，无法切片大文件"); return False, "pymupdf-missing"
        except Exception as e:
            print(f"  [WARN] 切片失败: {e}"); return False, f"slice-failed: {str(e)[:80]}"

    cmd = [MINERU_CLI, "-p", tmp, "-o", out_dir,
           "-m", "ocr" if ocr else "auto",
           "-b", backend, "-f", "true", "-t", "true"]
    if "http-client" in backend:
        cmd += ["-u", f"http://127.0.0.1:{PROXY_PORT}"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=21600)  # 6小时上限（串行模式慢）
        if proc.returncode != 0:
            err = proc.stderr[-300:] if proc.stderr else "no output"
            return False, err
        normalize_output(out_dir, block)  # 归位嵌套结构
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "timeout-6h"
    except Exception as e:
        return False, str(e)


def normalize_output(out_dir, block):
    """归位 mineru CLI 的嵌套输出结构到 {原名}_mineru/ 根目录。
    mineru CLI -o out_dir 会生成 out_dir/{文件名}/{backend}/...
    需把 md/json/images 移到 out_dir 根目录，符合放置规则。
    """
    import shutil
    base = safe(os.path.splitext(os.path.basename(block["file"]))[0])
    # 可能的嵌套路径
    nested_candidates = []
    for root, dirs, files in os.walk(out_dir):
        # 找包含 .md 且不在根目录的层
        md_files = [f for f in files if f.endswith(".md")]
        if md_files and root != out_dir:
            nested_candidates.append(root)
        if len(dirs) == 0 and root != out_dir and md_files:
            break

    if not nested_candidates:
        return  # 已在根目录

    # 取最深的嵌套目录作为源
    src_dir = max(nested_candidates, key=lambda p: p.count(os.sep))
    for fn in os.listdir(src_dir):
        s = os.path.join(src_dir, fn)
        d = os.path.join(out_dir, fn)
        if os.path.exists(d):
            continue
        shutil.move(s, d)
    # 清理空嵌套目录
    for root, dirs, files in os.walk(out_dir, topdown=False):
        for d in dirs:
            p = os.path.join(root, d)
            try:
                if not os.listdir(p):
                    os.rmdir(p)
            except OSError:
                pass
    # 重命名 {原名}.md → full.md
    md_src = os.path.join(out_dir, base + ".md")
    if os.path.exists(md_src) and not os.path.exists(os.path.join(out_dir, "full.md")):
        os.rename(md_src, os.path.join(out_dir, "full.md"))


def verify_output(out_dir, block):
    """检查转换输出质量，返回 (ok, issues)"""
    issues = []
    full_md = os.path.join(out_dir, "full.md")
    if not os.path.exists(full_md):
        return False, ["无 full.md"]
    size = os.path.getsize(full_md)
    if size < 100:
        issues.append(f"md 太小({size}B)")
    # 检查图片：仅当 full.md 实际引用了 images/ 但目录缺失/为空才报（纯文本文档无图正常）
    img_dir = os.path.join(out_dir, "images")
    try:
        md_refs_images = os.path.exists(full_md) and "images/" in open(full_md, encoding="utf-8", errors="replace").read(20000)
    except OSError:
        md_refs_images = False
    if os.path.isdir(img_dir):
        n_img = len(os.listdir(img_dir))
        if n_img == 0 and md_refs_images:
            issues.append("images/ 为空但 full.md 引用图片")
    else:
        if md_refs_images:
            issues.append("无 images/ 目录但 full.md 引用图片")
    # 检查 json
    json_files = [f for f in os.listdir(out_dir) if f.endswith(".json")]
    if len(json_files) < 2:
        issues.append(f"json 文件不足({len(json_files)})")
    # 内容抽样（检查是否乱码/空）
    try:
        with open(full_md, encoding="utf-8") as f:
            sample = f.read(2000)
        if sample.strip() == "":
            issues.append("md 内容为空")
        import re
        garbled = re.findall(r'[\ufffd]', sample)
        if len(garbled) > 5:
            issues.append(f"大量乱码字符({len(garbled)})")
    except Exception as e:
        issues.append(f"读 md 失败: {e}")
    # 语法门禁（mistune）：表格列数/代码块闭合（v0.1.0 补丁 T1）
    try:
        from dtmd.quality.gates.md_lint import md_lint as _md_lint
        _ok, _md_issues = _md_lint(full_md)
        issues.extend(_md_issues)
    except ImportError:
        pass  # md_lint 缺失时静默降级（不阻塞主流程）
    # 表格复核（camelot）：仅 PDF 且页数 ≤200 时启用（v0.1.0 补丁 T2）
    # 大文档全表复核太慢，只抽第 1 页做抽样；非 PDF 跳过
    if block.get("kind") == "PDF" and block.get("pages", 999) <= 200:
        try:
            from dtmd.quality.gates.table_recheck import table_recheck as _tbl
            _tbl_issues = _tbl(block["file"], full_md, out_dir)
            issues.extend(_tbl_issues)
        except ImportError:
            pass  # camelot 缺失时静默降级
        except Exception as e:
            issues.append(f"表格复核异常: {str(e)[:100]}")
    return len(issues) == 0, issues


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            return json.load(open(PROGRESS_FILE, encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] {PROGRESS_FILE} 解析失败: {e}", file=sys.stderr)
    return {"converted": 0, "last_block_idx": 0, "issues": []}


def save_progress(progress):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    json.dump(progress, open(PROGRESS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def wait_for_check(progress, day_idx, block_idx):
    """每 CHECK_INTERVAL 块，写 checkpoint 后退出，等人工检查后重跑续"""
    print(f"\n{'='*60}")
    print(f"[检查点] 已转换 {progress['converted']} 块，暂停等待人工检查")
    print(f"  位置: Day {day_idx} 第 {block_idx} 块")
    print(f"  检查项: 格式/内容/规则/复杂标记")
    print(f"[提示] 已写 checkpoint，重跑脚本将自动继续。等待人工检查...")
    # 写 checkpoint 标记（重跑时跳过已完成的）
    progress["checkpoint_at"] = f"Day{day_idx}-{block_idx}"
    save_progress(progress)
    # 用文件标记表示"需要人工检查"，重跑脚本时检测到则继续
    flag = os.path.join(TOOLS, "check_needed.flag")
    open(flag, "w", encoding="utf-8").write(f"Day{day_idx}-{block_idx}")
    print(f"[停止] 已暂停。我检查完后会删除 flag 并重跑继续。")
    sys.exit(0)


def detect_complex_now(filepath):
    """实时检测文档是否复杂（转换前调用）。严格模式：全文档采样，宁严勿漏。
    复杂标准: 无文本层(扫描版) / 图片>3张每页 / 数学公式密集
    返回 reasons 列表（空 = 普通，可转）
    """
    import re as _re
    try:
        import fitz
    except ImportError:
        return ["检测不可用(fitz缺失)"]  # 宁可跳过云端复核，也不本地冒进
    try:
        # 非 PDF（Office docx/pptx 等）无文本层/扫描/每页图片概念，天然普通
        ext = os.path.splitext(filepath)[1].lower()
        if ext != ".pdf":
            return []
        d = fitz.open(filepath)
        total = d.page_count
        if total == 0:
            d.close(); return ["空文档"]
        # 全文档采样：步长按页数自适应，首/中/尾全覆盖（复杂可能藏在后半段）
        step = max(1, total // 40)  # 最多采 ~40 页，覆盖全文档
        no_text = 0; img_count = 0; formula_pages = 0
        # 公式特征：扩展数学符号集 + LaTeX 标记
        formula_pat = _re.compile(
            r'[∫∑∏√±×÷∞→←≤≥∂∇αβγδεζηθικλμνξπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ∈∀∃∧∨]'
            r'|\\frac|\\dfrac|\\sum|\\int|\\sqrt|\\partial|\\infty|\\cdot|\\times|\\Delta|\\Rightarrow|\\approx'
        )
        for i in range(0, total, step):
            page = d[i]
            txt = page.get_text().strip()
            if not txt:
                no_text += 1
            img_count += len(page.get_images())
            if formula_pat.search(txt):
                formula_pages += 1
        d.close()
        n = (total - 1) // step + 1  # 实际采样页数
        reasons = []
        if no_text > n * 0.4:  # ≥40% 采样页无文本层 → 扫描版
            reasons.append("扫描版/无文本层")
        if img_count / n > 3:  # 平均每页 >3 张图 → 图片密集
            reasons.append("图片密集")
        if formula_pages >= 2:  # ≥2 采样页有公式 → 公式密集
            reasons.append("公式密集")
        return reasons
    except Exception:
        return ["检测异常-需人工复核"]  # 检测失败不本地冒进，转云端复核


def log_complex(block, reasons):
    """记录复杂文档到 complex_list.md（去重）"""
    complex_log = os.path.join(DOCS_DIR, "complex_list.md")
    entry = f"- 🔴 {os.path.basename(block['file'])} → 页 {block['start']}-{block['end']}（{block['pages']}页）— {';'.join(reasons)}"
    # 去重：检查是否已记录
    if os.path.exists(complex_log):
        try:
            existing = open(complex_log, encoding="utf-8").read()
            if os.path.basename(block['file']) in existing and str(block['start']) in existing:
                return
        except Exception:
            pass
    with open(complex_log, "a", encoding="utf-8") as cf:
        cf.write(entry + "\n")


def main(argv=None):
    args = list(argv) if argv is not None else sys.argv[1:]
    no_check = "--no-check" in args
    do_clean = "--clean" in args
    force_ocr = "--ocr" in args  # 强制 OCR（本地模式，README 声称支持）
    max_blocks = None
    # --max 与 --limit 同义（统一 CLI 可能透传 --limit 到 local）
    if "--max" in args:
        max_blocks = int(args[args.index("--max") + 1])
    elif "--limit" in args:
        max_blocks = int(args[args.index("--limit") + 1])

    if "http-client" in BACKEND:
        ensure_proxy()  # 仅 GLM 桥接需要代理；pipeline 纯本地不需要
    plan = json.load(open(PLAN, encoding="utf-8"))
    days = plan.get("days_normal") or plan.get("days") or []
    progress = load_progress()
    converted_since_check = 0

    print(f"[开始] 自动转换：{len(days)} 天普通文档，每 {CHECK_INTERVAL} 块检查"
          + ("（不检查模式）" if no_check else ""))
    if progress["converted"] > 0:
        print(f"[断点] 已完成 {progress['converted']} 块，跳过继续")

    total_converted = 0
    # 复杂文档清单（后续云端转换用）
    complex_log = os.path.join(DOCS_DIR, "complex_list.md")
    for day_idx, day in enumerate(days, 1):
        blocks = day["blocks"]
        for b_idx, block in enumerate(blocks, 1):
            # 先算输出目录，做已完成检查 —— 已本地转成功的块绝不再送云端（防重复浪费额度）
            orig_dir = os.path.dirname(block["file"])
            base = safe(os.path.splitext(os.path.basename(block["file"]))[0])
            out_root = os.path.join(orig_dir, base + "_mineru")
            file_count = sum(1 for d in days for x in d["blocks"] if x["file"] == block["file"])
            multi = file_count > 1
            out_dir = os.path.join(out_root, f"p{block['start']}-{block['end']}") if multi else out_root
            # 已完成：跳过（不检测、不记录）
            if is_done(out_dir):
                print(f"  [跳过·已完成] {os.path.basename(block['file'])} p{block['start']}-{block['end']}")
                continue
            # 复杂文档跳过，并记录到清单
            if block.get("complex", 0) >= 3:
                print(f"  [跳过·复杂] {os.path.basename(block['file'])} → 云端额度处理")
                with open(complex_log, "a", encoding="utf-8") as cf:
                    reason = block.get("reason", "复杂")
                    cf.write(f"- 🔴 {os.path.basename(block['file'])} → 页 {block['start']}-{block['end']}（{block['pages']}页）— {reason}\n")
                continue
            # 实时复杂检测：转换前扫描该 PDF 特征（全文档采样，宁严勿漏）
            reasons = detect_complex_now(block["file"])
            if reasons:
                print(f"  [跳过·复杂] {os.path.basename(block['file'])} → 云端额度处理（{'；'.join(reasons)}）")
                log_complex(block, reasons)
                continue
            # 转换
            print(f"  [Day{day_idx}/{b_idx}] {os.path.basename(block['file'])} → {block['start']}-{block['end']}（{block['pages']}页）")
            ok, err = convert_block(block, out_dir, ocr=force_ocr)
            if not ok:
                print(f"    [失败] {err}")
                progress["issues"].append(f"Day{day_idx} {os.path.basename(block['file'])} p{block['start']}-{block['end']}: {err[:100]}")
                save_progress(progress)
                continue
            # 验证输出
            v_ok, issues = verify_output(out_dir, block)
            if not v_ok:
                print(f"    [质量问题] {issues}")
                progress["issues"].append(f"Day{day_idx} {os.path.basename(block['file'])}: {';'.join(issues)}")
            total_converted += 1
            converted_since_check += 1
            progress["converted"] += 1
            save_progress(progress)
            print(f"    [OK] 转换完成 ({block['pages']}页)")

            # 联动清洗（--clean）：转完调 text-cleaning-engine 清洗 full.md（R5）
            if do_clean:
                try:
                    from dtmd.tools.clean_hook import clean_md
                    _full = os.path.join(out_dir, "full.md")
                    _ok, _out, _msg = clean_md(_full)
                    if _ok:
                        print(f"    [清洗] {_msg}")
                    else:
                        print(f"    [清洗跳过] {_msg}")
                except ImportError:
                    print("    [清洗跳过] clean_hook 不可用")

            # 每 CHECK_INTERVAL 块检查
            if not no_check and converted_since_check >= CHECK_INTERVAL:
                converted_since_check = 0
                wait_for_check(progress, day_idx, b_idx)

            if max_blocks and total_converted >= max_blocks:
                print(f"[完成] 达到 max {max_blocks} 块上限")
                save_progress(progress)
                return

    print(f"\n[全部完成] 共转换 {total_converted} 块")
    if progress["issues"]:
        print(f"[遗留问题] {len(progress['issues'])} 条:")
        for i in progress["issues"][-10:]:
            print(f"  - {i}")
    save_progress(progress)


if __name__ == "__main__":
    main()
