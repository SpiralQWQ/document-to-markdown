# document-to-markdown

<p align="center">
  <strong>PDF / Word / PPT → AI 可读 Markdown</strong><br>
  批量文档转写 · 强制 OCR · 质检门禁 · 多格式导出
</p>

<p align="center">
  <a href="https://github.com/SpiralQWQ/document-to-markdown/stargazers">
    <img src="https://img.shields.io/github/stars/SpiralQWQ/document-to-markdown?style=flat-square" alt="GitHub stars">
  </a>
  <a href="https://github.com/SpiralQWQ/document-to-markdown/blob/master/LICENSE">
    <img src="https://img.shields.io/github/license/SpiralQWQ/document-to-markdown?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/OCR-forced-orange.svg?style=flat-square" alt="强制 OCR">
  <img src="https://img.shields.io/badge/quality-L1%2FL2%2FL3-green.svg?style=flat-square" alt="质检三层">
  <a href="https://github.com/SpiralQWQ/document-to-markdown/actions/workflows/ci.yml">
    <img src="https://github.com/SpiralQWQ/document-to-markdown/actions/workflows/ci.yml/badge.svg" alt="CI">
  </a>
  <a href="https://github.com/SpiralQWQ/document-to-markdown/commits/master">
    <img src="https://img.shields.io/github/last-commit/SpiralQWQ/document-to-markdown?style=flat-square" alt="最近提交">
  </a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="CHANGELOG_zh.md">更新日志</a> ·
  <a href="CONTRIBUTING.md">贡献指南</a> ·
  <a href="COMMERCIAL.md">商业授权</a>
</p>

---

## 目录

- [解决的问题](#解决的问题)
- [特性](#特性)
- [架构](#架构)
- [文件说明](#文件说明)
- [安装](#安装)
- [用法](#用法)
- [质检系统 dtmd](#质检系统-dtmd)
- [配置参考](#配置参考)
- [输出结构](#输出结构)
- [FAQ / 常见问题](#faq-常见问题)
- [路线图](#路线图)
- [贡献](#贡献)
- [更新日志](#更新日志)
- [开源协议](#开源协议)
- [支持](#支持)

---

把 **PDF / Word（DOCX）/ PowerPoint（PPTX）** 文档转写成 **AI 可直接阅读的 Markdown**，
喂给大模型（RAG、Agent 流水线、笔记生成）。底层用 **MinerU** 做解析引擎，
并配有质检补丁（T1/T2/T4）和多格式导出（T5）。

> 项目作者：[SpiralQWQ](https://github.com/SpiralQWQ)

> 🔗 **联动** [**text-cleaning-engine**](https://github.com/SpiralQWQ/text-cleaning-engine)
> — 可选地把转出的 Markdown 交给它清洗（剥水印/导航/乱码碎片），再喂给大模型。
> 详见下方[联动清洗](#联动清洗可选接入-text-cleaning-engine)。

## 解决的问题

| 痛点 | document-to-markdown |
|---|---|
| 手动把 PDF/Word/PPT 转成 md 太慢 | ✅ 自动批量转换 |
| 扫描版 PDF 不开 OCR 会转出空壳 | ✅ 全部文档强制 OCR |
| 表格/公式经常转错 | ✅ 质检补丁拦截（T1/T2）|
| 加密/损坏的 PDF 静默失败 | ✅ 解析前自动修复（T4）|
| 只要 md，还想要 Word/PDF/PPT | ✅ Pandoc 多格式导出（T5）|
| 大规模转换质量没底 | ✅ **dtmd 质检**：L1/L2/L3 三层质检 + 返工闭环 |

## 特性

| 领域 | 你得到什么 |
|---|---|
| 📄 **多格式输入** | PDF、Word（DOCX）、PowerPoint（PPTX）|
| 🔍 **强制 OCR** | 每个文档都开 OCR——扫描页/公式永不丢失 |
| 🧪 **质检补丁（T1/T2/T4/T5）** | md 语法门禁 · 表格复核 · PDF 修复 · 多格式导出 |
| 🧠 **质检系统（dtmd）** | L1 自动 · L2 表格复核 · L3 视觉复审 · 返工闭环 · 三色报告 |
| ☁️ **云端模式** | MinerU API 批量上传→轮询→下载（5000 文件/天）|
| 🧼 **清洗联动** | 接入 text-cleaning-engine（剥水印/导航/乱码）|
| 🔄 **断点续跑** | 自动跳过已转块；重跑续传不重复 |
| 🖥️ **跨平台** | Windows / Linux / macOS（环境变量配路径）|

## 架构

```
输入文档（PDF / DOCX / PPTX）
  ├─ T4 pdf_repair：解析前修复损坏/加密 PDF
  ├─ MinerU（本地 pipeline 或云端 API）：解析 → full.md + images/ + json
  ├─ T1 md_lint：语法门禁（表格列数一致、代码块闭合）
  ├─ T2 table_recheck：camelot 交叉复核低置信表格
  └─ T5 export_md：Pandoc → docx / html / epub / pptx
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `src/dtmd/convert/local.py` | 主本地转换器：按计划批量转，质检，断点续跑 |
| `src/dtmd/convert/cloud.py` | 云端转换器：批量上传 → 轮询 → 下载（MinerU 云端 API）|
| `src/dtmd/convert/local_batch.py` | 轻量本地批量转换器 |
| `src/dtmd/cli.py` | **统一 CLI 入口**：转换 + L1/L2/L3 质检：L1/L2/L3 质检 + 返工闭环 + 三色报告 |
| `src/dtmd/quality/` | **质检包**：`blocks`(清单/状态) · `l1`(完整性/页数/md_lint/图片) · `l2`(表格复核) · `l3`(公式密度/文本/视觉) · `vision`(fitz 渲染+双视觉) · `sample`(L3抽样) · `rework` · `report` |
| `src/dtmd/quality/gates/md_lint.py` | T1：Markdown 语法门禁（mistune）|
| `src/dtmd/quality/gates/table_recheck.py` | T2：表格质检（camelot，质量评分）|
| `src/dtmd/quality/gates/pdf_repair.py` | T4：损坏/加密 PDF 修复（pikepdf）|
| `src/dtmd/export.py` | T5：多格式导出（Pandoc）|
| `src/dtmd/tools/glm_mineru_proxy.py` | GLM 适配代理（MinerU hybrid 模式用）|
| `src/dtmd/tools/watchdog.py` | 看门狗：心跳文件检测卡死/进程死亡 |
| `src/dtmd/tools/check_done.py` | 检查哪些文件夹已全部转完 |

## 安装

按顺序执行，每一步都告诉你装什么。

### 下载清单

| # | 获取 | 用途 | 来源 |
|---|---|---|---|
| 1 | 本仓库 | 代码 | 下面 `git clone` |
| 2 | Python 3.10+ | 运行脚本 | python.org |
| 3 | **MinerU**（+ 模型）| 解析引擎 | `pip install "mineru[all]"` |
| 4 | PyMuPDF | 大 PDF 切片 | `pip install pymupdf` |
| 5 | mistune、camelot-py、pikepdf | 质检补丁 | `pip install mistune "camelot-py[base]" pikepdf` |
| 6 | Pandoc（可选）| 多格式导出 | pandoc.org 或 `winget install JohnMacFarlane.Pandoc` |

### 第 1 步 — 克隆本仓库

```bash
git clone https://github.com/SpiralQWQ/document-to-markdown.git
cd document-to-markdown
```

### 第 2 步 — 安装 Python 依赖

```bash
pip install "mineru[all]" pymupdf mistune "camelot-py[base]" pikepdf
```

然后以可编辑模式安装本包，让 `python -m dtmd` 能在任意位置运行。在仓库根目录执行：

```bash
python -m pip install -e .
```

> **强制 OCR 是本项目的基本理念**：每个文档（PDF/Word/PPT）都开 OCR 解析，
> 这样扫描页、公式不会丢。慢，但准——这正是"慢、稳、准"要的效果。

### 第 3 步 — 配置路径（环境变量）

所有脚本通过环境变量读路径，可以在任意位置运行。默认指向仓库自身结构。

| 变量 | 作用 | 默认值 |
|---|---|---|
| `DTM_ROOT` | 数据根目录（你的文档）| 仓库上一级目录 |
| `DTM_TOOLS` | 工具目录（本仓库）| 仓库目录 |
| `DTM_MINERU_ENV` | MinerU 虚拟环境路径 | `mineru`（PATH 中）|
| `DTM_PANDOC` | Pandoc 可执行路径 | `pandoc`（PATH 中）|
| `DTM_PIX2TEXT_ENV` | Pix2Text 环境（可选，公式复核）| 空（关闭）|
| `DTM_PROXY_PORT` | GLM 代理端口 | `8031` |

Linux/macOS 示例：

```bash
export DTM_MINERU_ENV="/path/to/your/mineru-env"
export DTM_ROOT="/path/to/your/documents"
```

Windows PowerShell 示例：

```powershell
$env:DTM_MINERU_ENV = "E:\path\to\mineru-env"
$env:DTM_ROOT = "E:\path\to\documents"
```

### 第 4 步 — 准备数据目录（`_data/plan.json`）

转换需要一个**转换计划** `_data/plan.json`（描述要转哪些文件、页范围等）。
开源版**不含此文件**（它是你的私有数据），需自行创建。

最小计划示例（`_data/plan.json`）：

```json
{
  "days_normal": [
    {
      "blocks": [
        {
          "kind": "PDF",
          "file": "/path/to/your/file.pdf",
          "pages": 100,
          "size_mb": 5,
          "start": 1,
          "end": 100
        }
      ]
    }
  ]
}
```

脚本首次运行会自动创建 `_data/` / `_docs/` / `_logs/` / `_slices/` 目录。

### 第 5 步 — 云端 API Token（可选，云端模式用）

如果要用云端模式（`dtmd convert --mode cloud`），设置 MinerU API Token：

```bash
export MINERU_API_TOKEN="your_mineru_api_token"
```

云端模式走 mineru.net API：每天最多 **5000 个文件**；前 1000 页/天最高优先级，
超过走慢速队列（照样解析，不会丢）。

### 第 6 步 — GLM API Key（可选，hybrid 模式用）

如果用 GLM 适配代理（`glm_mineru_proxy.py`）：

```bash
export GLM_API_KEY="your_glm_api_key"
```

## 用法

### 本地批量转换

```bash
python -m dtmd convert --mode local                 # 按计划转（每 10 块检查）
python -m dtmd convert --mode local --no-check      # 连续转不暂停
python -m dtmd convert --mode local --max 5         # 最多转 5 块
```

### 云端转换（MinerU API）

```bash
python -m dtmd convert --mode cloud --complex --dry-run   # 预览会上传什么
python -m dtmd convert --mode cloud --complex             # 上传并轮询复杂文档
```

### 联动清洗（可选，接入 text-cleaning-engine）

转换完成后，可以把 Markdown 交给
[**text-cleaning-engine**](https://github.com/SpiralQWQ/text-cleaning-engine)
——一个规则驱动的清洗引擎，能剥掉转写文本里的水印、导航噪声、广告、乱码碎片。

```bash
# 1. 克隆清洗引擎并指向它
git clone https://github.com/SpiralQWQ/text-cleaning-engine.git /path/to/text-cleaning-engine
export DTM_CLEANER_PATH="/path/to/text-cleaning-engine"

# 2. 用清洗钩子清洗转出的文档（内部调用 text-cleaning-engine 的 clean_md 接口）
python -m dtmd.tools.clean_hook path/to/full.md                # → full_clean.md
python -m dtmd.tools.clean_hook path/to/full.md --anonymize    # → 加 PII 脱敏
```

输出：每个 `full.md` 会在同目录生成清洗后的 `full_clean.md`。
如果没设置 `DTM_CLEANER_PATH`，钩子会静默跳过（不阻塞主流程）。

钩子内部调用 text-cleaning-engine 的标准入口：
`python -m cleaner.clean_md <文件> [--anonymize]` → JSON `{ok, cleaned_text, stats}`。

### 多格式导出

```bash
python -m dtmd.export path/to/full.md --to docx   # → full.docx
python -m dtmd.export path/to/full.md --to html   # → full.html
python -m dtmd.export path/to/full.md --to pptx   # → full.pptx
```

### 质检（单独跑）

```bash
python -m dtmd.quality.gates.md_lint path/to/full.md          # markdown 语法门禁
python -m dtmd.quality.gates.table_recheck some.pdf           # 表格质检
python -m dtmd.quality.gates.pdf_repair broken.pdf out.pdf    # 修复损坏 PDF
```

## 质检系统 dtmd

`dtmd` 的质检子命令构成**三层质检系统**。转换完成后跑它，就知道哪些文档可信。

```
┌─ L1 · 自动（免费）─────────────────────────────┐
│  完整性 · 页数核对 · md_lint · 图片引用          │
│  → 标红=待复审候选（不判失败）                  │
├─ L2 · 专项（免费）─────────────────────────────┤
│  camelot 对表格密集块复核                       │
├─ L3 · 视觉复审（花 token）─────────────────────┤
│  文本层(LaTeX配平) + 视觉层(fitz渲染+双视觉)   │
└───────────────────────────────────────────────┘
   → 三色报告：放心 pass / 返工 rework / 误报 review
```

### 命令

```bash
python -m dtmd convert --mode local|cloud   # 转换（本地/云端管线）
python -m dtmd list [--scope all|complex|normal]   # 列出块与状态
python -m dtmd l1 [--scope all|complex|normal]   # L1 自动检查 → 待复审队列
python -m dtmd l2                                # L2 camelot 表格复核
python -m dtmd l3                                # L3 计划+成本预估（不跑视觉）
python -m dtmd l3 --run                          # L3 执行视觉复审（花 token）
python -m dtmd rework --cmds                     # 返工清单 + 重转命令
python -m dtmd report                            # 三色报告（JSON + MD）
```

典型流程：`l1 → l2 → l3 --run → rework → report`。

### 产物

| 产物 | 默认路径 |
|---|---|
| L1 待复审队列 | `_data/qa/l1_queue.json` |
| L2 结果 | `_data/qa/l2_results.json` |
| L3 结果 | `_data/qa/l3_results.json` |
| 三色报告 | `_data/qa/qa_report.json` + `qa_report.md` |
| 返工清单 | `_data/qa/rework.json` |

> L3 视觉复审**默认不开**（`--run` 才跑），因为它调用 Qwen-VL/GLM 视觉 API（按量计费）。
> 默认 `l3` 先出计划+成本预估；用 `--max-formula N` 控制公式密集抽样上限。

## 输出结构

```
{原目录}/{文档名}_mineru/
  ├── full.md           # 主输出（AI 可读）
  ├── images/           # 提取的图片
  └── *.json            # 中间解析结果
```

## 配置参考

所有脚本从环境变量读配置（**无硬编码路径**）。在 shell profile 或 `.env` 里设置（见 `.env.example`）。

### 路径

| 变量 | 作用 | 默认 |
|---|---|---|
| `DTM_ROOT` | 根数据目录（你的文档）| 仓库上级目录 |
| `DTM_TOOLS` | 工具目录（本仓库）| 仓库目录 |
| `DTM_MINERU_ENV` | MinerU 虚拟环境路径 | PATH 上的 `mineru` |
| `DTM_PANDOC` | Pandoc 可执行路径 | PATH 上的 `pandoc` |
| `DTM_PIX2TEXT_ENV` | Pix2Text venv（可选，公式复核）| 空（禁用）|
| `DTM_CLEANER_PATH` | text-cleaning-engine 仓库路径 | 空（钩子跳过）|
| `DTM_BRIDGE_DIR` | GLM 代理脚本（`glm_mineru_proxy.py`）所在目录 | 空（代理禁用）|
| `DTM_VISION_ANALYZER` | vision_analyzer.py 路径（L3 视觉复审必需）| PATH 上的 `vision_analyzer.py` |

### API Key

| 变量 | 作用 |
|---|---|
| `MINERU_API_TOKEN` | MinerU 云端 API（`dtmd convert --mode cloud`）|
| `GLM_API_KEY` | GLM-4.6V 视觉（L3 复审 / hybrid 代理）|
| `QWEN_API_KEY` | Qwen-VL 视觉（L3 复审，parallel 后端）|
| `GEMINI_API_KEY` | Gemini 视觉（可选 L3 后端）|

> L3 视觉复审默认用 **Qwen-VL + GLM-4.6V 并行**（`--backend parallel`），需设 `QWEN_API_KEY` 和 `GLM_API_KEY`。

## FAQ / 常见问题

### Q：扫描版 PDF 转出来是空的/缺字
确认 OCR 已开。`dtmd convert --mode local` 和 `dtmd convert --mode cloud` 默认强制 OCR。单块可用 `--ocr` 重跑（见 `python -m dtmd convert --help`）。

### Q：`dtmd l1` 标了一堆"表格样式未解析"
那是 **md_lint 的 `|` 启发式**——把任何含 `|` 的行当成疑似表格。数学（`|V|`）和代码常误报，所以标红是**低优先候选**，不是失败。用 `l2`（camelot）或 `l3`（视觉）确认真问题。

### Q：`dtmd l3` 显示"~315 次调用"，正常吗？
正常——那是选中目标的**成本预估**。`l3` 不加 `--run` 只出计划。用 `--max-formula N`、`--pages N`、`--limit N` 控制成本。

### Q：camelot 读不了我的 PDF
camelot 需要 **Ghostscript**。装好并加入 PATH。有些 PDF 需要 `lattice` 而非 `stream`，工具会自动尝试两种。

### Q：找不到 `_data/plan.json`
计划是**你的私有数据**（转哪些文件/页），不随仓库发布。自己建——见[安装第 4 步](#第-4-步--准备数据目录_dataplanjson)的最小示例。

### Q：`list --scope all` 显示块数比预期少？
`complex` 是 `normal` 的**子集**（复杂文档也会出现在普通清单里）。`dtmd` 按 `(file, start, end)` 去重，`all` 只显示去重后的唯一块。

### Q：能去掉转出文本里的水印/导航噪声吗？
可以——用可选的 [text-cleaning-engine](#联动清洗可选接入-text-cleaning-engine) 钩子（`python -m dtmd.tools.clean_hook path/to/full.md` → `full_clean.md`）。

## 路线图

- [ ] **PyPI 发布**（打包元数据已就绪）
- [ ] **Docker 镜像**：一键本地 pipeline
- [ ] **表格校验**：TEDS 打分（比 camelot accuracy 更强）
- [ ] **批量报告**：跨多本书的汇总质检报告
- [ ] **Web UI**：上传 → 转换 → 审阅面板

## 贡献

欢迎贡献！Bug 反馈、功能建议、PR 都欢迎。请先读 [CONTRIBUTING.md](CONTRIBUTING.md)，所有贡献需遵守我们的[行为准则](CODE_OF_CONDUCT.md)。

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)（英文）和 [CHANGELOG_zh.md](CHANGELOG_zh.md)（中文）。

## 开源协议

双许可：[AGPL-3.0](LICENSE)（开源） + 商业授权（[COMMERCIAL.md](COMMERCIAL.md)）。

## 支持

如果这个项目帮到过你，可以请我喝杯咖啡 ☕。打赏全凭心意，不打赏也完全没关系——
项目永远免费开源。

<p align="center">
  <img src="assets/donate_wechat.jpg" alt="微信收款" width="200">
  <img src="assets/donate_alipay.jpg" alt="支付宝收款" width="200">
</p>
