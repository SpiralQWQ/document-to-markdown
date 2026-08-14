# 开源发布验收报告 · document-to-markdown v0.3.0（文档规范化整改）

> **版本**: v0.3.0 · **日期**: 2026-08-13 · **状态**: 通过（可发布）
> **范围**: README/README_zh 规范化整改 + 社区文档补齐 + 打包元数据 + CHANGELOG 完善
> **流程**: S1 穷举闭包任务清单 → S3 逐 Task 4 轮审核 → S4 全量回归

## 一、整改背景

对标 GitHub 顶级开源项目文档规范（README badges/TOC/特性区、CONTRIBUTING、
CODE_OF_CONDUCT、pyproject.toml、Keep a Changelog），将本仓库文档从"够用"
提升到"专业开源标准"。同时补上 v0.3.0 新增的 `qa_runner` 质检系统文档（此前
代码已同步、文档缺失）。

## 二、交付物（12 Task + 1 验收，全部完成）

| Task | 内容 | 审核轮次 | 抓到的缺陷 |
|---|---|---|---|
| 01 | README 顶部：badges + TOC + 标题区 | 4轮 | logo.png 破图引用 |
| 02 | README Features 特性区 | 4轮 | — |
| 03 | README Files 表补 qa_runner + qa/ | 4轮 | — |
| 04 | README QA 质检系统章节 | 4轮 | — |
| 05 | README Configuration env 参考表 | 4轮 | — |
| 06 | README FAQ / Troubleshooting | 4轮 | — |
| 07 | README Roadmap + Contributing | 4轮 | — |
| 08 | README_zh.md 全量同步（16 章节对齐） | 4轮 | — |
| 09 | CONTRIBUTING.md 新建 | 4轮 | — |
| 10 | CODE_OF_CONDUCT.md 新建 | 4轮 | — |
| 11 | pyproject.toml 新建 | 4轮 | export extra 误列 pandoc(pip 无此包) |
| 12 | CHANGELOG [Unreleased] + docs 检查 | 4轮 | — |
| 13 | 本验收报告 | — | — |

**4 轮审核共抓出 2 个缺陷并修复**（logo 破图、pandoc extra 误导）。

## 三、验证结果（S4 全量回归）

| 检查项 | 结果 |
|---|---|
| README EN/ZH 章节数 | 各 16 章节，**中英对齐** |
| README TOC 锚点 vs 实际标题 | EN/ZH **全部匹配**（无死链）|
| badges（shields.io）| 6 个，链接有效 |
| pyproject.toml | TOML 有效，6 包 + paths.py 全部存在 |
| 社区文档 | CONTRIBUTING / CODE_OF_CONDUCT 齐备 |
| CHANGELOG | Keep a Changelog 规范 + [Unreleased] |
| 隐私红线 | 无机器绝对路径 / 密钥泄露 |

## 四、已知说明

- README 语言选择器链接到 CONTRIBUTING.md / CODE_OF_CONDUCT.md（已创建）
- pyproject.toml 为**可选打包元数据**，仓库仍以 requirements.txt 为运行依赖
- logo.png 未提供（README 用文字标题 + badges，不引用破图）

## 五、结论

**验收通过**：document-to-markdown v0.3.0 文档规范化整改完成，12 个 Task 全部
达标、2 个缺陷修复、中英文档结构对齐、TOC 无死链、社区文档齐备，达到 GitHub
顶级开源项目文档规范水平，**可发布**。
