# B08 schema 版本治理：迁移设计

## 目标与交付边界

形成可审阅、在补齐审批后可直接执行的迁移设计三件套，消除现有 schema 无版本归属、API/Worker 竞争维护和中断状态不明的问题。本任务只写设计，不交付迁移代码、DDL 或数据库操作。设计交付完成不等于迁移实施完成或 Claude 验收通过。

本 worktree 基线为 `codex/b08-migration-design` 的 `828e1d9d656bf266cba7bba0ed23a62c550db15c`。只允许新增本任务目录；禁止修改代码、测试、Spec、依赖、部署、任务总清单或仓库外文件；不 commit、push、发布、归档或写会话日志。不访问生产、数据库服务、Provider 或 MinerU。

## 背景与证据边界

- MySQL backend 默认初始化 schema，现有维护包括建表、补列、数据 UPDATE、删旧索引和补索引，没有迁移账本：`app/infrastructure/persistence/mysql/backend.py:43`、`app/infrastructure/persistence/mysql/schema.py:550`。不能将初始化函数当作无副作用的基线登记。
- API 装配与 Worker 任务/就绪恢复均构造 runtime：`app/main.py:152`、`app/workers/document_tasks.py:23`、`app/workers/document_tasks.py:37`、`app/workers/document_tasks.py:48`。
- 正式 DocumentJob 事件复用 `job_events`：`app/infrastructure/persistence/mysql/document_jobs.py:376`。该表与 `document_jobs` 都是保护对象。
- 用户提供的生产只读核查快照：`jobs`、`job_files`、`stage_messages` 各 0 行；`job_events` 2511 行全部属于 119 个新任务；`document_jobs` 119 行。配置为 `PUBLIC_DEPLOYMENT_MODE=single_tenant_public`、`JOBS_ACCESS_MODE=token`、`APP_ENV=dev`，API/Worker 同镜像且都会启动。本轮未复核生产；行数是历史快照，不能作为未来删除许可，`APP_ENV=dev` 不能作为非生产判断。
- B05 第 3/4 步在另一分支移除旧消费者并删除三表 CREATE，尚未合入（用户提供）。本分支仍存在三表 CREATE：`app/infrastructure/persistence/mysql/schema.py:11`、`app/infrastructure/persistence/mysql/schema.py:28`、`app/infrastructure/persistence/mysql/schema.py:37`。

## 范围与要求

1. 设计已知 schema 基线识别、版本/校验和/执行状态账本，区分既有库登记、新库初始化与未知或部分完成库；登记不改变业务数据。
2. 只允许独立迁移执行者修改 MySQL schema；API/Worker 使用统一只读兼容检查，未知版本、中断及漂移明确拒绝服务/消费，不自动修复。
3. 定义中断后物理状态核对、重跑、前滚与备份恢复；逐操作声明可逆性，不承诺 DDL 事务回滚。
4. 首个收缩迁移只处理 `jobs`、`job_files`、`stage_messages`；删除前重新确认为空、无消费者、依赖检查通过且备份可恢复。保护正式数据、事件、payload、投影及其他表。
5. 比较显式 SQL 版本化与 Alembic，给出推荐及证据；MySQL 具体版本、旧 schema 支持集合和 SQLite 范围须批准后固定。
6. 后续实施顺序：本设计可先完成；B05 合入并确认发布候选不再创建/消费三表 → 完成版本治理代码和隔离验证 → 获批生产停写与基线登记 → 切换兼容 API/Worker → 独立 DROP 审批与执行。可合并停写窗口，但不可合并或推定授权。

## 非目标

不引入 ORM，不改造全库 LONGTEXT，不重写历史 payload，不回填列表/状态投影，不搬迁数据库后端；不处理 B09–B11，不改变认证/Provider 行为，不增加 CI，不做全仓回归或在线门禁。SQLite/file 现有行为不在本次文档任务中改变；是否纳入未来 schema 版本治理单独决定。

## 实施前用户决定点

| 编号 | 决定 | 推荐与审批边界 |
|---|---|---|
| D-1 | 工具选型 | 推荐显式 SQL + 小型版本执行入口；Alembic 为候选，不视为已选定或允许新增依赖。 |
| D-2 | 支持的旧版本与数据库 | 首期只支持经签字确认的当前 MySQL 8.4/InnoDB 基线轮廓与空库；实际补丁版本/镜像摘要须另行核实。SQLite 建议暂不纳入本机制，保持原行为；更老 MySQL、MariaDB、多主和其他历史结构不自动兼容。 |
| D-3 | 停写窗口与恢复目标 | 推荐首次接入与收缩均在全量停写窗口执行，包含 API、Worker、回调、定时任务和运维写者；由用户确认窗口、排空方式、最大时长、RTO/RPO 与恢复负责人。 |
| D-4 | 生产操作 | 基线账本创建/写入、权限调整、部署与恢复分别需明确生产授权。只读核查也须另行授权访问。 |
| D-5 | 实际 DROP | 单独批准目标库身份、三表精确名单、迁移校验和、备份及恢复证据、执行人和窗口；设计获批不代表 DROP 获批。 |

这些决定点是后续实施门槛，不阻塞本轮按用户要求完成设计文档。出现范围扩大或不能识别的 schema，停止相关动作并报告。

## 验收标准

- **AC-1**：PRD 明确目标、范围、非目标、B05 先后关系，以及工具、旧版本/数据库、停写和 DROP 的审批点。
- **AC-2**：设计包含版本表、无业务数据变更的基线登记、单执行者、启动兼容检查、中断恢复、逐项可逆性、正式数据保护、三表删除前置检查；至少比较两种方案并推荐。
- **AC-3**：实施计划按步骤列出最小验证、旧/新/部分 schema 夹具、授权隔离 MySQL 的重跑/中断/恢复与停止条件，并区分生产授权步骤。
- **AC-4**：对现有代码的引用均为已核实的 `文件:行号`。拟新增路径明确标记，不冒充已存在实现。
