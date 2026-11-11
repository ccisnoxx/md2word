# Datasheet 质量基线、表格与状态合同实施计划

## 进入实施

本任务经用户审阅后进入 `in_progress`。当前观测、验证和待补证据见[执行记录](validation.md)。开发按下列顺序交付，当前分支已有行为用对应验收证明复用，证据暴露的偏差进入有界修改。

## 1. 建立样本与基线（AC1～AC3）

- [ ] 核对当前工作基线、正式转换链路和历史清单。把现有四个 P0 样本及报告口径作为对照，逐项核对新增样本的来源、许可、可用性、SHA-256 和模式。
- [ ] 确定至少两份不同的非 OPA228 数据手册以及连续跨页范围。为表格、Token 和页面区域建立独立标注，为阻断负例写入预期定位与原因码。记录仅有组件夹具的样本及缺少正式源件的候选。
- [ ] 基于现有回归脚本接入扩展清单和指标报告。优先复用样本清单、报告、DOCX 检查、人工签字与翻译审计数据，补齐固定分母、指纹、缺测、分组和重算所需字段。新增报告口径单独版本化，保留 P0 报告与签字读法。
- [ ] 用固定夹具验证分母、缺件、超时、不可打开 DOCX、预期阻断、重复 Token、页面匹配失败及人工缺测等边界。保留原始数据、汇总及计算所用口径。
- [ ] 先执行本地组件与离线回放，产出基线和失败矩阵。正式 PDF 验收使用隔离测试环境，按授权运行 direct 与英译中。人工核对绑定初次产物及对应的审核轮次，每轮保留被审核产物的指纹。未取得授权或样本、渲染环境、账单、人工记录缺失时，在报告中标明影响的指标和剩余验收。

## 2. 收敛复杂表格（AC4、AC6）

- [ ] 将样本映射到来源逻辑表、Grid、渲染计划和 OOXML 输出。用独立标注对照跨度、表头、来源顺序、跨页拼接和重复表头处理，区分原生、按合同拆分、降级和缺失。
- [ ] 优先在现有 `app/services/tables/` 和 `app/services/renderer/logical_table_plan.py` 的所有者处处理已复现偏差。复用表格证据和现有质量归属，检查关联的表格翻译上下文是否依赖被改变的坐标或 ID。保持源数据和当前渲染视图各自的版本绑定。
- [ ] 在出错路径增加定向回归，验收同一份产物的实际 OOXML 和可读技术内容。复核大表、合并表头、连续页、缺片段各自的预期质量与内部草稿行为。

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
