# 更新日志

本项目所有值得记录的变更都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

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
  完整报告：`docs/开源发布验收报告_v1.0.md`。

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
