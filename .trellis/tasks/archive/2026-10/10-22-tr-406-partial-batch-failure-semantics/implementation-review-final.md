# TR-406 最终独立复审

日期：2026-10-22。只读 reviewer：`/root/storage_audit`。本轮仅复核第三轮三个具体缺口及其直接修复，没有扩大检查范围或修改仓库。

## 结论

第三轮三项缺口均已闭合，本次限定范围没有新增或残留 P1/P2/P3。结合前两轮已闭合范围，本地候选可以停在人工验收阶段；不代表人工已接受或生产启用门已通过。

| 修复点 | 独立实测证据 |
|---|---|
| 预算失败后的执行权 | `_claim_translation_batch()` 保留失败副作用并返回 None。原双根49/26、限额26、执行短根反例重放后 Provider=0、audit=0、attempt=0、lease=None。 |
| success CAS 树错误 | 专用异常先于 ValueError 透传，保留原 generation。探针得到 translation_batch_tree_invalid、generation=0，无 oss_failed 误分类，无目标 IR/主 DOCX 晋升。 |
| Artifact metadata 驱动异常 | SQLite 与模拟 pymysql.err 驱动异常均收口 oss_failed；重放后 Provider=1、audit=1，无产物晋升。未知 TypeError 继续可见，不伪装成功或进入 Provider 重试。 |

独立执行三个新增 selector，3项通过，0.397秒：

- `test_budget_preflight_failure_does_not_return_failed_batch_as_claim`
- `test_batch_success_cas_tree_error_keeps_tree_code`
- `test_batch_result_repository_sqlite_failure_is_oss_failed_without_provider_retry`

另执行五组本地窄探针对照，均满足断言。42/126项组合、release、前端等已有门禁由质量报告提供，本轮未重复，未记为独立实测。

## 固定候选

开始与结束 SHA-256 一致，且与质量验证后的候选相符：

- `app/domains/document_jobs/execution.py`：`5119d349c638b6e2c590f0154187eeff33f4e71cf18270299c7cc342208c75d2`
- `tests/test_translation_batch_failure_semantics.py`：`dbc01050224d34e6b784d217333e214257378856bcbc1b79eb688f6d8483b26c`

前轮 R1–R10 的原问题、修复与证据保留在 round1/round2/round3 报告中，不用最终结论覆盖失败历史。

真实 MySQL/InnoDB 并发与断连、部署文件系统锁、真实 Provider/S3、Word 人工证据和生产写者启用继续 pending。本轮未连接真实数据库或 Provider，未修改文件、提交或 push。
