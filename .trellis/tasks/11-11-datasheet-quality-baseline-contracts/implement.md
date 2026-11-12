# Datasheet 质量基线、表格与状态合同实施计划

## 进入实施

本任务经用户审阅后进入 `in_progress`。基线见[执行记录](validation.md)，整件修复见[目录公式验证](toc-formula-verification.md)，上游标记与人工校核见[表头来源](table-header-review.md)，实时服务与人工采集见[英译中实测](en2zh-validation.md)。

本阶段先复算和核对七组指标（Q2），再补齐 `canonical-table/v1` 的跨样本结构对照（Q3）。每个偏差先记录可复现输入、预期和实际、受影响指标、定位层级及证据。按共用处理环节形成后续修复批次，使用能覆盖同类问题的最小用例与多份样本验收。[问题清单](issues.md)

## 1. 建立样本与基线（AC1～AC3）

- [ ] 核对当前工作基线、正式转换链路和历史清单。把现有四个 P0 样本及报告口径作为对照，逐项核对新增样本的来源、许可、可用性、SHA-256 和模式。
- [ ] 确定至少两份不同的非 OPA228 数据手册以及连续跨页范围。为表格、Token 和页面区域建立独立标注，为阻断负例写入预期定位与原因码。记录仅有组件夹具的样本及缺少正式源件的候选。
- [x] 固定计划和既有观测接入七组指标统一复算。按运行保留观测指纹、分组、分母和缺测原因，人工数据使用绑定 DOCX 的独立回填文件。[计算与复算](metrics-implementation.md)
- [x] 定向覆盖分母、缺件、超时、不可打开 DOCX、预期阻断、重复 Token、页面匹配失败、人工缺测和人工记录绑定，保留原始观测和口径版本。
- [x] 常规 Golden Sample 回归从固定清单采集任务终态、主 DOCX、成功及失败耗时和可归因费用，并输出七组指标。使用原 P0 四份 PDF 和本地回环服务验证采集到复算。[常规回归出表](metrics-implementation.md#常规回归出表)
- [ ] 先执行本地组件与离线回放，产出基线和失败矩阵。正式 PDF 验收使用隔离测试环境，按授权运行 direct 与英译中。人工核对绑定初次产物及对应的审核轮次，每轮保留被审核产物的指纹。未取得授权或样本、渲染环境、账单、人工记录缺失时，在报告中标明影响的指标和剩余验收。

## 2. 收敛复杂表格（AC4、AC6）

- [ ] 将样本映射到来源逻辑表、Grid、渲染计划和 OOXML 输出。用独立标注对照跨度、表头、来源顺序、跨页拼接和重复表头处理，区分原生、按合同拆分、降级和缺失。
- [ ] 用现有 `app/services/tables/` 和 `app/services/renderer/logical_table_plan.py` 对照独立标注、源 Grid、渲染投影和实际 OOXML。将可归因的偏差登记给对应处理环节，区分缺少来源语义、结构投影差异和实际写入差异。保持源数据和当前渲染视图各自的版本绑定。
- [ ] 对照已有真实样本和小夹具，覆盖宽表、多级表头、正常跨页续表及缺片段。记录每种风险的实际 OOXML、可编辑性、覆盖层级和质量状态。修复批次形成后，按受影响合同选择定向回归。
- [x] 首批处理复合表号：源归组器确认相同完整编号，渲染计划复用同一题注判定。合并正例、相邻独立反例、TPLD2001 原始 v2 与两段完整 HTML、真实缺片段负例均已对照 Grid、投影及 Word。[首批复验](continuation-contract-validation.md)
- [x] 预合并来源绑定以 TPLD2001 原始 MinerU 包和 SN74AC244 缺片段负例复验 Grid、Word 和质量证据。原始结构基线保留。[来源绑定复验](upstream-table-coverage-validation.md)
- [ ] 人工指标待审阅回填，翻译版视觉偏差待同模式批准基准。

## 3. 明确并验证状态合同（AC5、AC6）

- [ ] 用当前 API、状态所有者与仓储提交入口对照 CON-103/104、QA 和 REL 的相关条目。记录每一条合同的状态集合、转换触发者、绑定证据、兼容读法和失效原因。把通过验证的合同写回已有设计、API 文档和适用 Spec。
- [ ] 在已支持的任务入口验证正常发布、质量阻断、待审草稿、旧批准失效、相同请求重放、冲突重放、证据变更、权限拒绝和发布后固定产物。分别核对列表资格、详情可操作性与最终提交。对已复现的并发差异，核对仓储提交、审核及文件保护的原子边界，按受影响 adapter 定向验证。
- [ ] 现有行为满足合同的路径，以文档和已有测试证据验收。若要改变公开状态含义、权限、存储 schema、历史迁移或发布策略，先形成可审阅的影响及兼容方案。

## 4. 验证入口与证据（AC1～AC6）

按实际改动选用以下现有测试入口。新增用例放在相应所有者的测试中，并记录精确执行命令与结果。

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_golden_sample_manifest.py'
.venv/bin/python -m unittest discover -s tests -p 'test_local_mineru_quality_matrix.py'
.venv/bin/python -m unittest discover -s tests -p 'test_document_ir_word_renderer_layout.py'
.venv/bin/python -m unittest discover -s tests -p 'test_formal_mineru_render_evidence.py'
.venv/bin/python -m unittest discover -s tests -p 'test_protected_tokens.py'
.venv/bin/python -m unittest discover -s tests -p 'test_document_job_delivery_state.py'
.venv/bin/python -m unittest discover -s tests -p 'test_document_job_delivery_state_api.py'
.venv/bin/python -m unittest discover -s tests -p 'test_document_job_list_publish_light_check.py'
```

- 组件回放使用 `scripts/dev/run_component_pdf_regression.py --manifest <组件清单> --sample-id <样本ID>`，适用现有 MinerU 夹具。基线与修订版使用相同输入和版式配置，分别记录代码提交。
- 真链路使用 `scripts/ops/run_golden_sample_regression.py` 指向获准的隔离目标，使用 `GOLDEN_SAMPLE_BASE_URL`、`GOLDEN_SAMPLE_MANIFEST` 和 `GOLDEN_SAMPLE_RUNS_DIR` 绑定本次运行。先核对样本、目标和认证，按批准范围运行样本及人工签字。实际服务和渲染器证据分别记录。
- 若触及公开响应或前端动作，按已有 Spec 验证 OpenAPI 快照或动作契约。触及原子写入、文件保护或权限合同且有具体未决风险时，对候选 diff 做独立只读复核。保留分支状态、受影响路径和验证范围。
- 汇总版本化基线、样本覆盖、预期与实际差异、定向检查和签字状态。历史发布结论只绑定原运行，外部前提缺失的验收保留实际状态。父任务引用子任务证据并负责跨任务集成。

## 回退与风险

- 样本、人工标注、指标口径和基线结果均按版本追溯。修订或回退用对应清单和运行版本复算，保留已有历史报告。
- 重点核对 Grid 身份域、技术 Token 归属、审核有效性和发布提交的引用边界。按各改动所属提交局部回退，保持已发布记录、历史审核和绑定文件的可追溯性。
