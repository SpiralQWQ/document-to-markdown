# 开源发布验收报告 · document-to-markdown v0.4.0

> **版本**: v0.4.0 · **日期**: 2026-08-13 · **状态**: ✅ 通过（可发布）
> **范围**: src/dtmd 结构重构 + 统一 CLI + 三层质检系统 + 隐私清理 + 文档规范化
> **流程**: S1 穷举闭包 → S2 防呆全路径 → S3 逐 Task 4 轮审核 → fixloop 5 轮 scan+修 → final 验收

## 一、交付物

### 结构（src 布局，SoC 目录契约）
```
src/dtmd/
├── __init__.py / __main__.py / cli.py   # 统一 CLI（python -m dtmd，7 命令）
├── config.py / utils.py                 # 路径配置（无硬编码）/ 纯工具
├── convert/                             # 转换域：base(公共) / local(本地) / cloud(云端) / local_batch
├── quality/                             # 质检域：gates(检查器) + levels(L1/L2/L3) + vision/sample/rework/report
├── export.py                            # 导出域（Pandoc 多格式）
└── tools/                               # 运维：watchdog/check_done/clean_hook/glm_proxy
```
根目录**零散落 .py**（顶级开源规范）；文档齐备（README 中英/CHANGELOG 中英/CONTRIBUTING/CODE_OF_CONDUCT/LICENSE/COMMERCIAL/pyproject）。

### 统一 CLI（7 命令）
`python -m dtmd convert|l1|l2|l3|rework|report|list` + `--version`/`--mode local|cloud`。

## 二、过程（S1-S4 + fixloop）

| 环节 | 结果 |
|---|---|
| S1 穷举闭包 | 16 个 Task（骨架/config/utils/转换域/质检域/CLI/收尾/验收） |
| S3 逐 Task 4 轮审核 | 每 Task 完成度/回归/隐蔽缺陷/质量 4 轮，过才进下个 |
| S2 防呆全路径 | 缺数据友好提示/负数校验/非法参数/源缺失跳过/zip-slip 防护 |
| fixloop 5 轮 scan+修 | **73 个问题**（HIGH 功能 bug / 连锁 bug / 隐私高危 / 文档边角）全部修复 |
| 证据单 | `temp/fixloop_evidence/round_1~7.md`（每轮 现象→根因→修复→影响） |

### fixloop 抓到的关键问题（部分）
- CLI `--max`/`--limit` 参数歧义/不透传（终点一致破坏）
- cloud day-parse 被 flag 值污染（连锁 bug）
- local_batch 超时公式错误 + 多片输出覆盖
- zip-slip 解压路径逃逸（含 Windows 盘符相对）
- **隐私高危：内部验收报告/私有统计随仓库发布 → 已删**
- **git 未提交（发布即破）+ paths.py 机器路径历史泄漏 → 已提交 + filter-branch 清理 + force-push**

## 三、隐私与安全（红线核验）
- 无硬编码绝对路径/密钥（全部环境变量：DTM_*/MINERU_API_TOKEN/GLM_API_KEY 等）
- 无机器路径名（T.* 目录命名已清）
- **git 历史已清理**（paths.py + 机器路径从全部历史移除，force-push 到 GitHub）
- 源码/文档**零私有项目数据/书目/真实统计残留**
- zip-slip 解压防护（绝对/../盘符相对成员全过滤）

## 四、回归与验证
- 20 模块 import 全通 | tests 15 passed | 全部文件语法通过
- 终点一致性：`cloud.already_done IS base.is_done`、`blocks.safe IS utils.safe`、`cloud 与 local 共用 compute_out_dir`
- git：3 提交（f0480ca/d0c60a0/5b75d1e），工作树干净，远程同步

## 五、已知局限（诚实声明）
1. **穷举扫描永无止境**：fixloop 5 轮后仍可能发现文档边角项（scan 是穷举式，收敛判定难以正式满足）。已接受当前强状态，边角项记入 backlog。
2. `local_batch.py` 多片大文件输出到 `_s{j}` 子目录（防覆盖），未做片间 full.md 拼接合并。
3. `mineru_local_batch.py` 从 v0.1.0 保留的 `-m auto` → 已改 `-m ocr`（强制 OCR 理念对齐）。
4. L3 视觉复审依赖外部 `vision_analyzer.py`（需 `DTM_VISION_ANALYZER` 环境变量指向）；仓库不随附该脚本。
5. `DTM_ROOT` 在 pip 安装场景需显式设置（src 布局根解析依赖）。

## 六、结论

**验收通过**：document-to-markdown v0.4.0 达到开源发布标准——结构符合 SoC 目录契约、统一 CLI、三层质检、隐私红线守死、git 历史干净、文档规范化齐备。**可发布**（已推送 GitHub origin/master）。
