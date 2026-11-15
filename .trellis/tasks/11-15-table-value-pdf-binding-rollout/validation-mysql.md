# 第五阶段 MySQL 并发与审批发布验收

## 实际环境

使用隔离 Colima 中的 MySQL Community Server 8.4.9，运行镜像与仓库生产 Compose 声明的引用一致，均为 `docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`。本次 MySQL 服务的平台为 `linux/arm64`。

驱动实测使用 `md2word-rollout5:candidate`，镜像 ID 为 `sha256:6127850d19531ef99844ffb99090dfbb09dab1f0e997d1673de1381987618f1f`，平台为 `linux/amd64`，应用用户为 `md2word`，PyMySQL 版本为 1.2.3。只将测试夹具复制进一次性候选容器，应用代码和运行时依赖来自候选镜像。测试只接受显式启用的 loopback 地址及测试凭据，建随机 schema，运行后移除。写连接观测到 `REPEATABLE-READ`、`autocommit=0`、`innodb_lock_wait_timeout=50`。五张相关表的引擎均为 InnoDB，表排序规则为 `utf8mb4_0900_ai_ci`，服务配置的 `collation_server` 为 `utf8mb4_unicode_ci`。任务和文件的主键分别为 `job_id` 与 `file_id`。

## 验收结果

最终候选覆盖 8 项专项，首次运行的 6 项直接沿用有效结果，另 2 项以更新后的审批发布用例在同一候选镜像定向通过。早先用例在预先使报告失效后才读取发布视图，实际该 GET 已按现有错误合同返回安全 500。修正后的用例先取得有效快照，再使报告失效并直测发布 POST。

| 场景 | 实际结果 |
| --- | --- |
| 同 UUID 并发 | 须等先提交方的 job 主键锁。提交后返回原接受凭据。独立连接读回一次加代、一条账本和一条接受审计。同 UUID 改核定内容返回 `new_generation_request_conflict`。 |
| 不同 UUID 并发 | 败方等到 job 锁释放后看到已推进代次，返回 `new_generation_state_invalid`。旧代读取新代重放意图被拒，旧代更新无法覆盖新代的原包和执行槽。 |
| 依赖声明与提交顺序 | 删除声明先提交时，同包接受在文件锁释放后依当前描述拒绝。声明回滚后原绑定可接纳。受控时钟跨过报告有效期的竞争仍拒绝。相反交错下，声明方等接纳事务提交后执行。拒绝方未留下新代或审计。 |
| 锁异常与回执丢失 | 从独立连线造成真实 1205 行锁超时，查询原 UUID 无接纳。模拟 COMMIT 成功后回执丢失，以原 UUID 对账并重放，保持唯一已接纳代次和审计。 |
| 审批重核 | 最后一次实物读取后，在提交前独立提交报告或 IR 删除声明，正式审批返回 `409 review_result_integrity_conflict`。job 的批准状态、批准指针、历史条数和序号保持原值。 |
| 审批提交与回滚 | 批准先持有 Word、IR 和报告快照锁时，文件删除声明在报告主键行锁等待。批准提交时返回 200，独立连接仅见一条历史。模拟已插入历史而尚未提交时中断，审批返回安全 500，历史和序号无写入，等锁方可继续。 |
| 发布与未决项 | 完整认证的正例批准 200、发布 201。报告在发布独立认证后、事务提交前变更时返回 `409 publication_result_unavailable`。报告在发布认证前已失效保留现有安全 500，两种失败均无发布记录或指针。未决原 finding 仍走既有审批与发布 409。 |

独立第三连接从 `performance_schema.data_lock_waits` 与 `data_locks` 看到 `document_jobs.PRIMARY` 两次、`document_files.PRIMARY` 六次 `RECORD` 等待，观察到等待关系的用时为 56–129 ms。该轮只比较并发结果和事务语义，耗时受本地虚拟化、候选仿真和测试屏障影响。

用例走正式 MySQL adapter，审批发布用正式 FastAPI 路径、实际生成的 DOCX、登记的 IR 和表格报告。专项中的上游传输与预览 Provider 使用既有测试替身，实际 MinerU 传输、正式 Worker 和真实回包指纹由本任务的运行验收单独记录。入口为 `python -m unittest -v tests.test_table_value_rollout_mysql`，继承既有显式 MySQL 测试开关和凭据名。
