# document-to-markdown

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
| `auto_convert.py` | 主本地转换器：按计划批量转，质检，断点续跑 |
| `mineru_day.py` | 云端转换器：批量上传 → 轮询 → 下载（MinerU 云端 API）|
| `mineru_local_batch.py` | 轻量本地批量转换器 |
| `md_lint.py` | T1：Markdown 语法门禁（mistune）|
| `table_recheck.py` | T2：表格质检（camelot，质量评分）|
| `pdf_repair.py` | T4：损坏/加密 PDF 修复（pikepdf）|
| `export_md.py` | T5：多格式导出（Pandoc）|
| `formula_recheck.py` | 公式复核钩子（可选，需要 Pix2Text）|
| `glm_mineru_proxy.py` | GLM 适配代理（MinerU hybrid 模式用）|
| `watchdog.py` | 看门狗：心跳文件检测卡死/进程死亡 |
| `check_done.py` | 检查哪些文件夹已全部转完 |

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

如果要用 `mineru_day.py`（云端模式），设置 MinerU API Token：

```bash
export MINERU_API_TOKEN="your_mineru_api_token"
```

云端模式走 mineru.net API：每天最多 **5000 个文件**；前 1000 页/天最高优先级，
超过走慢速队列（照样解析，不会丢）。

### 第 5 步 — GLM API Key（可选，hybrid 模式用）

如果用 GLM 适配代理（`glm_mineru_proxy.py`）：

```bash
export GLM_API_KEY="your_glm_api_key"
```

## 用法

### 本地批量转换

```bash
python auto_convert.py                 # 按计划转（每 10 块检查）
python auto_convert.py --no-check      # 连续转不暂停
python auto_convert.py --max 5         # 最多转 5 块
```

### 云端转换（MinerU API）

```bash
python mineru_day.py --complex --dry-run   # 预览会上传什么
python mineru_day.py --complex             # 上传并轮询复杂文档
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
python tools/clean_hook.py path/to/full.md                # → full_clean.md
python tools/clean_hook.py path/to/full.md --anonymize    # → 加 PII 脱敏
```

输出：每个 `full.md` 会在同目录生成清洗后的 `full_clean.md`。
如果没设置 `DTM_CLEANER_PATH`，钩子会静默跳过（不阻塞主流程）。

钩子内部调用 text-cleaning-engine 的标准入口：
`python -m cleaner.clean_md <文件> [--anonymize]` → JSON `{ok, cleaned_text, stats}`。

### 多格式导出

```bash
python export_md.py path/to/full.md --to docx   # → full.docx
python export_md.py path/to/full.md --to html   # → full.html
python export_md.py path/to/full.md --to pptx   # → full.pptx
```

### 质检（单独跑）

```bash
python md_lint.py path/to/full.md          # markdown 语法门禁
python table_recheck.py some.pdf           # 表格质检
python pdf_repair.py broken.pdf out.pdf    # 修复损坏 PDF
```

## 输出结构

```
{原目录}/{文档名}_mineru/
  ├── full.md           # 主输出（AI 可读）
  ├── images/           # 提取的图片
  └── *.json            # 中间解析结果
```

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)（英文）和 [CHANGELOG_zh.md](CHANGELOG_zh.md)（中文）。

## 开源协议

双许可：[AGPL-3.0](LICENSE)（开源） + 商业授权（[COMMERCIAL.md](COMMERCIAL.md)）。

## 支持

如果这个项目帮到过你，可以请我喝杯咖啡 ☕。打赏全凭心意，不打赏也完全没关系——
项目永远免费开源。做开源这么久，每一份小小的支持都能让我高兴很久。

<p align="center">
  <img src="assets/donate_wechat.jpg" alt="微信收款" width="200">
  <img src="assets/donate_alipay.jpg" alt="支付宝收款" width="200">
</p>
