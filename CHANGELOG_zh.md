# 更新日志

本项目所有值得记录的变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

## [0.5.0] — 2026-08-21

### 新增
- **块级清洗**（`dtmd.clean` 包）：剔除 MinerU 转写产物 full.md 里的页眉/页脚/页码/水印。
  检测结合 MinerU `content_list.json` 的块类型（`header`/`footer`/`page_number`/
  `page_footnote`）+ 位置感知兜底（跨页重复的贴顶矮块）+ 跨页重复确认。提供
  `clean_full_md` / `clean_out_dir` / `find_content_list`；支持 dry-run 预演与
  fail-open（清洗失败不阻塞主流程）。
- **`dtmd clean` CLI 命令**：清洗单个/多个目录，`--recursive`（递归找所有含 full.md 的
  目录，覆盖单块与多块 `p{start}-{end}` 子目录）、`--dry-run`（预演不写回）、`--verbose`。
- **转写流程默认自动清洗**：`convert/local.py` 与 `convert/cloud.py` 转写完成后立即清洗
  （fail-open——失败不阻塞转写管线）。
- **渠道水印清除（可选，接入 text-cleaning-engine）**：块级清洗后，通过 text-cleaning-engine
  的精准 `--watermark-only` 入口剥掉文字特征水印（QQ群/微信/邮箱签名）。只剥水印段，
  行/文档其余内容不动（保留率 100%）。未设置 `DTM_CLEANER_PATH` 时跳过（fail-open）。

### 修复
- 短噪音 key（<4 字符，如页码、单字答案）不再参与全文匹配删除，防止误删正文短词
  （如判断题"对/错"答案）。
- 越界/异常 bbox（y 超页高）不参与位置判定。
- 去掉底部位置感知——页脚水印已由 MinerU `footer`/`page_number` 类型直接收集，
  避免误判页面底部附近的正文。

### 测试
- `tests/test_block_clean.py`（合成数据，无需真实文档）。
- `tests/test_clean_cli.py`（CLI 边界：无参数/目录不存在/dry-run/recursive/混合/文件路径）。

## [0.4.1] — 2026-08-13

### 新增
- CI 工作流（`.github/workflows/ci.yml`）：Python 3.10/3.11/3.12 多版本跑 pytest。
- `config` / `cli` 单元测试（`tests/test_config.py`、`tests/test_cli.py`）。
- 社区文档：`SECURITY.md`、issue 模板与 PR 模板（`.github/`）。

### 修复
- `md_lint` 降级分支消息与 `l1.py` 低优先分类对齐（无 `mistune` 时表格样式文本正确归为候选）。

## [0.4.0] — 2026-08-13

**目录结构重构为 `src/dtmd/`（按职责 SoC 目录契约）。**

### 变更
- **新 `src/dtmd/` 布局**（src 布局，统一 `python -m dtmd` CLI）：
  - `dtmd/convert/` — 转换域（`base` 公共 / `local` 本地管线 / `cloud` 云端管线）
  - `dtmd/quality/` — 质检域（`gates` 检查器 + `levels` L1/L2/L3 + `blocks`/`sample`/`rework`/`report` + `vision`）
  - `dtmd/export.py`、`dtmd/tools/`（watchdog/check_done/clean_hook/glm_proxy）、`dtmd/config.py`、`dtmd/utils.py`
- **删除全部根壳**（`auto_convert.py`/`mineru_day.py`/`qa_runner.py`/...）和旧平铺包——根目录不再有 `.py` 文件。
- **统一 CLI**：`python -m dtmd convert|l1|l2|l3|rework|report|list`（7 命令）取代各脚本入口。
- **命令迁移**：`python auto_convert.py` → `python -m dtmd convert --mode local`；`python mineru_day.py --complex` → `python -m dtmd convert --mode cloud`；`python qa_runner.py l1` → `python -m dtmd l1`。
- 去重 `safe()`（原 4 份）到 `dtmd.utils`；统一 `is_done`/`already_done` 到 `dtmd.convert.base`。

### 修复
- `qa/vision.py` 硬编码绝对路径（`C:/Users/...`）→ 环境变量 `DTM_VISION_ANALYZER`（隐私红线）。
- `tests/` import 迁移到 `dtmd.*`（15 测试全过）。

### 新增
- 统一 CLI 加 `--version` / `--mode local|cloud`。
- 数据缺失（plan.json 私有数据）给友好提示，不再裸 traceback。

## [0.3.0] — 2026-08-12

质检系统（qa_runner）—— 转写产出的三层质检。

### 新增
- **`qa_runner.py` + `qa/` 包**（10 文件）：`list / l1 / l2 / l3 / rework / report` 6 命令
- **L1 自动层**：完整性 + 双层页数核对（origin.pdf 硬检 + content_list 软检）+ md_lint（高/低优先级拆分）+ 图片引用完整性
- **L2 表格复核**：camelot 只跑表格密集块（抑制 pypdf 警告刷屏）
- **L3 复审层**：文本层（LaTeX 配平/内容一致性）+ 视觉层（fitz 渲染 + Qwen-VL/GLM 双视觉 A+B 区域+整页审）+ 判定规则
- **返工闭环**：返工清单 + 重转命令生成
- **三色报告**：放心/返工/误报，JSON + Markdown 双输出
- **抽样成本控制**：高优先全查 + 公式密集代表上限（`--max-formula`）+ 视觉调用预估

### 修复
- argparse 子解析器默认值覆盖 `--scope`
- 脏块数据（缺 file/start/end）整批崩溃
- `origin.pdf` UUID 前缀命名不兼容
- content_list 末尾空白页 off-by-one 误报
- `doc.close()` 后访问 f-string bug
- 重转命令漏 `--complex`
- `report` 缺 L1 队列时产出误导性「全放心」报告（严重）
- plan.json `pending_complex ⊂ pending_normal` 重叠导致重复处理（已去重）

### 已验证
- `load_blocks(all)` 已去重复杂/普通重叠块
- L1 全量扫描：全部完成、无缺输出
- L2 表格复核：表格密集块已标记待复审
- L3 全量视觉复审：`$` 误报纠正后无 fail
- 三色报告已生成（放心/返工/候选）

## [0.2.0] — 2026-08-11

模块化重构 + 接入 text-cleaning-engine 联动清洗。

### 变更

- **模块化包结构**：脚本从根目录平铺重组为
  `converter/`（核心转换）、`quality/`（T1/T2/T4 质检）、`export/`（T5）、
  `tools/`（辅助工具）、`cli/`（入口）。
- **路径单点事实源**（`paths.py`）：所有脚本统一从这一个模块解析
  数据/文档/日志/工具路径，环境变量可覆盖（`DTM_ROOT`、`DTM_MINERU_ENV`、
  `DTM_PANDOC` 等），不再有各脚本路径漂移。
- **根目录薄入口保留**：`python auto_convert.py` 和 `python mineru_day.py`
  仍然可用——它们转发到对应包。

### 新增

- **`requirements.txt`** — 完整 pip 依赖清单。
- **`.env.example`** — 环境变量模板（路径 + API 密钥，绝不提交）。
- **`tests/`** — `md_lint`、`table_recheck`、`pdf_repair`、`export` 的单元测试。
- **`--clean` 联动钩子**（`tools/clean_hook.py`）：转换完成后，把 `full.md`
  交给 [text-cleaning-engine](https://github.com/SpiralQWQ/text-cleaning-engine)
  清洗（剥水印/导航/乱码碎片）→ `full_clean.md`。
  用 `python auto_convert.py --clean` 启用；需要 `DTM_CLEANER_PATH`。
  未配置时静默跳过。修复了 UTF-8 stdin/stdout，保证中文不乱码。

### 修复（穷举测试发现）

- **Pandoc 检测回归**：重构后 `PANDOC` 默认只找 PATH，而便携版 Pandoc 不在
  PATH → 导出全部失败。`paths._detect_pandoc()` 现按 环境变量 → 便携版 → PATH
  三级检测。
- **clean_hook 环境变量读取**：`CLEANER_PATH` 在 import 时固化，运行中改
  `DTM_CLEANER_PATH` 不生效。现改为 `_cleaner_path()` 每次实时读取。

### 测试

- **84 个穷举用例** 覆盖 8 个任务（paths、md_lint、table_recheck、pdf_repair、
  export_md、clean_hook、CLI 入口、导入/隐私），每个任务过 4 轮审核。
  完整报告：`docs/acceptance-report-v0.2.0.md`。

## [0.1.0] — 2026-08-11

首次开源发布：基于 MinerU 的批量文档转 Markdown 工具，带质检补丁和多格式导出。

### 新增

- **核心转换器**（`auto_convert.py`）：按计划批量转换 PDF/DOCX/PPTX，
  全部文档强制 OCR，转完质检，断点续跑（自动跳过已完成块）。
- **云端转换器**（`mineru_day.py`）：用 MinerU 云端 API 批量上传 → 轮询 → 下载
  （`model_version=vlm`，复杂文档强制 OCR）。
- **T1 · Markdown 语法门禁**（`md_lint.py`）：用 mistune 3.x AST 检查
  表格列数一致性、代码围栏闭合、乱码字符。接入 `verify_output()`。
- **T2 · 表格质检**（`table_recheck.py`）：用 camelot 2.x
  （stream/lattice + 质量评分）标记低置信表格。接入 `verify_output()`
  （仅 PDF ≤200 页启用）。
- **T4 · PDF 急救**（`pdf_repair.py`）：用 pikepdf 10.x 去除空密码加密、
  恢复轻度损坏 PDF；真加密标记待人工。接入 `convert_block()` 切片前。
- **T5 · 多格式导出**（`export_md.py`）：基于 Pandoc 把 `full.md` 导出为
  docx / html / epub / pptx。在 md 目录下运行，保证 `images/` 相对路径正确。
- **辅助工具**：`check_done.py`（文件夹完成度检测）、`watchdog.py`（心跳 +
  卡死检测）、`glm_mineru_proxy.py`（GLM 适配代理）、`formula_recheck.py`
  （可选公式复核钩子）、`wait_cloud.sh`。
- **目录结构**：`_data/`（计划/进度）、`_docs/`（计划文档）、`_logs/`（日志）、
  `_archive/`（历史）、`_slices/`（临时切片）。所有脚本从环境变量读路径
  （`DTM_ROOT`、`DTM_MINERU_ENV`、`DTM_PANDOC` 等），任意位置可运行。

### 移除（开发过程中）

- **T3 · MixTeX 公式复核**：MixTeX 不在 PyPI（文档写的 `pip install mixtex`
  不存在）；改用 Pix2Text 实测发现它不做公式级复核（整页识别且有错字）。
  不硬塞无用功能，故移除。

### 修复

- **mistune 自动闭合未闭合代码围栏**：mistune 3.x 对未闭合代码块会静默闭合，
  所以围栏闭合检测改为数围栏行数（奇数 = 未闭合）。
- **pikepdf 10.x 移除 `strict` 参数**：损坏恢复改用 `attempt_recovery=True`。
- **export_md 自定义输出路径**：输出改用绝对路径，`--out` 跨目录可用。

### 依赖

- Python 3.10+：`mistune 3.3.4`、`camelot-py 2.0.0`、`pikepdf 10.11.0`
- 可选：`Pandoc`（3.x）导出用、`Pix2Text` 环境公式复核用、
  `GLM_API_KEY` hybrid 模式用、`MINERU_API_TOKEN` 云端模式用。
