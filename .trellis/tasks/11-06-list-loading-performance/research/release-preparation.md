# Research: 列表性能候选的发布准备事实

- Query: 核对维护中的发布、构建、迁移、原数据保真与回退入口，为后续审批提供可审核事实。
- Scope: internal；只读本地源码、部署记录与任务文档，仅写本文件。
- Date: 2026-11-07
- Checkout: `/Users/sc/PycharmProjects/md2word-wt/list-loading-performance`。

## Findings

### 结论与证据边界

本候选包含五列拆分、投影版本更新及异常读取会话。前两项要求停全部写者后迁移，不能滚动混部；异常读取会话自身没有额外配置或迁移。新旧版投影分别为 job/file **3/2 与 2/1**。线上切换不能直接沿用普通“只换镜像”回退。

当前可审核的入口是已有 Dockerfile、维护的分层 Compose 发布说明、双表迁移 CLI。尚未在本次研究中确认可直接运行的生产备份恢复、实例绑定、全库原列保真及生产固定 as_of 差分工具；这些不能以测试脚本代替。本文没有执行测试、构建、SSH、数据库连接、生产操作或 Git 命令。

### 文件索引与相关 Spec

| 文件 | 作用与定位 |
| --- | --- |
| `docker/prod/Dockerfile:2` | 固定 Python 基础镜像；15–18 行使用锁与离线 wheels |
| `docker/prod/docker-compose.yml:4` | 仓库标准 api/worker/redis/mysql 四服务定义；不是当前线上完整实际编排 |
| `docs/deploy/p0-docker-deployment.md:41` | CPython、平台、57 个 wheel、hash 与来源约束 |
| `docs/deploy/hostdzire-dmit-md2word.md:52` | 当前线上分层 override 模式、基础目录、完整清单与切换命令 |
| `scripts/ops/migrate_document_job_list_keys.py:1` | 新入口，复用当前列表迁移实现 |
| `scripts/ops/migrate_document_job_list_query.py:28` | 双表全部派生列、新版本、迁移/verify 所有者 |
| `scripts/ops/migrate_document_job_state.py`、`migrate_document_job_reviews.py` | 旁路写者也可能维护派生事实，不能在窗口中混入旧版脚本 |
| `.trellis/spec/backend/document-job-list-query-v2.md` | 新布局、就绪/比较/错误合同 |
| `.trellis/spec/backend/database-guidelines.md` | schema maintenance、共享 writer 与请求级读取会话合同 |
| `.trellis/spec/backend/runtime-configuration.md` | 配置入口边界 |
| 当前任务 `research/key-source-design.md`、`design.md` | 停写、恢复、游标和旧 JSON 重建要求；组合候选以 design 的 V 域校验为准 |
| 当前任务 `incident-read-session-plan.md` | 连接复用保留逐操作事务；无新 env/schema |
| 当前任务 `implement.md`、`research/key-integration.md` | 已有本地证据与生产未验收边界 |

### 构建输入与当前生产编排

1. `docker/prod/Dockerfile:2`：Python `3.11.18-slim-trixie`，固定 digest `sha256:b701198cb708b68d9413ca67d6311bd97c9389a2c5fe4da0511fc652642366cd`。目标为 **CPython 3.11.18 / Debian 13 / linux/amd64**；生产 Compose 本身未写 platform，构建现场仍需确认主机/活动 builder 架构。
2. 锁：`requirements/locks/cp311-linux-amd64.txt`；wheelhouse：构建上下文的 `requirements/wheels/`。57 个运行 wheel，不含 pip；镜像用 `pip --isolated --no-index --find-links=/tmp/wheels --require-hashes --only-binary=:all:`。wheel 不在 Git archive 内，不能仅导出源码就构建。
3. 官方来源记录：`.trellis/tasks/11-06-dependency-image-baseline/research/pypi-provenance.json` 中除 pip 外的 56 个制品，加 `wheelhouse-provenance.json` 的 Pillow 12.2.0。先核对文件名、目标 tag、官方 SHA-256 与当前锁；记录随发布准备保留，运行包不含 `.trellis`。apt/Poppler 未锁仓库快照，不能承诺完整镜像字节复现。
4. 文档固定 MySQL 8.4.9 digest `sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084`，Redis 7.4.9 digest `sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99`。此次仅发布 API/Worker，不能顺带重建这两个服务。
5. `docs/deploy/hostdzire-dmit-md2word.md:58–60` 记载：生产 api/worker 使用 `/root/md2word-releases/template-compat-c1f7e8a1468f-20261029/compose.yaml` 加历次 override；MySQL/Redis 来自 `/root/md2word/docker-compose.p0.yml`。基础层拥有 env、账号文件、模板绑定、外部卷和网络，不能丢弃。上次成功 release 的 `compose-files.txt` 才是下一次叠加的起点。窗口前用实际容器 Compose labels/上次成功记录复核，不能将历史路径视为已重新确认。
6. 当前任务已有公开版本与随后只读镜像核验记录为 `28cacd8a`，任务初始本地基线为 `25860865812ef5bb9159a449aaa7df0a6dfcb815`。归档部署记录 `.trellis/tasks/archive/2026-11/11-06-table-placeholder-failure-diagnostics/deployment.md:9–15` 记载 release `/root/md2word-releases/28cacd8a-table-diagnostics`、API/Worker image ID `sha256:77176d1903e9f266814b9ec3464551d1920c50b33683f3707889d570243dac7a`。这些是既有证据，不证明发布窗口时仍相同。

构建与切换的已维护命令形状如下。变量必须来自审批后的发布身份及现场核对；此处不执行、不创建脚本、不提供凭据值：

```sh
# 新 release 已导出确切提交、补齐 wheelhouse，MD2WORD_IMAGE 为唯一版本化标签。
docker compose --env-file .env -f docker/prod/docker-compose.yml build api
# 切换阶段在已核对的基础 Compose 工作目录，显式展开每个 -f，保留其顺序。
docker compose -p "$COMPOSE_PROJECT" -f '<原基础文件>' -f '<既有override>' -f '<本次override>' config --quiet
docker compose -p "$COMPOSE_PROJECT" -f '<原基础文件>' -f '<既有override>' -f '<本次override>' up -d --no-deps --no-build api worker
```

不要将此模板的省略项作为实值。构建前按项目规则查看活动 daemon 的 mirrors/proxy 及 builder；按官方固定引用执行正常 pull，实际失败后再诊断，不用 curl Docker Hub 超时推断 pull 失败。归档记录中的“无 mirror/proxy、default/docker”是 2026-11-06 历史值。

### 服务、环境与全部停写边界

- API 为 `python -m uvicorn app.main:app`，worker 为 `python scripts/dev/run_document_worker.py`；后者同时消费 `DOCUMENT_JOBS_CELERY_QUEUE` 与 `DOCUMENT_JOBS_TRANSLATION_BATCH_CELERY_QUEUE`（`scripts/dev/run_document_worker.py:34–53`）。停一个 queue 不足以证明无写者。
- 仓库 Compose 以 `.env` 提供配置，API/Worker 共用 `MD2WORD_IMAGE` 与 `/app/var`；实际生产还叠加 override 环境、账号与模板挂载。`JOBS_REPOSITORY_BACKEND=mysql`、`DOCUMENT_JOBS_WORKER_BACKEND=celery`、broker 与两个 queue 名均需现场确认，不能只看 `.env`。
- 迁移单独需要显式 `JOBS_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`。`APP_VERSION`、`DEPLOYMENT_ID` 是发布标识；不改现有认证、MinerU、对象存储、模板等配置。文档只记录键，不记录值。
- 完整停写对象包括 API 所有任务/文件修改与回调、普通任务及翻译 batch Worker、内联/eager/in_process 执行器、replay/retry/review/cleanup/导入修复/状态回填脚本、外部 cron/systemd/人工 SQL 与第二迁移进程。停止 API 会阻断同进程回调，但尚需现场核对有没有其它入口或独立进程。
- 源码 `app/workers/celery_app.py:24–42` 没有列出 beat_schedule；这不证明主机没有外部 scheduler。需在窗口盘点进程/容器/定时入口并确认在途工作、事务已排空；不得把停止 api/worker 两容器当作完整写者清单。
- 不在停写阶段启动应用做普通健康检查：`app/main.py:129,166,314–325,398–401` 有 bootstrap；启动本身可能写库。迁移 CLI 使用 `MysqlPersistenceBackend(..., initialize=False)`（`migrate_document_job_list_query.py:171–176`），避免应用 bootstrap。

### 迁移 CLI：可审核的确切合同

```sh
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --dry-run --batch-size 100
# dry-run 每表仅一批；续读使用上一份只读报告的 last_scanned_*，直到两表 has_more=false。
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --dry-run --batch-size 100 --after-file-id '<last_scanned_file_id>' --after-job-id '<last_scanned_job_id>'
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --apply --batch-size 100
# apply 仅使用最后已成功提交的游标，失败批次的 last_scanned_* 不能用。
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --apply --batch-size 100 --after-file-id '<last_successful_file_id>' --after-job-id '<last_successful_job_id>'
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --verify --batch-size 100
```

- 配置不读取 `.env`：`Settings(_env_file=None, **overrides)`，五个 MySQL env 名必须显式存在（245–280 行）。运行容器的网络、env 注入、挂载及凭据来源需在现场方案落实；当前 CLI 本身不校验预期 server UUID。
- 双表顺序 files→jobs；apply files 仍有下一批时 jobs pending（213–225 行）。**dry-run 会分别扫描两表一批**（208–212 行），不是等待文件扫完才扫描 jobs。源设计“files 未完 jobs pending”只适用于 apply。
- DDL 逐列提交；遇失败保留已加列，不 DROP。apply 每表一批事务，仅修正不一致行，整批成功后推进 `last_successful_*`。`committed_rows` 包括原本一致行，`mismatches` 是本批修正前发现的差异，不等于 UPDATE 数。
- verify 必须双空游标；内部按 batch-size 分块但在同一 RR 只读快照遍历完整双表。只有 exit code 0 且 `all_ready=true`、两表 complete、无 errors/schema_missing/mismatches 才是全量就绪。
- 返回 0：该次模式无失败；dry-run/apply 不能据此宣称全量 ready。返回 1：配置构造失败、迁移失败或 verify 不一致。argparse 参数错误（含 verify 带游标/缺显式 env）退出 2，可能没有 JSON 报告。依据 236–280 行与 argparse 使用。
- 原名 `migrate_document_job_list_query.py` 已同步到新布局，不能把它当成旧版回退入口。

### 数据库身份、备份、保真与固定结果对照

已有合同要求全库与对象/配置备份、隔离恢复核验、双表原 payload/时间/其他业务列以及其他表不变（特别 `job_events`）。但查阅的 `scripts/ops/`、当前任务、部署/runbook 中**没有可确认的通用生产备份恢复或全库保真 CLI**。不能拿历史 `/root/md2word` 目录 tar 当作 MySQL 与共享对象卷备份。

可核对的只读身份 SQL 形状：

```sql
SELECT @@server_uuid AS server_uuid, @@version AS version, DATABASE() AS database_name;
```

这只是查询形状，尚无预期 UUID/库名的批准值或绑定执行工具。应记录并双重核对实例 UUID、明确库名、版本及连接位置，保持凭据在现有秘密管理边界。CLI 的 host/database env 不等于实例身份保护。

现有工具不能替代上述准备：

- `research/production_readonly_probe.py:32–38` 只查只读标志、版本、行数及体积，没有 UUID 绑定或全库原列 hash。
- `research/benchmark-key-mysql.py:48–73` 会建合成库并直接写入合成记录/旧 JSON；它不是生产验收工具，禁止把业务库连接交给它。
- `tests/test_document_job_list_query_migration.py` 有原 payload/时间/额外列及 `job_events` 不变的夹具证据；测试不能证明生产实际未变。
- 迁移 verify 仅从权威 payload 重算并核对派生列，不校验全库其他表，不提供备份，也不证明固定 as_of 的完整旧/新列表结果相等。

后续审批前需落实：可审阅的备份/隔离恢复命令及保存位置、恢复点/责任人；原列与其它表一致性比较工具（只输出行数/hash，不输出 payload）；使用冻结旧查询与新查询、真实可见域、固定 as_of 的完整结果差分载体。两侧相同报错不能判等通过。工具未落实前不能把“生产切换已可直接执行”作为结论。

### 旧版冻结与回退

回退时仍需停全部写者，用**升级前完整冻结代码/镜像中的旧迁移实现及其依赖**从权威 payload 重建 job/file 2/1 大 JSON，旧版空游标 verify 后才启动旧进程；新增五列保留。不要只拷旧文件到新源码旁执行：其 imports 指向当前 `list_query`/backend/config，不能证明仍生成旧布局。恢复旧 writer 后新列整体视为陈旧，再升级从空游标完整重建。

主会话于本轮回传只读 Git 证据：`git diff 28cacd8a 25860865 -- scripts Dockerfile* docker-compose* docker requirements*` 无差异。这证明两冻结提交的上述工具/构建输入相同，可从部署旧版或本地基线的完整代码冻结旧布局工具；不能将此结论扩大为当前磁盘候选同名脚本可回退。实际生产旧镜像、代码与冻结提交仍需在窗口重新核对，冻结目录及其完整依赖未准备并核验前，不把旧回退命令列为可立即执行。

恢复备份会覆盖业务数据，与旧 JSON 重建和代码回退是不同动作，需另行明确批准。当前上线指南的普通镜像回滚不能覆盖本次 schema/投影迁移回退。

### 其它任务与发布记录的工具来源

- 主会话已确认依赖任务 `research/{prepare_wheelhouse.py,check_artifacts.py,pypi-provenance.json,wheelhouse-provenance.json}` 四个文件均 tracked；tracked 只证明可随源码取得，不证明适配本次生产窗口。
- 依赖任务 `research/prepare_wheelhouse.py:59–69` 直接 SSH hostdzire 并回写其 `wheelhouse-provenance.json`，带任务专属上下文，不是纯离线检查命令。本次不执行、不直接推荐复用。
- 同目录 `check_artifacts.py` 会比较 HEAD、读取其任务文件及 dev/prod Compose；它是该任务的证据检查器，不是本次通用 release 工具。
- 归档 `11-06-table-placeholder-failure-diagnostics/deployment.md:15` 记载 `/root/md2word-validation/table-diagnostics-deploy/` 内有远端脚本/日志。当前仅看到部署记录，未读取远端脚本或确认其是否 tracked、是否支持本次迁移，不能宣布它现成可用。
- 主会话核对 `git ls-files .trellis/tasks/**/release/**/*.py` 无结果，并用包含忽略文件的 root 搜索确认没有历史任务 `migrate.py`、`snapshot.py`、`query_diff.py`；不要引用这些不存在的工具。本研究不据此扩开发新工具。
- `scripts/ops/check_release.py` 是既有发布聚合入口，本任务不因收尾或发布规划自动执行它，不扩展全仓测试/Golden Sample 门禁。

## External references

本研究不采用新的外部 API 或依赖，不作生态选择；未联网。版本/digest/官方制品来源仅依据仓库 Dockerfile、锁、既有 provenance 和维护文档，真实性及现场运行身份边界如上。没有宣称完成最新外部来源重新认证。

## Caveats / Not Found

1. 研究开始时 `docs/runbooks/backend.md:142` 尚描述旧 2/1 布局；主会话已接手同步新版合同及 dry-run/apply 区分。本报告的行号指研究时读取版本，以当前源码 TABLES、Spec 和 key-source-design 为准。
2. 当前生产 Compose 链、镜像、活动写者、DB UUID/库名、恢复点、wheel 实物路径及可用磁盘需在获批窗口核对；历史记录不替代现场状态。
3. 本地引擎证据为 MySQL 8.4.13 arm64，线上记录为 8.4.9；性能及生产验收未完成。AC-2 仍要求正常认证用户两页默认 GET 三次中位数 ≤2 秒、页面完成 ≤3 秒，不把 ready 健康耗时当列表验收。
4. 未读凭据文件、未输出业务 payload，未执行任何生产或验证命令；此文件仅为审批准备研究。
