# TR-406 验收证据映射

本文件映射 revision 2 的 AC1–13 与当前测试入口；通过数量和最终候选状态以 `quality-validation.md`、最终独立复审和实施总结为准，不把测试存在当作已通过。

| AC | 当前可观察合同 | 主要证据入口 |
|---|---|---|
| AC1 | 终败优先于 queued/running 兄弟，无回填/目标 IR/主 DOCX | failure_semantics：`test_terminal_failure_marks_job_before_running_sibling_returns`、`test_terminal_leaf_stops_queued_sibling_and_replay_is_idempotent`、四方向失败对照。 |
| AC2 | split/同代自动重试可正常完成，不重调成功兄弟 | 既有 FastAPI truncated split/fan-in 与用户 retry 定向回归；公开 OPA228 和合成表格真实成功链路。 |
| AC3 | attempt/预算/lease 耗尽稳定停止，重复消息零新调用 | workflow 的预算/过期 lease；repository 的最后预算/回收/双 claim；failure_semantics 的 lease reclaim 与重放。 |
| AC4 | 旧 attempt/lease/代次不能写胜出记录或字节 | repository：`test_old_attempt_lease_and_terminal_sibling_cannot_promote_result`、双 claim barrier；TR-403 真实迟到字节/checksum 回归；旧代树异常不可误伤新代。 |
| AC5 | 用户原子换代，从准确 source 重建全部新代批次 | failure_semantics 的 retry source/新批次/无旧 result 指针断言；既有 retry 过滤/原子 retry/receipt 与 TR-403 generation 绑定回归。 |
| AC6 | partial 中间结果不能当主件下载、QA 或发布来源 | failure_semantics 的部分成功 batch download-url/QA/主件隔离；CON-104 文件分类与显式文件/过期/权限回归。 |
| AC7 | 树/覆盖/evidence/来源/hash 不符失败关闭，零单元明确 | workflow 树与零单元；repository 真中断/rollback；TR-403 integrity execution 全模块；stage/fan-in 与真实 I/O 错误归属。 |
| AC8 | 权威摘要、行分类、代次和安全事件一致 | workflow 终态优先/停止/计数同源；API 换代窗口；failure_semantics claim/CAS拒绝收口、单次审计/单次终态事件及安全 I/O 消息。 |
| AC9 | UI 消费后端结论及动作，旧响应不覆盖当前代 | frontend unit 与“翻译批次”mock smoke：operator/admin、375/768/1024/1440、dark、键盘和旧 generation 响应；见 frontend-validation.md。 |
| AC10 | direct 零 AI，一主件、原生表格、完整草稿/资格及历史不可变 | modes、generated_artifact_identity、result_persistence、delivery_state/download_availability/API；合成表格 w:tbl 与单位文本；公开 OPA228 和 direct matrix。 |
| AC11 | 三 adapter 同一窄合同、真实 file/sqlite 与 fake MySQL | repository 的独立 backend/连接、真实 barrier/事务回滚、job→batch当前读/rollback SQL断言；真实 InnoDB/部署FS仍待上线启用门。 |
| AC12 | B判空暂停、A一成功一运行、B恢复账本不变；残根消费前失败 | repository：`test_double_initialization_keeps_state_after_stale_empty_observation`、file真写故障、sqlite事务rollback；failure_semantics：`test_partial_root_installation_fails_closed_without_repair_or_provider_call`。 |
| AC13 | terminal CAS后job仍running，终态自身/兄弟消息都幂等收口 | failure_semantics：真实中断重放、summary后claim/CAS拒绝收口、普通竞争与旧代对照；repository：正常split writer持锁期间snapshot等待，区别崩溃残树。 |

模块对应：`tests/test_translation_batch_failure_semantics.py`、`tests/test_translation_batch_repository.py`、`tests/test_translation_batch_workflow.py`。既有回归和精确入口见 `research/verification-navigation.md`，原始 HEAD 已复现的10项旧失败见 `research/original-head-regression.md`。

边界：本地 fake Provider 和 fake MySQL 不证明真实供应商四方向语言质量、InnoDB并发/断连或部署文件锁；生成 DOCX 不代替 Word 人工签字。样本矩阵仍有既有标题样式 flags 与 phase3 backlog 门，见 `sample-validation.md`。这些门禁保持，不进行生产连接、部署、提交或 push。
