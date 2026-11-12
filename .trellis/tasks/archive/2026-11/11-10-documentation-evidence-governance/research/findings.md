# 文档清点与证据边界

日期：2026-11-10。范围：规划阶段对本地文件与既有任务记录的只读核对；没有应用或生产验证。本文件保留该阶段快照，后续实施范围与实际结果见任务 progress.md 及分批记录。

## 1. 清单来源

`document-inventory.json` 基于 Git 跟踪文件和非忽略的新增文件，纳入 docs Markdown/YAML、根 README／DOCUMENTATION-MANIFEST、Docker README、trellis-bootstrap Markdown 及 tests/fixtures Markdown，共 134 份：133 份已跟踪、1 份为卫生任务已有新增文档。内容身份取当前工作区字节，不是纯 HEAD 快照。

| 批次 | 数量 | 当前核对程度 |
|---|---:|---|
| B1 | 10 | 抽查核心漂移和权威入口；尚未全面核验这 10 份正文。 |
| B2 | 21 | 枚举并读取元数据；目标设计和计划正文待逐份核验。 |
| B3 | 51 | 枚举并读取元数据；正文与命令待逐份核验。 |
| B4 | 52 | 枚举并读取元数据；提示词与模板只记录用途类别。 |

72 份已有 frontmatter 或 YAML 顶层元数据；134 份中均未发现顶层 doc_status、last_verified_commit 或 owner。元数据计数不涉及正文真伪。新增治理说明不计入这份现有资料快照，实施时另行补入。

## 2. 已核对差异

| ID | 类别与结论 | 源文件定位 | 不能外推的结论 |
|---|---|---|---|
| F01 | 当前说明问题：Docker README 的依赖安装描述与生产 Dockerfile 不符。 | `docker/README.md:10`；`docker/prod/Dockerfile:15-19` | 没有构建镜像或证明生产正在使用该版本。 |
| F02 | 历史调查：gap 明确只局部复核，其他条目保留旧基线。 | `docs/implementation/current-gap-analysis.md:1-14` | 没有全面证明旧缺口仍然存在。 |
| F03 | 当前静态实现：扩展阶段类型已经存在；产品 Manifest 仍将 CON-102 记为 todo。 | `app/domains/document_jobs/models.py:19-32`；`docs/implementation/codex-task-manifest.yaml:48-59` | 类型存在不能证明完整调用流程、所有 AC、人工接受及当前部署。 |
| F04 | 当前静态实现：已有 TableContextBuilder 接入并受 table_context_enabled 开关控制；Manifest 的 TR-404 仍为 todo。 | `app/domains/translation/document_ir_translator.py:340-350`；`docs/implementation/codex-task-manifest.yaml:300-311`；`docs/implementation/current-gap-analysis.md:68` | 接入不证明启用或语义质量，不能直接把 TR-404 改为 done。 |
| F05 | 文档声明通过：Golden 报告记载 release 20d496e 的四样本自动回归和人工签字。 | `docs/testing/pdf-to-word-golden-sample-acceptance-report.md:15-31` | 本轮没有核看或重跑原始运行证据，也不能证明当前 HEAD 或线上通过。 |
| F06 | 现有机制：权威清单区分目标文档、任务状态与当前事实，并保留人工接受门。 | `DOCUMENTATION-MANIFEST.md:44-53`；`docs/README.md:47-61` | 不能认为项目从零缺少文档治理。 |

## 3. 既有任务与重叠

- `.trellis/tasks/11-06-source-audit-remediation-plan/design.md:43-49` 已定义 B01；其 `progress.md` 的派单表记录局部修正文案通过。本任务复用已存在修正，不把该表当成当前所有文件状态的证明。
- `.trellis/tasks/11-10-repository-hygiene/verification.md:3-15` 记载个人路径治理和本地检查，当前仍有未提交变更；不重做其产品改动、历史测试或扫描。
- `.trellis/tasks/11-06-source-audit-remediation-plan/progress.md` 记录 B06 默认关闭及开启边界；本轮没有检查生产开关。
- 当前分支的翻译批次提取会改变执行器调用位置。后续文档核验应刷新入口与 SHA，不能把原行号长期作为唯一证据。
- 本任务是上述局部修正之外的统一字段与文档迁移规划；不修改相关旧任务和产品 Manifest 的执行状态。

## 4. 消费方与工具观察

对 `scripts/`、`.trellis/scripts/`、`tests/` 做了 baseline_commit、last_reviewed、doc_type、frontmatter、codex-task-manifest 的定向搜索，未发现这些顶层文档字段的直接业务消费方。这不是证明仓库外没有消费者；实施前仍应检查实际变更格式，保留原键值与业务结构。

系统 python3 未安装 PyYAML；项目 `.venv/bin/python` 已可导入 PyYAML。规划清单通过现有 PyYAML 读取 frontmatter／YAML，未安装依赖、调用业务启动入口或导出 OpenAPI。生成清单的内联脚本没有持久化为新工具。

## 5. 工作区保护

建项前 Git porcelain 展开到单个未跟踪文件后共 245 条 dirty 路径；这与初次按目录聚合显示的 177 项属于同一工作区。本地存档的基线记录路径、内容身份和 index 条目摘要。后续验证比较实际文件身份，不靠条目数量推断保护成功。

本轮只新增任务目录资料；Trellis create 的会话任务指针由官方脚本管理。没有 task start、archive、add_session、staging、commit、push 或生产动作。
