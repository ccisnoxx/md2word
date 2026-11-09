# Research: 生产窗口的数据库排空只读统计

- Query: 核对三表真实字段、当前代/历史记录/lease、MinerU等待与未知首次提交，提供可直接使用的只读统计片段。
- Scope: internal；只读当前源码，不SSH、不连接数据库、不执行下方片段，仅写本文件。
- Date: 2026-11-07
- 授权：主会话通知用户已批准停写、备份/隔离恢复回退演练，门槛通过后迁移切换与线上验收；全库覆盖恢复未授权。本研究不自行执行这些动作。

## Findings

### 直接结论

1. `document_jobs` **无物理status/stage/retry_count列**，均在外层payload；callback与translation表有物理status。不得执行猜测的 `document_jobs WHERE status=...`。
2. callback只有pending/running属于既有owner的replayable集合。failed/ignored/processed不是待处理队列，历史失败本身不阻断窗口。processed可能保留历史lease字段，不能把任意非空lease当活动。
3. translation的当前代判断同时要求 `batch.generation == batch.job_retry_count == job.retry_count`。物理generation和payload generation也应一致。旧代/终态job下的失败批次不是活动；当前代failed且retryable只能叫“可能需处理”，不能仅凭flag宣称一定可重试。
4. running/parsing有batch ID且无raw result属于已知外部结果等待；无batch ID属于“尚未提交或首次提交结果未知”，都不能因Celery空闲而忽略。无batch不是无外部请求的证据：上传请求先发生，成功返回后才持久化batch ID。
5. 最小无活动任务窗口要求：所有job非终态=0、callback pending/running=0、当前代待处理批次=0；旧代/孤儿running批次须单列核对真实Worker是否还有调用。并行还需API在途、Celery所有节点active/reserved/scheduled、两队列/优先级队列/unacked和DB事务全部确认。DB单次统计不能单独证明全局排空。

### 文件与字段定位

| 源码 | 事实 |
| --- | --- |
| `app/infrastructure/persistence/mysql/schema.py:376` | jobs物理列是job_id/payload/时间及质量/复核/投影列；无status/stage |
| 同文件`:428` | callback物理列message_id/job_id/status/dedupe_key/payload/created_at/updated_at |
| 同文件`:442` | translation物理列batch_id/job_id/generation/status/payload/created_at/updated_at |
| `app/domains/document_jobs/models.py:125` | job.status/stage/retry_count/mineru_batch_id/mineru_data_id/mineru_raw_result_file_id/timeout_at等在payload |
| 同文件`:230` | callback外层payload包含job_retry_count、lease_owner/leased_at/lease_expires_at；内层payload才是Provider回调正文 |
| 同文件`:251` | translation外层payload包含generation/job_retry_count/status/retryable/attempt/lease |
| `app/infrastructure/persistence/mysql/document_jobs.py:487` | replayable只取pending/running |
| 同文件`:512` | processed只更新status和时间，可能保留旧lease；failed/ignored会清lease |
| `app/domains/document_jobs/execution.py:529` | callback先排除终态、再检查retry_count，再检查running/parsing |
| 同文件`:1369`、`:1615` | translation拒绝终态/旧代，claim还要求running/translating和原plan/budget合同 |
| 同文件`:341`、`:350`、`:385` | 首次上传在batch ID落库前；未就绪返回running/parsing |
| `app/workers/document_tasks.py:19` | callback模式可在外部任务未完时结束Celery任务；只有polling模式countdown续投 |
| `app/domains/document_jobs/workflow.py:95` | ACTIVE={pending,queued,running}，TERMINAL={succeeded,failed,canceled} |

相关Spec：`.trellis/spec/backend/database-guidelines.md`、`document-job-list-query-v2.md`、`translation-batch-lifecycle.md`；窗口顺序见同目录 `production-execution-plan.md` 第9节。读取时未运行产品初始化。

### 可直接使用的SQL：身份绑定后、同一RR只读事务

在已经核对期望server_uuid/database的连接上执行；这些语句不创建表/临时表、不改业务数据。先做结构/JSON粗检，任何bad_json非零不得将后续NULL当“无活动”。MySQL列返回类型/字符集仍以连接实际配置为准。

```sql
SELECT @@server_uuid AS server_uuid, DATABASE() AS database_name,
       @@version AS server_version;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;
SELECT 'document_jobs' AS table_name, COUNT(*) AS rows_count,
       COALESCE(SUM(NOT JSON_VALID(payload)), 0) AS bad_json
FROM document_jobs
UNION ALL
SELECT 'document_job_callback_messages', COUNT(*),
       COALESCE(SUM(NOT JSON_VALID(payload)), 0)
FROM document_job_callback_messages
UNION ALL
SELECT 'document_job_translation_batches', COUNT(*),
       COALESCE(SUM(NOT JSON_VALID(payload)), 0)
FROM document_job_translation_batches;

-- CASE保护坏JSON，不依靠WHERE求值先后；缺字段保留NULL分组，不过滤掉。
SELECT JSON_UNQUOTE(JSON_EXTRACT(
           CASE WHEN JSON_VALID(payload) THEN payload END, '$.status')) AS job_status,
       JSON_UNQUOTE(JSON_EXTRACT(
           CASE WHEN JSON_VALID(payload) THEN payload END, '$.stage')) AS job_stage,
       COUNT(*) AS rows_count
FROM document_jobs
GROUP BY job_status, job_stage;

SELECT status, COUNT(*) AS rows_count
FROM document_job_callback_messages GROUP BY status;
SELECT status, generation, COUNT(*) AS rows_count
FROM document_job_translation_batches GROUP BY status, generation;
ROLLBACK;
```

上述只做安全初筛，不能单独区分当前代与lease。以下代码由主会话放在既有受限远端载体内运行；不另建生产脚本、不暴露业务payload。使用同一**已身份绑定、已经开启RR READ ONLY snapshot的PyMySQL DictCursor连接**。函数本身只有SELECT，结束事务/关闭连接由外层拥有。

### 完整只读分类代码

代码依赖旧镜像已有models，不构造Settings/backend、不调用build_runtime。`observed_at`由外层明确提供aware UTC datetime。模型校验异常只计数，不打印可能含payload的异常文本；任何错误计数非零都不能声明排空。缺失关键原始字段不能让Pydantic默认值掩盖；若历史记录缺字段，作为数据待核对事项报告，不直接补值。

```python
from collections import Counter
from datetime import datetime
import json
from app.domains.document_jobs.models import (
    DocumentJobRecord, DocumentJobCallbackMessage,
    DocumentJobTranslationBatchRecord,
)


def collect_window_readiness(connection, observed_at):
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        raise ValueError("观察时间必须是aware datetime")
    active = {"pending", "queued", "running"}
    terminal = {"succeeded", "failed", "canceled"}
    counts, errors = Counter(), Counter()
    jobs = {}

    def rows(statement):
        with connection.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchall()

    def decode(row, model, identity, required, label):
        try:
            raw = json.loads(row["payload"])
            if not isinstance(raw, dict) or any(k not in raw for k in required):
                raise ValueError("缺少原始状态字段")
            record = model.model_validate(raw)
            if record.id != row[identity]:
                raise ValueError("物理ID和payload不一致")
            if "status" in row and record.status != row["status"]:
                raise ValueError("物理状态和payload不一致")
            if "job_id" in row and identity != "job_id" and record.job_id != row["job_id"]:
                raise ValueError("物理job_id和payload不一致")
            if "generation" in row and record.generation != row["generation"]:
                raise ValueError("物理generation和payload不一致")
            return record
        except Exception:
            errors[label + ":invalid_record"] += 1
            return None

    def lease_class(record):
        deadline = record.lease_expires_at
        if deadline is None:
            return "missing_deadline" if record.lease_owner else "none"
        if deadline.utcoffset() is None:
            errors["lease:naive_time"] += 1
            return "invalid"
        return "future" if deadline > observed_at else "expired"

    for row in rows("SELECT job_id,payload FROM document_jobs"):
        counts["jobs:rows"] += 1
        job = decode(row, DocumentJobRecord, "job_id",
                     ("id", "status", "stage", "retry_count"), "jobs")
        if job is None:
            continue
        jobs[job.id] = job
        counts["jobs:status:" + job.status] += 1
        if job.status in active:
            counts["jobs:active"] += 1
            counts["jobs:active_stage:" + job.stage] += 1
            if job.archived_at is not None or job.deleted_at is not None:
                counts["jobs:active_but_archived_or_deleted"] += 1
            if job.timeout_at is not None:
                if job.timeout_at.utcoffset() is None:
                    errors["jobs:naive_timeout"] += 1
                elif job.timeout_at <= observed_at:
                    counts["jobs:active_past_timeout"] += 1
            if job.status == "running" and job.stage == "parsing":
                if job.mineru_raw_result_file_id:
                    counts["mineru:raw_result_present_job_not_advanced"] += 1
                elif job.mineru_batch_id:
                    counts["mineru:known_batch_waiting"] += 1
                else:
                    counts["mineru:submission_not_started_or_unknown"] += 1
        elif job.status in terminal and job.failed_stage == "parsing":
            # 只记录历史诊断；不能据此声称外部请求从未发生，也不自动算活动。
            counts["mineru:terminal_parsing_failure"] += 1
            if not job.mineru_batch_id:
                counts["mineru:terminal_parsing_failure_no_batch"] += 1

    for row in rows("SELECT message_id,job_id,status,payload FROM document_job_callback_messages"):
        counts["callbacks:rows"] += 1
        message = decode(row, DocumentJobCallbackMessage, "message_id",
                         ("id", "job_id", "status", "job_retry_count"), "callbacks")
        if message is None:
            continue
        job = jobs.get(message.job_id)
        relation = ("unresolved_job" if job is None else
                    "job_terminal" if job.status in terminal else
                    "old_generation" if message.job_retry_count != job.retry_count else
                    "current_parsing" if job.status == "running" and job.stage == "parsing" else
                    "current_nonparsing")
        counts["callbacks:" + message.status + ":" + relation] += 1
        if message.status in {"pending", "running"}:
            counts["callbacks:replayable"] += 1
            counts["callbacks:replayable_lease:" + lease_class(message)] += 1
        else:
            # processed可保留旧lease，绝不把这类字段直接升级为活动。
            counts["callbacks:historical_status:" + message.status] += 1
            if message.status == "failed" and relation == "current_parsing":
                counts["callbacks:failed_on_current_waiting_job"] += 1

    for row in rows("SELECT batch_id,job_id,generation,status,payload FROM document_job_translation_batches"):
        counts["batches:rows"] += 1
        batch = decode(row, DocumentJobTranslationBatchRecord, "batch_id",
                       ("id", "job_id", "status", "generation", "job_retry_count"), "batches")
        if batch is None:
            continue
        job = jobs.get(batch.job_id)
        current = job is not None and batch.generation == batch.job_retry_count == job.retry_count
        relation = ("unresolved_job" if job is None else
                    "job_terminal" if job.status in terminal else
                    "current_generation" if current else "old_or_inconsistent_generation")
        counts["batches:" + batch.status + ":" + relation] += 1
        if job is not None and current and job.status in active:
            if batch.status in {"pending", "queued", "running"}:
                counts["batches:current_unsettled"] += 1
            if batch.status == "failed" and batch.retryable:
                counts["batches:current_failed_retryable_requires_owner_review"] += 1
        if batch.status == "running":
            # 旧代running也可能对应尚未退出的同步外部调用，单列留给进程核对。
            counts["batches:running_lease:" + relation + ":" + lease_class(batch)] += 1
        if batch.generation != batch.job_retry_count:
            counts["batches:generation_field_mismatch_requires_review"] += 1

    return {
        "observed_at": observed_at.isoformat(),
        "counts": dict(sorted(counts.items())),
        "errors": dict(sorted(errors.items())),
        "database_snapshot_only": True,
        "global_quiescence_proven": False,
    }
```

外层只能输出函数返回的聚合JSON。代码中的宽捕获仅在未知持久化记录反序列化边界，将该记录明确标为error、阻断“通过”，不吞成正常值；不输出ValidationError全文。若job ID由历史collation别名寻址，Python精确字典关联可能得到unresolved_job，必须用绑定参数SQL按原列collation复核真实目标并核对payload.id，不能直接判历史/终态跳过。

### 门槛与解释

| 观察 | 如何处理 |
| --- | --- |
| jobs active>0，包括archived/deleted或超时但仍running | 不算排空；记录异常，不能靠UI隐藏/超时推断结束 |
| running/parsing无batch ID | 首次请求可能已发但结果未落库；保持API/回调/Worker，不自动重提或取消 |
| callback failed，关联终态job或旧代 | 历史诊断，不因数量非零拒绝窗口；不自动replay/改状态 |
| callback processed仍有lease_owner | 历史字段残留可能是正常实现；不算活动lease |
| callback pending/running，哪怕job终态/旧代 | 仍是owner的回放集合，后续可能写ignored/events；未处理前不声称无写者，不能一律按“历史”排除 |
| current parsing + callback failed | 消息不自动replay，但job尚未收口，按job active门槛阻断 |
| translation旧代/终态job failed、succeeded、split、canceled | 不算当前活动任务；保留分组统计 |
| translation旧代/终态job running | 不能断言必有执行，也不能直接忽略；结合完整Worker active/reserved/scheduled及实际进程/lease判断 |
| lease expired | 不是远端调用已终止的证明；不能删除lease或自动回填状态来排空 |
| errors非零、unresolved关联、物理/payload状态不一致 | 未知，不判通过；报告摘要，另行受限核对 |
| SQL/inspect无响应或节点缺失 | 未取得证据，不等于0 |

先阻普通新业务但保留真实callback入口和Worker；上述条件收敛后关闭callback并优雅停API，Worker继续消化最后投递；复核再停Worker，最后检查无事务/其他写者，才进入T0。终态旧任务仍可能收到迟到callback并写ignored/events，所以“历史失败不算活跃”不意味着窗口可以保留callback入口。

## External references

本补查仅核对仓库已实现数据合同，不引入外部库/协议或新行为。MySQL只读事务与Celery停止的官方来源已在 `production-execution-plan.md` 引用，本文件没有执行环境验证。

## Caveats / Not Found

- 本研究未运行SQL/代码，没有线上计数结论。代码是供主会话受限载体使用的可审阅片段，不是已经验证过的生产工具。
- DB内没有“上游绝对无任何运行请求”的全局账本，尤其首次上传响应丢失不能单从batch ID反推。分类保留未知提交；任何需要Provider查询/取消或replay的动作应作为实际问题处理，不作为隐含排空步骤。
- 当前源码字段合同应由主会话与冻结旧镜像核对；读取时不能把新模型放入旧运行环境造成兼容污染。
- 所有历史failed均非零不是阻塞理由；所有真实当前非终态/未确认调用和replayable消息未经处理则不能证明排空。全库覆盖恢复不在本轮授权内。
