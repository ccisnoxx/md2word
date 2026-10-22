# DocumentJob 模式与 direct 资源合同

## 1. 范围与触发

修改任务模式、创建 schema、资源绑定、重试/克隆或任务配置 UI 时适用。后端模式 owner 是 `app/domains/translation/modes.py`，前端名称/能力 owner 是 `frontend/src/utils/format.ts`；避免在入口各自复制模式表。

## 2. 接口

- `POST /api/v1/document-jobs`：`mode` 或 `translation_mode` 选择模式。
- `POST /api/v1/document-jobs/{id}/retry`：保持模式与 generation 合同。
- `POST /api/v1/document-jobs/{id}/clone`：保持源任务模式，新任务 ID；不是模式切换接口。
- `GET /api/v1/document-jobs/config-summary`：只读资源摘要，包含四方向元数据，不执行翻译。

## 3. 请求、响应与展示

规范值为 `direct/en2zh/ru2zh/zh2en/zh2ru`，分别对应既有五种 `*_pdf_to_word` mode。用户名称为“原文 PDF 转可编辑 Word”、英译中、俄译中、中译英、中译俄。

- 历史 `zh2zh`、`zh_to_zh` 仅在服务端输入归一为 direct。请求 schema 在 Literal 前处理明确 alias；OpenAPI/前端枚举保持五值，响应/snapshot/event 保存规范值。
- direct 使用模板、MinerU、符号与排版规则，不调用翻译术语服务、Profile payload/Prompt 解析、Provider 或翻译批次服务。符号规则 `term_rule_set` 不属于翻译术语。
- direct 的新请求不接受非空 `term_version_id`、`translation_term_set_id/version`、`translation_profile_id/version`。校验必须在翻译加载与 mutation 前，但仍保留权限/状态检查优先级。
- 历史 direct 快照可读；默认 retry、keep-source clone 的惰性字段不重新加载或回写清理，源任务与审计保留。
- direct UI 隐藏翻译资源、Prompt/模型、Provider/AI 调试区，折叠快照也使用只读投影。不能改响应原对象或用隐藏代替后端授权。
- 克隆追溯中的 `clone.source_term_version_id` 也属于翻译字段，direct 展示副本仅移除该字段，保留来源任务、模板和策略；翻译任务仍完整展示。
- 只过滤已知翻译资源 warning；未知 warning、P0 blockers、模板/符号规则错误保留。翻译方向缺资源继续禁用。
- 页面动作消费后端 `available_actions`；模式能力不用于推断发布资格，不增加前端状态机。

## 4. 验证与错误矩阵

| 条件 | 结果 |
|---|---|
| alias 单字段/与 direct mode 相符 | canonical direct；正常权限和源文件验证。 |
| 规范化后双字段冲突 | 400 `invalid_request`。 |
| 未知、空串、非法类型 | 422 `validation_error`，不静默变 direct。 |
| 有权限的 direct 新请求显式翻译资源 | 400 `invalid_request`，零加载/绑定/投递副作用。 |
| 无资源重选权限 | 保留现有 403。 |
| Operator debug true / Admin direct debug true | 403 `role_forbidden` / 400 `invalid_request`。 |
| 必需 P0 执行链未就绪 | 503 `document_jobs_not_ready`。 |

## 5. 正常、缺省与非法场景

- 正常：direct 绑定 published 模板和符号规则，生成一份主 DOCX，零 AI/批次/翻译 Artifact。
- 缺省：未给 mode/translation_mode 使用 direct；翻译默认资源缺失不构成 direct 的翻译依赖。
- 非法：direct 传显式翻译术语，不能先加载后丢弃；未知模式不能回退 direct。

## 6. 必要测试

- `tests.test_document_job_modes`：真实请求 schema alias、双字段与非法输入、direct 零翻译加载/单 DOCX、拒绝无 mutation、历史 retry/clone。
- `tests.test_fastapi_jobs_backend`：复用四方向资源、语言匹配、debug/owner 权限和正式 Worker 回归。
- `frontend/src/utils/format.test.ts`、`documentJobConfig.test.ts`：模式能力、精确 warning 过滤、投影不修改输入。
- mock API UI smoke：两角色 direct 创建/详情、翻译切 direct payload、展开快照隐藏、长文案宽度与键盘。
- OpenAPI 由 `scripts/ops/export_openapi.py` 生成，`check_release.py` 检查；不得手改生成 JSON 或放宽断言。

## 7. 错误与正确做法

错误：schema 先以五值 Literal 拒绝历史 alias，只在 service 内做归一；或 direct 先调用翻译术语服务，再把结果设为 None。

正确：输入 alias 在 schema 类型检查前归一；应用层 direct 在进入翻译依赖前结束该分支。

```python
# 原文转换只解析普通转换资源，历史被动字段不能激活翻译加载。
if not spec_for_document_job_mode(mode).is_translation:
    return None
```

UI 同样先按共享模式能力判断是否展示，再构造展示副本；不能用删除后端 snapshot 字段来隐藏配置。

## 8. 执行阶段与恢复合同（CON-102）

CON-102路径A已获规划审核，候选按first-valid-receipt实现；实际定向证据和独立复核见当前任务receipt-validation.md/receipt-review.md。真实MySQL及部署文件系统锁语义的启用门未完成前，不得据本节直接启用生产写者。

### 8.1 范围与触发

修改 DocumentJobStage、执行/批次推进、失败定位、取消/恢复、事件或前端阶段消费者时适用。模型 owner 为 `document_jobs/models.py`，推进和事件 owner 为 `execution.py`；批次状态与主任务 stage 是不同合同。不得为拆阶段重写 Renderer/Provider 算法或提前增加质量/复核/交付状态。

### 8.2 接口与存储

- `DocumentJobRecord.stage/failed_stage`、`DocumentJobEventRecord.stage` 使用同一后端阶段类型；三个新增值为 `translating/translation_validating/quality_checking`，只与主任务 `status=running` 配对。
- GET detail/events/incidents 与 saved views 消费该合同。响应的 stage/failed_stage 仍为字符串，前端类型同步并保留未知值原文展示，筛选未知值仍拒绝。
- file/sqlite/MySQL继续保存JSON payload，内部新增prepared_result（旧记录None），文件候选复用pending_upload与协议metadata；无表列/DDL/backfill、计时字段或状态开关。OpenAPI只能通过现有生成器维护。局部原子写入的唯一规范见[Database Guidelines](./database-guidelines.md#documentjob-结果登记的局部原子合同con-102)。

### 8.3 推进与事件合同

- direct 从 ir_converting 直接进入 rendering，再经 quality_checking、uploading 完成；不得进入翻译依赖。
- 翻译在 source IR 保存后、批次投递前进入 translating；仅当前代有效叶子批次全成功或零单元空计划才能进入 translation_validating。
- translation_validating 承载现有 ID 合并和回填，不表示已具备 ProtectedToken/数字/术语算法。最终 IR 通过后才进入 rendering。
- quality_checking 承载现有 evidence/ensure，必须早于 generated_word 登记；确定性丢失的门禁与 QUALITY-004 不变。
- 新阶段事件保持 generation、trace、安全摘要与真实阶段。duration_ms 只填本次实际可测耗时；进程重启后的未知总耗时不猜值。
- 恢复入口须主动收敛已成功批次，不只依赖末批回调；旧 ir_converting 在途翻译和历史记录可继续读取/恢复。

### 8.4 验证与错误矩阵

| 条件 | 必须行为 |
|---|---|
| 新stage与queued/succeeded等错误status配对 | 模型拒绝，不静默归一。 |
| Provider/单批次校验最终失败 | failed_stage=translating，保留translation_failed与原批次预算/审计。 |
| 全量missing/extra ID；重复ID/回填错误 | failed_stage=translation_validating；分别保留translation_fan_in_mismatch或translation_failed。 |
| 翻译结果文件读取/最终IR存储失败 | 保留存储错误oss_failed，failed_stage准确，不伪装为Provider失败。 |
| DOCX evidence/完整性失败 | failed_stage=quality_checking、error_code=render_failed，主件不登记。 |
| 旧generation、取消或终态回流 | 拒绝推进，不复活任务或污染当前代。 |
| quality_checking或uploading空结果槽位且缺少可复用主件/内存bytes | 原子要求本代/最终IR及receipt仍空，记录来源后回rendering重建重验；不重复MinerU/Provider，不降低进度。 |
| uploading已有receipt | 所有调用仅物化同一file_id并按receipt完成，不再回rendering、选件或写对象；物化冲突/到期删除按uploading/oss_failed关闭。 |
| 迟到候选失败或旧快照回退 | receipt为空的原子条件拒绝其修改；不能按另一调用的current.stage误写失败。 |
| 自动发现旧代、缺代数或不同最终IR的主件 | 保留历史，但不晋升为当前结果；不能把缺失代数猜成0。 |

### 8.5 正常、旧记录与失败场景

- 正常：四方向翻译共享阶段序列，批次queued/running/split/succeeded不来回改变主任务stage；direct无翻译事件或Provider调用。
- 旧记录：保留全部旧stage和事件；明确result_file_id按既有重试语义验证所属任务、类型和可用状态后复用；扫描发现只能选择同代/同最终IR主件。
- 失败：新阶段的取消/超时/终态保护与主入口guard必须同时覆盖；不能仅加Literal而使任务滞留，也不能放宽guard跳过质量门禁。
- 并发：允许私有pending候选重复计算/写入，每个候选独立key，首次有效receipt原子选定唯一身份。receipt前的阶段/回退/候选失败要求空槽；之后只允许匹配receipt收尾。取消/timeout可胜出，retry原子换代清槽，旧调用不复活任务。不承诺整条转换exactly-once；batch仓储的既有并发边界不因此升级。
- 部署：全部读者先支持新stage并保留receipt、具备原子写入/候选可见性；旧API写者和Worker均退出后才启新写者。回滚先停止消费/相关写入、收敛或保留在途，只回上述兼容版本；兼容读者保留HEAD旧执行器时暂停全部DocumentJob消费/内联执行，不将该候选作为活跃Worker回退版本；不清洗字段/审计/文件。

### 8.6 必要测试

- 后端真实应用服务配合fake外部端：五种模式序列、零单元、split/fan-in、失败分类、取消/超时/重投/旧代、主件恢复与质量先于登记。
- repository合同：新旧record/event/failed_stage/receipt往返、空槽/receipt/IR条件、原子双retry与取消/timeout；file双进程/SQLite真实连接竞争及锁释放；fake MySQL只核SQL形状，真实InnoDB专项为写者启用门。
- 前端：阶段文案/URL guard单测，定向mock API smoke实际显示新值和未知值、执行阶段筛选、保留URL与后端动作禁用。
- first-valid-receipt定向证明A上传/B恢复及迟到失败、选定后禁止回退、四点中断、候选独立key/字节checksum/evidence、列表/按ID/技术Token隐藏候选、物化与保留期不复活；legacy仅唯一可核验同代/IR件，矛盾不猜最新。
- 稳定候选执行既定release；未变的前端unit/build/smoke和Renderer component证据可复用。线上/Word证据另行明确，不冒用离线结果。

### 8.7 错误与正确做法

错误：只把三个值加到Literal；批次仍只接受ir_converting，质量仍在rendering，恢复扫描取任意历史主件。

正确：同时更新模型、推进guard、失败/取消/超时、恢复及真实消费者；自动恢复严格检查来源，重新生成的字节必须重走quality_checking后才能登记。

```python
# 阶段变化必须核对当前代和执行状态，旧回流不能覆盖新的执行尝试。
if job.retry_count != generation or job.status != "running":
    return job
```


### 8.8 结果候选与下载可见性

质量检查通过后，先登记带`document_job_result_protocol=1`的pending候选，再写含file_id的唯一对象key。文件服务拥有对象和descriptor，DocumentJob仓储拥有当前generation/最终IR的结果槽位；选定后的所有恢复者只能物化该receipt，最后才绑定result_file_id并完成。候选/receipt均不新增公开API字段或前端状态机。

新协议generated_word必须是合法完成任务的当前result_file_id才可出现在任务files及下载签发/Token消费；receipt存在时不能通过同代fallback暴露其他generated_word。未绑定或取消后的候选即使已物化也不可成为用户主件。明确历史result_file_id合法复用保留；普通/files/{id}仍只提供原权限内metadata读取，Admin库存观察不能代替任务交付资格。旧文件/快照/审计不删除，不覆盖不可变发布件。
