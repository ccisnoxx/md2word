# TR-406 执行验证记录

## 已运行

- `python -m py_compile app/domains/document_jobs/execution.py app/domains/document_jobs/service.py app/domains/document_jobs/schemas.py app/domains/document_jobs/router.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_failure_semantics tests.test_translation_batch_workflow tests.test_document_job_execution_stages`
  - 45 项通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_document_job_delivery_state tests.test_document_job_delivery_state_api tests.test_document_job_download_availability tests.test_document_job_download_availability_api tests.test_document_job_result_persistence`
  - 53 项通过。
- `git diff --check`（本任务执行/API/测试路径）通过。

## 观察到的合同证据

- 真实 file backend、SQLite fixture、fake Provider 流程覆盖终态失败、排队兄弟停止、审计
  只发生一次、无目标 DocumentIR/DOCX，以及 API execution/逐行 disposition 投影。
- 同一批次真实 claim 竞争只产生一次 Provider 调用；过期 lease 经过真实 release/reclaim 递增
  attempt 并拒绝旧 lease 回流；终态 CAS 故障窗口重放终态自身和排队兄弟不重复调用或发
  事件。
- claim/success/failure/split/release/enqueue 的原子端口返回 None 时，执行器会重新读取同任务
  锁快照；同代终态由 finalizer 收口，普通竞争直接结束，旧代不会污染新代。
- Provider 成功后的 batch Artifact 写入或成功 CAS 仓储 I/O 故障映射为 `oss_failed`，保留一次
  成功审计且不重调 Provider；原始存储异常路径不会进入 Provider 失败重试。
- 部分根安装消费时立即失败，保留根集合不被补齐且 Provider 为零；部分成功批次的 result
  artifact 不能从任务下载，也不会进入 QA 摘要或最新主件。
- 真实 file backend 重试窗口覆盖鉴权读取旧代、锁内 snapshot 读取新代时的 generation 一致性，
  不混合旧批次，也不将新代误判为 tree invalid；新代批次复用同一 source IR 绑定但拥有新
  batch identity，且没有旧 result artifact。
- 四个翻译方向的 Provider 失败都停在 translating；版本化 OPA228 MinerU 包以及含表格、单位、
  多 item 的合成 MinerU ZIP 均经过真实 converter→batch fan-in→renderer 成功对照，失败对照
  不发布 target IR 或主 DOCX。
- delivery/download 依赖测试覆盖内部主件分类、质量/复核阻断、发布资格与不可变结果件；
  本任务没有新增发布资格或 PublicationRecord owner。

## 仍需主会话关注

- 本记录覆盖 file backend 与 SQLite fixture 的执行路径；三 adapter 的并发锁、MySQL RR
  专项和全量发布门禁仍以主会话最终整组回归结果为准。
