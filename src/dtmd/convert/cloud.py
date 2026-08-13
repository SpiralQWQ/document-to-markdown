#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU 每日转换执行脚本（PDF+PPT+DOC → 喂 AI 的 md）

用法:
  python -m dtmd convert --mode cloud 1                # 转换 Day 1
  python -m dtmd convert --mode cloud 1 --dry-run      # 只切片+预览，不上传
  python -m dtmd convert --mode cloud 1 --limit 2      # 只处理前 2 块（试跑）
  python -m dtmd convert --mode cloud 1 --ocr          # 扫描件强制 OCR
  python -m dtmd convert --mode cloud 1 --force        # 强制重转：绕过"已转跳过"，覆盖旧输出

流程: 本地切片 → 批量上传 → 轮询 → 下载 zip → 解压全量 → 删 zip
输出: 每原文件解压到 {原文件目录}/{原文件名}_mineru/ 独立子文件夹
      多块大文件 → {原名}_mineru/p{start}-{end}/ 分子文件夹
      full.md + images/ + json 全保留
"""
import os, sys, json, time, zipfile, re
import shutil
import requests

# Windows GBK 控制台兼容：强制 UTF-8 输出，防止 emoji/中文打印崩溃
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://mineru.net/api/v4"
# 路径统一走 dtmd.config（仓库根为基准，环境变量可覆盖）
from dtmd import config as _paths
from dtmd.utils import safe
from dtmd.convert.base import is_done, make_slice, compute_out_dir

already_done = is_done  # 统一完成判断（base.is_done）

DATA_DIR = _paths.DATA_DIR    # plan/进度 等数据
DOCS_DIR = _paths.DOCS_DIR    # 计划文档 等文档
LOGS_DIR = _paths.LOGS_DIR    # 运行日志
PLAN = _paths.PLAN
SLICE = _paths.SLICE_DIR
MAX_WAIT = 7200  # 轮询最长 2 小时
FORCE = False  # 强制重转：--force 时绕过"已转跳过"并覆盖旧输出（模块级，供 save_zip 读）


def err(msg):
    print(f"[错误] {msg}", file=sys.stderr)


def headers():
    tok = os.environ.get("MINERU_API_TOKEN", "").strip()
    if not tok:
        err("未设置 MINERU_API_TOKEN 环境变量（用 setx MINERU_API_TOKEN xxx）"); sys.exit(1)
    return {"Content-Type": "application/json", "Authorization": f"Bearer {tok}"}


def http(method, url, retries=3, **kw):
    """带重试的请求（应对偶发 SSL/连接/超时抖动）"""
    for attempt in range(retries):
        try:
            return requests.request(method, url, timeout=kw.pop("timeout", 60),
                                    proxies={"http": None, "https": None}, **kw)
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError,
                requests.exceptions.Timeout) as e:
            if attempt == retries - 1:
                raise
            wait = 3 * (attempt + 1)
            print(f"  [重试] {method} 失败({type(e).__name__})，{wait}s 后重试")
            time.sleep(wait)


def upload_file(path, url, retries=3):
    """PUT 上传（重试时重新打开文件）"""
    for attempt in range(retries):
        try:
            with open(path, "rb") as f:
                return requests.put(url, data=f, timeout=600,
                                    proxies={"http": None, "https": None})
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError,
                requests.exceptions.Timeout) as e:
            if attempt == retries - 1:
                raise
            wait = 3 * (attempt + 1)
            print(f"  [重试] 上传失败({type(e).__name__})，{wait}s 后重试")
            time.sleep(wait)


def main(argv=None):
    args = list(argv) if argv is not None else [a for a in sys.argv[1:]]
    dry = "--dry-run" in args
    global FORCE
    FORCE = "--force" in args
    # 强制 OCR = 本项目基本理念（与 README 声称一致）：默认 is_ocr=true，
    # --ocr 保留为显式确认（默认已开）；复杂文档本就强制 OCR
    ocr = True
    complex_mode = "--complex" in args
    limit = None
    # 默认预算：充分利用每日 5000 文件上限（接受超额走慢速队列）。
    # 前 1000 页优先队列快跑，超额部分优先级降低但仍会解析（不丢）。
    # 之前默认 1000 页/单次，拆多次会超日累计；现在一次排到 5000 页上限，充分利用云端。
    budget = 5000
    only_keyword = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--budget" in args:
        budget = int(args[args.index("--budget") + 1])
    if "--only" in args:
        only_keyword = args[args.index("--only") + 1]
    # Day 解析：只取"非 flag 的裸数字位置参数"，跳过带值 flag(--limit/--budget/--only)的值，
    # 避免 `--limit 2` 的 2 被误当 Day 2（Round2 fixloop 抓到的连锁 bug）
    _VALUE_FLAGS = {"--limit", "--budget", "--only", "--max"}
    day = None
    _i = 0
    while _i < len(args):
        _a = args[_i]
        if _a in _VALUE_FLAGS:
            _i += 2; continue
        if _a.startswith("-"):
            _i += 1; continue
        if _a.isdigit():
            day = int(_a); break
        _i += 1

    plan = json.load(open(PLAN, encoding="utf-8"))

    if complex_mode:
        # 处理标记的复杂文档（走云端 1000 页额度）
        blocks = plan.get("pending_complex", [])
        if only_keyword:
            # 只处理文件名含关键词的块（整本完整）
            blocks = [b for b in blocks if only_keyword.lower() in os.path.basename(b["file"]).lower()]
            if not blocks:
                print(f"[complex] 无匹配 '{only_keyword}' 的块"); return 0
        if not blocks:
            print("[complex] 无标记的复杂块"); return 0
        if limit:
            blocks = blocks[:limit]
        # 先建 file_counts（用完整 pending_complex 判断单块/多块，勿用预算过滤后的 blocks）
        file_counts = {}
        for blk in plan.get("pending_complex", []):
            file_counts[blk["file"]] = file_counts.get(blk["file"], 0) + 1
        if budget:
            used, kept = 0, []
            for b in blocks:
                # 排除已完成的块（不占今日预算）——用运行时计算的 out_dir，勿依赖 b["out_dir"]（常缺失）
                _out = compute_out_dir(b, file_counts)
                if (not FORCE) and is_done(_out):
                    continue
                if used + b["pages"] > budget:
                    continue
                used += b["pages"]; kept.append(b)
            blocks = kept
            print(f"[预算] 今日限 {budget} 页，实际排 {used} 页 / {len(blocks)} 块")
        print(f"[复杂文档] {len(blocks)} 块 / {sum(b['pages'] for b in blocks)} 页"
              + ("（DRY-RUN 预览）" if dry else ""))
        os.makedirs(SLICE, exist_ok=True)
        tasks = []
        for i, b in enumerate(blocks):
            out_dir = compute_out_dir(b, file_counts)
            if not FORCE and is_done(out_dir):
                print(f"  跳过(已完成): {os.path.basename(b['file'])} p{b['start']}-{b['end']}")
                continue
            if not os.path.exists(b["file"]):
                print(f"  跳过(源文件不存在): {os.path.basename(b['file'])}")
                continue
            tasks.append({"tmp": make_slice(b, i), "out": out_dir, "data_id": f"cx{i}"})
        if not tasks:
            print("[complex] 全部已完成"); return 0
        print(f"[待传] {len(tasks)} 个文件")
        if dry:
            for t in tasks:
                print(f"  → {os.path.basename(t['tmp'])}"); print(f"    输出: {t['out']}")
            return 0
        h = headers()
        for g in range(0, len(tasks), 50):
            group = tasks[g:g + 50]
            payload = {"files": [{"name": os.path.basename(t["tmp"]), "data_id": t["data_id"],
                                  "is_ocr": ocr, "model_version": "vlm"} for t in group],
                       "model_version": "vlm"}
            r = http("POST", f"{API}/file-urls/batch", headers=h, json=payload, timeout=60)
            rj = r.json()
            if rj.get("code") != 0:
                err(f"申请上传链接失败: {rj.get('msg')}"); sys.exit(1)
            batch_id = rj["data"]["batch_id"]
            urls = rj["data"]["file_urls"]
            for t, u in zip(group, urls):
                with open(t["tmp"], "rb") as f:
                    pr = http("PUT", u, data=f, timeout=600)
                print(f"  上传 {os.path.basename(t['tmp'])}: HTTP {pr.status_code}")
            print(f"[已提交 batch {batch_id}] {len(group)} 文件，轮询中...")
            poll_and_save(batch_id, group, h)
        cleanup()
        print(f"[复杂文档] 全部完成 ✅"); return 0

    if not day:
        err("用法: python -m dtmd convert --mode cloud <DayN> [--dry-run] [--limit N] [--ocr] [--complex]"); sys.exit(1)
    days = plan.get("days_normal") or plan.get("days") or []
    if day < 1 or day > len(days):
        err(f"Day {day} 超出范围（1-{len(days)}）"); sys.exit(1)
    blocks = days[day - 1]["blocks"]
    if limit:
        blocks = blocks[:limit]
    if budget:
        used, kept = 0, []
        for b in blocks:
            if used + b["pages"] > budget:
                print(f"  [预算] 跳过超预算块 p{b['start']}-{b['end']}（今日已排 {used}/{budget} 页，留给下次）")
                continue
            used += b["pages"]
            kept.append(b)
        blocks = kept
        print(f"[预算] 今日限 {budget} 页，实际排 {used} 页 / {len(blocks)} 块")
    print(f"[Day {day}] {len(blocks)} 块 / {sum(b['pages'] for b in blocks)} 页"
          + ("（DRY-RUN 预览，不上传）" if dry else ""))

    # 全局多块统计（跨天，保证同一文件输出结构一致）
    file_counts = {}
    for d in days:
        for blk in d["blocks"]:
            file_counts[blk["file"]] = file_counts.get(blk["file"], 0) + 1

    os.makedirs(SLICE, exist_ok=True)

    # 生成上传任务清单（跳过已完成）
    tasks = []
    for i, b in enumerate(blocks):
        orig_dir = os.path.dirname(b["file"])
        base = safe(os.path.splitext(os.path.basename(b["file"]))[0])
        out_root = os.path.join(orig_dir, base + "_mineru")
        multi = file_counts.get(b["file"], 0) > 1
        out_dir = os.path.join(out_root, f"p{b['start']}-{b['end']}") if multi else out_root
        if not FORCE and already_done(out_dir):
            print(f"  跳过(已完成): {os.path.basename(b['file'])} p{b['start']}-{b['end']}")
            continue
        if not os.path.exists(b["file"]):
            print(f"  跳过(源文件不存在): {os.path.basename(b['file'])}")
            continue
        tmp = make_slice(b, i)
        tasks.append({"tmp": tmp, "out": out_dir, "data_id": f"d{day}b{i}"})

    if not tasks:
        print("[Day] 全部已完成"); return 0
    print(f"[待传] {len(tasks)} 个文件")

    if dry:
        for t in tasks:
            print(f"  → {os.path.basename(t['tmp'])}")
            print(f"    输出: {t['out']}")
        print("[DRY-RUN] 完成，未上传。加 --ocr 开 OCR，或去掉 --dry-run 真正执行")
        return 0

    h = headers()

    # 分批上传（每批 ≤50）
    for g in range(0, len(tasks), 50):
        group = tasks[g:g + 50]
        payload = {"files": [{"name": os.path.basename(t["tmp"]), "data_id": t["data_id"],
                              "is_ocr": ocr, "model_version": "vlm"} for t in group],
                   "model_version": "vlm"}
        r = http("POST", f"{API}/file-urls/batch", headers=h, json=payload, timeout=60)
        rj = r.json()
        if rj.get("code") != 0:
            err(f"申请上传链接失败: {rj.get('msg')}"); sys.exit(1)
        batch_id = rj["data"]["batch_id"]
        urls = rj["data"]["file_urls"]
        for t, u in zip(group, urls):
            pr = upload_file(t["tmp"], u)
            print(f"  上传 {os.path.basename(t['tmp'])}: HTTP {pr.status_code}")
        print(f"[已提交 batch {batch_id}] {len(group)} 文件，轮询中...")
        poll_and_save(batch_id, group, h)

    cleanup()
    print(f"[Day {day}] 全部完成 ✅")
    return 0


def poll_and_save(batch_id, group, h):
    by_data = {t["data_id"]: t for t in group}
    done_ids = set()  # 已保存/已失败，防止轮询循环重复下载
    t0 = time.time()
    while time.time() - t0 < MAX_WAIT:
        r = http("GET", f"{API}/extract-results/batch/{batch_id}", headers=h, timeout=60)
        rj = r.json()
        if rj.get("code") != 0:
            err(f"查询失败: {rj.get('msg')}"); return
        res = rj["data"]["extract_result"]
        finished = [x for x in res if x.get("state") in ("done", "failed")]
        pending = [x for x in res if x.get("state") not in ("done", "failed")]
        for x in finished:
            t = by_data.get(x.get("data_id"))
            if not t or x.get("data_id") in done_ids:
                continue
            done_ids.add(x.get("data_id"))
            if x.get("state") == "done" and x.get("full_zip_url"):
                save_zip(t, x["full_zip_url"])
            elif x.get("state") == "failed":
                print(f"  [失败] {os.path.basename(t['tmp'])}: {x.get('err_msg', '未知')}")
        if not pending:
            return
        n_done = len(finished); n_tot = len(res)
        print(f"  [轮询] {n_done}/{n_tot} 完成，{len(pending)} 进行中...")
        time.sleep(20)
    err("轮询超时 2 小时，未完成块下次重跑会自动跳过已完成的续传")


def save_zip(t, zip_url):
    """下载 zip → 解压到输出目录 → 删除 zip（图片/json 全保留）。

    单文件失败不中断整批：HTTP 非 200 / zip 损坏 → 记录错误并返回。
    """
    if FORCE:
        shutil.rmtree(t["out"], ignore_errors=True)
    os.makedirs(t["out"], exist_ok=True)
    tmp_zip = os.path.join(SLICE, f"tmp_{t['data_id']}.zip")
    r = http("GET", zip_url, timeout=600)
    if r.status_code != 200:
        print(f"  [错误] zip 下载失败 HTTP {r.status_code}: {os.path.basename(t['out'])}")
        return
    try:
        with open(tmp_zip, "wb") as f:
            f.write(r.content)
        with zipfile.ZipFile(tmp_zip) as zf:
            # zip-slip 防护：过滤绝对路径 / ../ 越界 / 盘符相对(C:foo) 成员
            def _safe_member(m):
                fn = m.filename
                if fn.startswith(("/", "\\")):
                    return False
                if os.path.isabs(fn):
                    return False
                if os.path.splitdrive(fn)[0]:  # 盘符相对（Windows os.path.isabs 漏网的 C:evil）
                    return False
                if ".." in os.path.normpath(fn).split(os.sep):
                    return False
                return True
            members = [m for m in zf.infolist() if _safe_member(m)]
            zf.extractall(t["out"], members=members)
    except (zipfile.BadZipFile, Exception) as e:
        print(f"  [错误] zip 解压失败: {os.path.basename(t['out'])} → {e}")
        return
    finally:
        try:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
        except OSError:
            pass
    print(f"  [保存] {os.path.basename(t['out'])} ← zip 已解压并删除（full.md+images+json 全保留）")


def cleanup():
    """清理切片临时文件（保留输出本体）"""
    try:
        for fn in os.listdir(SLICE):
            p = os.path.join(SLICE, fn)
            if os.path.isfile(p):
                os.remove(p)
        print("[清理] 切片临时文件已清除")
    except OSError:
        pass


if __name__ == "__main__":
    main()
