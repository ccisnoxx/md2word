# B3 独立文档复核

日期：2026-11-10。范围：B3 的 51 份资料、准备记录及必要静态入口；复用 B1/B2 不变证据。本复核仅写本报告，不改维护文档、API Manifest、业务源码或任务状态。

结论：**B3 的 51 份文档候选通过独立复核。** 一项准备记录的 P3 统计口径已由实施方修正，未发现本批引入而未关闭的缺陷；两条既有断链按授权边界保留。

## Findings (fixed)

- 文件：`research/b3-preparation.md:67–74`。
- 问题：document-jobs 原将主 router 的 24 项称为“本文件直接装饰器数量”，易被误读为文件内全部静态声明；实际另有 9+2+4 项子 router 声明。
- 修复：已反馈主会话，由实施方将文件级数改为 **39**，明确列出 24+9+2+4 组成及其他文件/动态注册不在该计数内。复核方已读取修订后的文字，与直接 AST 观察一致；未改 API 实现或 API 文档，也没有运行应用。

## Findings (not fixed)

无本批引入而未关闭的问题。以下为实施前已经存在的断链，按任务的范围纪律保留，没有顺带更改历史引用：

- `docs/api/document-jobs.md:87` 引用 CON-102 归档目录的 `receipt-validation.md`，该本地目标不存在。
- 同文档引用同一目录的 `receipt-review.md`，该本地目标不存在。

两个目标的完整相对路径已在 b3-implementation.md 的“既有断链与准确边界”逐项记录。它们影响从 API 页面直接打开原回执，但不能据此否定历史验证，也不能声称已经读取这些不存在的本地文件。B2 已另以可读 Git 对象定位相关历史证据；本轮不扩展为历史归档修复。

## 已完成的独立核对

| 范围 | 观察与结论 |
|---|---|
| 7 份 superseded | 对照实施前原文，Jobs API 明确移除并转 Files + Document Jobs；DocumentIR v1、模板配置包、术语 SQL、AI 审计和翻译术语 v1 均有明确替代入口；PDF 在线总结占位原文也已指向架构/计划与 backend runbook。分类依据原内容，不是按日期批量归档。 |
| 2 份 draft | backend-architecture-baseline-and-issues 原 status=draft，标题注明初稿、正文保留 2026-05-28 legacy Jobs 基线；backend-design-implementation-plan 原 status=draft，summary 明确设计草案。保留旧 checklist 和历史事实，不将其升级成现行已接受方案。 |
| historical 与模板 | term-assets-sql-versioning-tasks 是没有现行任务说明的历史占位，没有擅造替代 AC；两份旧质量报告分别绑定 20260602T071017Z 与 20260603T070724Z。联调计划含 2026-06-10 旧执行节，空白验收模板仍是可维护程序资料，不被当作已签字记录。 |
| API Manifest 的旧字段 | guides 中在线总结仍 current、两个 term-assets 主题仍 approved，确与对应 deferred 正文有区别；mineru-callbacks.source_files 指向的 mineru_callback.py 当前不存在。准备记录正确将其限定为索引/路径差异，既不改原业务对象，也不以索引旧状态覆盖正文用途。 |
| API 入口 | 直接读取 v1 聚合 router，17 个本批现行 family 均有挂载，旧 Jobs 未挂载；示例方法/路径均可由装饰器定位。仅作静态声明核对，未导入应用、生成 OpenAPI 或验证鉴权。原 P3 数量口径已修正，不据此扩成全 API 审计。 |
| 旧启动与 callback 示例 | 根 run_api.py/run_worker.py、旧 run_stage_worker.py 不存在，正式 scripts/dev 入口存在；runbook 指向对应入口。identity guard 不验证额外 token，checksum 路径使用 uid/seed/content。准备记录所述旧提示与现行参考的差异成立，未引入新的鉴权结论。 |
| 正式上传与组件修复入口 | Files router 的 upload_file_content 回落路径存在；P0 联调页的外部 presigned 条件不证明当前启用。组件 README 的旧 app/conversion 提示与维护治理页的 DocumentIR/renderer/共享规则入口有差异，适合用导语链接限定而不改历史步骤。 |
| 脚本/样本 | 静态查看正式启动、迁移薄入口与已复核验收脚本；未执行文中命令、main 或 --help。Golden 4 个 canonical ID、P1 3 个 ID 和 target_sample_count=3 均有声明，available 不作为运行结果。 |
| 41 份静态输入 | 独立计算准备记录中的 41 个 SHA-256，全部匹配；与 HEAD 相同、既有未提交差异和未跟踪的关系也一致。文件身份不代表全文件审计，仍按局部入口范围解释。 |

## 51 份最终候选

已读取 51 份原文相对实施前只读副本的完整差异：均仅增加治理字段与明确导语，API Manifest 仅增加顶层字段，既有卫生说明仅追加 frontmatter。没有移除或改写旧正文、历史命令/结果/样本/job/hash、旧 checklist 或业务对象。

新增范围说明准确区分 API 的挂载/声明与响应/权限/副作用实跑，维护程序与运行证据，草稿与冻结合同，以及历史 blocked/未通过结论与新批次验收。替代页给出真实替代入口，PDF 在线占位所引的两份旧架构/计划明确注明仍为草稿。所有核验提交与 owner 保持 null，未用统一 HEAD 或默认人类责任人补齐。

51 份文档当前 SHA-256 全部匹配 b3-implementation.md 的交接表；实施报告与修订后的准备记录也匹配主会话交接的内容身份。解析、链接和保持检查的相关输入未变，可以直接复用。没有产品实现合同变更或需要另写 .trellis/spec/ 的新实现约束，治理规则继续由 B1 文档承担。

## Verification

- 生命周期、精确新增范围与重点静态边界：独立复核完成，P3 统计口径已修正。
- 51 份最终候选的 YAML/frontmatter、原字段、类型/枚举和新增链接/锚点检查：通过，复用实施方一次性 B3 定向检查；selected=51、errors=[]、新增断链0，两条既有断链单列。生命周期为39 active、7 superseded、3 historical、2 draft。
- 原文和业务对象保持：通过，复用剥离新增块后的51份精确字节比较和两个 docs Manifest 全业务对象比较；独立阅读的精确差异与该结果一致。卫生页仅元数据，未改原扫描结论。
- 范围和工作区保护：复用已交接的显式文件卫生及 diff 检查；B1/B2 32份候选与 B4 52份原文未变。245条原 dirty 中225条不变，累计20条为授权文档叠加，范围外变化0、index摘要不变；复核方没有修改这些文件。
- 本复核报告的格式、相对链接与文件卫生：通过，仅检查报告本身，不重跑整批文档验证。
- Lint / TypeCheck / 应用测试：不适用，未运行。
- 构建、CI、发布脚本、Docker、生产访问和依赖安装：未执行。
- 没有 stage、commit、push、archive 或 add_session。没有 Python 变更或 Python 注释/docstring/运行输出变更；新增报告使用中文。
