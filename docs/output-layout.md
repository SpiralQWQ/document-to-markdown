# Output Layout — 转写输出目录结构规范

> 本文档定义 `document-to-markdown` 所有转写产物的输出目录布局。
> 适用：云端管线（`cloud.py`）、本地管线（`local.py`）、HTML 云端转写（`_html_mode()`）。

---

## 基本原则

1. **隔离**：每个原文件独立目录 `{原文件名}_mineru/`，与原文件同目录
2. **不覆盖**：MinerU 原始输出 `.md` 保留，清洗后的 `full.md` 另存
3. **多块切片**：PDF 超过 200 页会被切片，每片一个子目录 `p{start}-{end}/`
4. **图片目录**：所有提取的图片统一放在 `images/` 子目录

---

## 单块输出（PDF/DOC/PPT ≤ 200 页，或 HTML 单文件）

```
{原文件所在目录}/
└── {原文件名}_mineru/
    ├── full.md                         ← 清洗后的最终 Markdown（block_clean + 渠道水印）
    ├── {原文件名}.md                    ← MinerU 原始输出的 Markdown（未清洗）
    ├── {原文件名}_content_list.json     ← 块级内容列表（block_clean 清洗依据）
    ├── {原文件名}_content_list_v2.json  ← v2 版内容列表（备用）
    ├── {原文件名}_layout.pdf            ← MinerU 版式分析 PDF
    ├── {原文件名}_middle.json           ← MinerU 中间结果
    ├── {原文件名}_model.json            ← MinerU 模型推理结果
    ├── {原文件名}_origin.pdf            ← 原始 PDF 分页备份（仅 PDF 源文件）
    ├── {原文件名}_span.pdf              ← MinerU 分栏分析 PDF
    └── images/
        ├── abc123.jpg                   ← 提取的图片
        └── ...
```

### HTML 文件输出

HTML 走 `_html_mode()`，输出目录结构同上，但多一个 `main.html` 文件：

```
{原文件所在目录}/
└── {原文件名}_mineru/
    ├── full.md                         ← 清洗后的最终 Markdown
    ├── main.html                       ← 原始 HTML 备份
    ├── content_list.json               ← 块级内容列表（清洗依据）
    └── images/
        └── ...
```

> HTML 不切片（整文件上传），无 `{原文件名}.md` / `_origin.pdf` / `_layout.pdf` 等非 HTML 产物。

---

## 多块输出（PDF > 200 页，被切片上传）

```
{原文件所在目录}/
└── {原文件名}_mineru/
    ├── p1-200/                         ← 第 1-200 页
    │   ├── full.md
    │   ├── {原文件名}_content_list.json
    │   ├── {原文件名}_model.json
    │   ├── {原文件名}_origin.pdf
    │   └── images/
    │       └── ...
    ├── p201-400/                       ← 第 201-400 页
    │   ├── full.md
    │   ├── {原文件名}_content_list.json
    │   ├── {原文件名}_model.json
    │   ├── {原文件名}_origin.pdf
    │   └── images/
    │       └── ...
    └── p401-552/                       ← 第 401-552 页
        ├── full.md
        └── ...
```

> 切片规则：每片 ≤ 200 页，起止页码 `p{start}-{end}` 命名。每片独立输出，各自有完整 `full.md` + `content_list.json` + `images/`。

---

## 文件说明

### 最终产物（用户直接使用）

| 文件 | 生成方式 | 用途 |
|------|---------|------|
| `full.md` | block_clean 清洗后写入 | **AI 喂料**（RAG / Agent 管线 / 笔记生成） |
| `images/` | MinerU 提取 | 图片引用（`full.md` 中通过 `![](...)` 引用） |

### MinerU 原始产物（调试 / 质检用）

| 文件 | 用途 |
|------|------|
| `{原文件名}.md` | MinerU 原始 Markdown（未清洗，含页眉/页脚/页码噪音） |
| `{原文件名}_content_list.json` | 块级内容列表（每块含 type / text / bbox / page_idx） |
| `{原文件名}_content_list_v2.json` | v2 版内容列表（备用，`_v2` 后缀不会参与清洗读取） |
| `{原文件名}_layout.pdf` | 版式分析可视化 PDF |
| `{原文件名}_middle.json` | MinerU 中间处理结果 |
| `{原文件名}_model.json` | 模型推理结果（含 OCR 文本、坐标、置信度） |
| `{原文件名}_origin.pdf` | 原始 PDF 分页备份（仅 PDF 源文件） |
| `{原文件名}_span.pdf` | 分栏分析可视化 PDF |

### HTML 特有产物

| 文件 | 用途 |
|------|------|
| `main.html` | 原始 HTML 文件备份 |

---

## 命名规则

| 字段 | 规则 | 示例 |
|------|------|------|
| `{原文件名}` | `safe()` 处理后的文件名（去掉扩展名，特殊字符替换） | `Python编程入门经典` |
| `{原文件名}_mineru` | 输出目录后缀 | `Python编程入门经典_mineru/` |
| `p{start}-{end}` | 多块子目录，页码从 1 开始 | `p1-200`、`p201-400` |
| `images/` | 图片目录名固定，不随文件名变化 | `images/` |

---

## 云端转写限额

| 限制项 | 值 | 说明 |
|--------|----|------|
| 单文件大小 | ≤ 200 MB | MinerU API 限制 |
| 单文件页数 | ≤ 200 页 | 超过需切片，分批上传 |
| 每日高优额度 | 1000 页 | 最高优先级队列 |
| 每日页数预算 | 5000 页（`--budget` 可调） | 超出 1000 页部分降级排队（不封死） |
| 每日文件数上限 | 由账号额度决定 | 错误码 `-60018`：每日解析任务数量已达上限 |
| 批量上传 | ≤ 50 文件/批 | API 单次 batch upload 上限 |
| 批量提交 | ≤ 200 个 | API 单次 batch task 上限 |
| HTML 额度 | 独立配额 | 错误码 `-60019`：html 文件解析额度不足 |
| 轮询超时 | 2 小时 | `cloud.py` `MAX_WAIT = 7200` 秒 |

> 预算通过 `--budget N` 调整（默认 5000 页），`--limit N` 限制块数。超预算块自动跳过，留到下次。
> HTML 解析使用独立额度，与 PDF/DOC/PPT 不共享页数配额。