# 验收报告 v0.1.0 — _mineru_tools 质检补丁与目录整理

> 日期：2026-08-11
> 项目：M.AIStudy 文档转写工具（MinerU 双通道）
> 范围：目录整理 + 4 个补丁（T1 mistune / T2 camelot / T4 pikepdf / T5 Pandoc）
> 前置：基于 673 仓文档转写调研（`_调研/github笔记格式调研/文档转写md调研/`）的补丁重构计划

---

## 一、执行摘要

### 完成情况

| 项 | 状态 | 说明 |
|---|---|---|
| 目录整理（B 方案）| ✅ | _data/_docs/_logs 分目录，4 脚本路径统一常量 |
| T1 mistune md 门禁 | ✅ | 新增 md_lint.py，接入 verify_output |
| T2 camelot 表格复核 | ✅ | 新增 table_recheck.py，接入 verify_output |
| T3 MixTeX 公式复核 | ❌ **已砍** | MixTeX PyPI 无包；Pix2Text 实测不符（有错字、非公式复核）|
| T4 pikepdf 坏 PDF 急救 | ✅ | 新增 pdf_repair.py，接入 convert_block |
| T5 Pandoc 多格式导出 | ✅ | 新增 export_md.py，Pandoc 便携版 |
| F2 CHANGELOG | 见配套 | CHANGELOG.md |

### 关键结论
- **4 个补丁全部通过 4 轮审核**（完成度/副作用/隐藏bug/融合度），无回归
- **T3 砍掉**（诚实决策：不硬塞无用功能，详见第五节）
- **目录整理未破坏任何功能**：云端 dry-run、本地数据读取全部正常

---

## 二、目录整理（B 方案）

### 结构变更
```
_mineru_tools/
├── auto_convert.py / mineru_day.py / watchdog.py / mineru_local_batch.py / check_done.py / glm_mineru_proxy.py / wait_cloud.sh  ← 核心脚本（根目录）
├── _data/    plan.json, auto_progress.json, watchdog_heartbeat.json
├── _docs/    cloud_plan.md, complex_list.md, 验收报告, CHANGELOG
├── _logs/    auto_run.log, cloud_run.log, cloud_err.log, auto_run_err.log
├── _archive/ 旧文档 + 测试遗留(_test_local/_test_ocr + 测试log)
└── _slices/  临时切片（运行时会重建）
```

### 脚本路径改动（统一目录常量）
| 脚本 | 改动 |
|---|---|
| auto_convert.py | 新增 DATA_DIR/DOCS_DIR/LOGS_DIR 常量；PLAN/PROGRESS→_data、complex_list→_docs、proxy.log→_logs |
| mineru_day.py | 新增 DATA_DIR/DOCS_DIR/LOGS_DIR；PLAN→_data（动态路径）|
| mineru_local_batch.py | PLAN→_data |
| watchdog.py | HEARTBEAT/PROGRESS→_data |

### 验证
- 语法 6 脚本全 OK
- 旧路径残留 0
- plan.json（25 天普通 + 186 块复杂）可读
- mineru_day.py dry-run 实战跑通（正确识别已完成块）

---

## 三、T1 mistune md 语法门禁

### 实现
- 新增 `md_lint.py`（mistune 3.x，AST 模式 + table 插件）
- 检测：表格列数一致性、代码块围栏闭合、空文件、乱码
- 接入 `auto_convert.py` 的 `verify_output()`

### 4 轮审核
| 轮 | 结果 |
|---|---|
| ① 完成度 | ✅ 正常文档/坏表格/坏代码/空/乱码全判定正确 |
| ② 副作用 | ✅ verify_output 真实输出 ok=True，原有大小/乱码检查保留 |
| ③ 隐藏bug | ✅ 不存在/乱码/空/未闭合全优雅，真实 full.md 无误报 |
| ④ 融合度 | ✅ 无硬编码、风格一致 |

### 修复的 bug
- mistune 对未闭合代码块"自动闭合"→ 改用"围栏奇数计数"检测

---

## 四、T2 camelot 表格复核

### 实现
- 新增 `table_recheck.py`（camelot 2.0.0，stream/lattice 双试 + accuracy 质量评分）
- 低于 80% accuracy 的表格标记低置信，写 table_review_hint
- 接入 `verify_output()`（仅 PDF ≤200 页启用，避免大文档卡死）

### 4 轮审核
| 轮 | 结果 |
|---|---|
| ① 完成度 | ✅ 真实 PDF 复核、漏检标记、文件不存在处理 |
| ② 副作用 | ✅ verify_output T1+T2 双钩子跑通真实 PDF 无误报 |
| ③ 隐藏bug | ✅ Office/大PDF/文件不存在 3 类边界全优雅 |
| ④ 融合度 | ✅ 无硬编码、导入方式统一 |

---

## 五、T3 MixTeX 公式复核（已砍，诚实决策）

### 尝试过程
1. **MixTeX**：PyPI 无 `mixtex` 包（调研报告写的 pip 命令不存在）→ 无法安装
2. **换 Pix2Text**：独立 venv 安装成功（T.Pix2Text_FormulaOCR_Env_v1.1.6），实测整页识别

### 实测结论（为什么砍）
| 需要的能力 | Pix2Text 实测 |
|---|---|
| 公式图→LaTeX 复核（跟 UniMERNet 比对）| ❌ 不做（整页识别，非公式级）|
| 识别准确性 | ⚠️ 有错字（"Matrices"→"Mlatrices"）|
| 作为第二引擎 | ❌ 比 MinerU 弱，交叉验证价值存疑 |

**决策**：不硬塞无用功能，**T3 砍掉**。Pix2Text venv 保留不删（不碍事）。若未来做真正的第二引擎，应选 marker/surya（单独立项）。

---

## 六、T4 pikepdf 坏 PDF 急救

### 实现
- 新增 `pdf_repair.py`（pikepdf 10.11.0）
- 能力：空密码加密去加密、损坏恢复（attempt_recovery）、真加密标记人工
- 接入 `convert_block()` 切片前急救

### 4 轮审核
| 轮 | 结果 |
|---|---|
| ① 完成度 | ✅ 正常/空密码加密/真加密/损坏 4 场景全对 |
| ② 副作用 | ✅ convert_block 急救分支（真加密跳过/损坏恢复/空密码不误触发）|
| ③ 隐藏bug | ✅ 不存在/目录当文件/空文件全优雅 |
| ④ 融合度 | ✅ 无硬编码 |

### 修复的 bug
- pikepdf 10.x `strict` 参数不存在 → 改用 `attempt_recovery`

---

## 七、T5 Pandoc 多格式导出

### 实现
- Pandoc 便携版 3.10.1 解压到 `AAA.Tool\T.Pandoc_Convert_Env_v3.10.1`
- 新增 `export_md.py`（docx/html/epub/pptx 导出，cd 到 md 目录保图片路径）
- 支持 --to / --out 参数

### 4 轮审核
| 轮 | 结果 |
|---|---|
| ① 完成度 | ✅ docx(含图1.7MB)/html/epub/pptx 全导出成功 |
| ② 副作用 | ✅ 独立脚本，不影响主流程 |
| ③ 隐藏bug | ✅ 空md/乱码md/自定义out/不存在/不支持格式全优雅 |
| ④ 融合度 | ✅ 仅 PANDOC 一个工具路径常量（合理）|

### 修复的 bug
- 自定义输出路径失败 → 输出改用绝对路径

---

## 八、全量回归验证（F1 最终）

| 验证项 | 结果 |
|---|---|
| 4 补丁模块全部可导入 | ✅ |
| 全部脚本语法 | ✅ 6 脚本全 OK |
| mineru_day.py dry-run | ✅ 云端脚本未被破坏 |
| plan.json 数据完整 | ✅ 25 天普通 + 186 块复杂 |
| 测试残留清理 | ✅ 全部归档/删除 |

---

## 九、安装的依赖清单

| 依赖 | 位置 | 版本 |
|---|---|---|
| mistune | 系统 Python | 3.3.4 |
| camelot-py[base] | 系统 Python | 2.0.0 |
| pikepdf | 系统 Python | 10.11.0 |
| Pandoc | AAA.Tool\T.Pandoc_Convert_Env_v3.10.1 | 3.10.1 |
| Pix2Text（T3 用，保留不删）| AAA.Tool\T.Pix2Text_FormulaOCR_Env_v1.1.6 | 1.1.6 |

> 注：系统 Python 指 `C:\Program Files\Python312\python.exe`（脚本运行环境，fitz 所在）。

---

## 十、遗留事项 / 建议

1. **第二引擎**（真需求，未做）：建议 marker/surya，单独立项，非本期
2. **图片处理**：交给 media-to-notes 后续处理（用户已定）
3. **网页/HTML 入口**：走云端 MinerU-HTML（用户已定，脚本需加 --html 分支，后续）
4. **质检门禁量化**（ParseBench 思路）：未来可建中文教材小评测集
