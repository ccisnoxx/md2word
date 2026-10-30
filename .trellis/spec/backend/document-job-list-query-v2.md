# DocumentJob 有效复核列表查询 v2

## 1. 范围与状态

适用于保持线上有效复核语义的SQLite/MySQL列表下推、派生事实和双表回填。2026-10-30已按冻结113文件清单完成v2源码接回根checkout，文件SHA/mode及实际根目录92项针对测试通过，原暂存及其他未提交工作保留，未提交或推送；本地接回证据见任务 `10-30-document-job-query-pushdown` 的v2-root-writeback.md。同日hostdzire已通过固定候选完成迁移与切换，实际验收见该任务v2-live-execution.md；本地接回未执行新的线上发布或迁移。候选路径/源码产物见该任务release/v2及evidence，本地接回与线上交付分别以对应执行证据为准。

## 2. 接口与存储

- 外部GET参数与字段保持；service列表items仍是`(job, available_actions)`。
- 内部`DocumentJobListQuery.as_of`为单次aware UTC观察时刻；`DocumentJobListResult.observed_results`包含每个页内job ID的明确File或None，不允许缺键时重读。
- `document_jobs.list_query_json`版本2；`document_files.review_query_json`版本1；SQLite TEXT/MySQL LONGTEXT，payload权威，不新增索引。非generated_word只保存基础身份/type，复核键不适用，不能与漏回填NULL混淆。
- `is_document_job_table_evidence_snapshot_current(expected) -> bool`在每个原重核点独立读取最新事实，只返回结果，不返回完整payload；原archived/九字段tuple和deleted前提不增减。job ID仅用于原collation寻址。
- 显式迁移保留dry-run/apply/verify，新增`--after-file-id`与原`--after-job-id`各自游标；报告`tables.document_files/document_jobs`各自计数/成功游标。apply先文件后任务；verify禁止非空游标，在同只读快照全量验证两表。
- 任务内 `release/ops/migrate.py` 要求 `--expect-database/--expect-server-uuid`，仅取明确 `JOBS_MYSQL_*`，`initialize=False`；dry-run/verify 会话只读、两类锁等待均为 10 秒。`snapshot.py snapshot/compare` 仅核对双表原列；`query_diff.py` 要求独立冻结 O 源码/manifest 和 aware `--as-of`，只比较列表元数据，不扩写为完整 API/动作验收。
- `ops_container.py --execute` 的固定一次性容器使用 uid0、`--cap-drop ALL --cap-add DAC_OVERRIDE`、NNP和只读rootfs/ops/baseline，仅证据目录与tmp可写。镜像应用用户所有的0600源码需要该单项能力；不恢复全套默认能力，不改镜像/业务文件权限或账号。
- 任务专用 `evidence/v2-normal-session-client.py --control <本轮唯一0700目录>` 由用户在自己的 TTY 手动输入现有用户名和隐藏密码；固定 SSH `hostdzire`、后端 `127.0.0.1:18000`，使用正常 `auth/login` 与 `auth/me`。控制文件仅允许 `preflight/acceptance-start/acceptance-status/quit` 四动作，按 `request-NNNN.json` / `result-NNNN.json` 递增编号。

## 3. 合同与状态归属

有效复核依赖当前文件和时钟，不缓存最终分类。job静态事实复用effective_quality/receipt_identity原owner；file事实由每次_write_file同行维护，包括不增加revision的删除预留。create、任务_write_job、状态回填及正式复核导入直接SQL旁路均同步事实；从最终将持久化payload再解码生成，不使用JSON转换前的模型。

三统计域：summary=V（权限/归档/删除）；QA summary=B（再加status/q/date）的翻译任务，固定四键且不受QA选项影响；filtered_summary/total/items=F（再加有效QA选项），分页前汇总。完整筛选/聚合/排序/分页由SQL执行；整次SQL列表请求包括动作构建，完整任务payload解码次数不超过页条数。已有页内model_copy不算重复解码。

SQL关联当前文件保留原寻址语义：MySQL按file_id列collation寻找，随后精确核对payload.id与请求ID；不能用binary JOIN把原ID错误变成缺件。权限/复核业务字符串和规范文本仍binary比较。所有列表统计/页选择与文件观察在同连接只读快照，MySQL显式RR；不在事务中做对象I/O。

比较有三个owner：receipt_identity沿原序列化摘要；descriptor按原dict相等；receipt按模型相等、仅排除etag/updated_at/expires_at/revision，expiry另比较。规范文本保留Python数字相等、NULL/缺键、数组顺序、typed日期及NaN/Infinity，不能以普通JSON或新SHA替代严格相等。MySQL JSON_TYPE的INTEGER和UNSIGNED INTEGER均是整数事实，数值比较仍使用精确signed微秒；不接受浮点或字符串伪数。

单请求固定as_of；下一请求自然反映到期。SQL与页内复核复用同次元数据观察；发布/预览/表格/新代深度动作仅对当前页执行，保留实时外部认证和POST重核。因此页外对象故障不再拖累本页，但V域有效复核的元数据错误保持。file后端保留原读取与历史校验，不承诺跨两集合原子快照。

正式迁移验收期间停止全部 job/file 及全库备份相关写者；先备份与隔离恢复演练，再 apply、空游标全量 verify、原列 before/after 比对和冻结 O/C 差分，完成后才启动任何新 API/Worker。应用启动仍可能运行原 schema/seed/recovery，不能当只读验收。数据覆盖恢复与兼容镜像代码回滚分开授权，旧写者恢复后两表重新从头构建。

`DAC_OVERRIDE`可绕过读写执行DAC检查，不能称只读能力；写入限制由只读rootfs及挂载独立保证。运维无有效JSON时保留真实`docker_exit_code/ops_phase/ops_error_category`，坏stdout不输出/保存；失败stderr先按实际配置凭据及JSON/repr形式脱敏，再于当前执行者所有的0700实际证据目录独占创建0600随机诊断文件，报告只返回文件名。诊断保存失败只附`save_failed`，不替换主错误或退出码；未知写结果不重试。

正常用户验收不得绕过原 JWT/权限：密码仅经固定 SSH stdin 正常登录，JWT 仅远端单进程内存，输出只有安全摘要；凭据不接受 argv/env/file 输入，不写控制文件或日志。正常登录会写原 auth.login 审计，安排在 T0 前。工具不支持的浏览器标记或受限终端操作不能靠其他电脑操作绕过；由用户本人手动启动已验证客户端。

有限 SSH 行协议的发送和完整响应读取共享一个 90 秒截止时间；响应最多 64 KiB。请求与结果使用 `publish_json`：同目录0600临时文件完整写完并关闭，再 `os.link` 独占原子发布，最后清临时文件；不能先暴露半 JSON，也不能用覆盖式 rename 丢失旧结果。客户端同目录禁止重启；一次样本创建尝试后不重试，任何失败退出并关闭 SSH，最长等待一小时。

## 4. 校验与错误矩阵

| 情况 | 行为 |
| --- | --- |
| 真缺件或未通过完成态/归属/type/status观察门 | 按原review规则失效；不能把任意JOIN文件直接传入复核 |
| 下载检查ApiError、删除预留/到期 | 保留已观察file；删除预留先于expiry比较 |
| 可达naive/aware错误、descriptor溢出/质量结构错误 | 按原前缀显式失败；前序已返回不额外触发，published不吞异常 |
| 缺投影/旧版本/坏形状/缺列 | 明确不可用/503；不静默漏数、不GET回填或Python全量回退 |
| job外层时间或prepared_result.file内嵌两时间缺raw键 | 显式预检阻断，不冻结default now |
| generated_word缺created_at | 预检阻断；非word缺created_at及当前file缺updated_at不据此扩大阻断 |
| 旧job或file writer恢复 | 两表事实整体不可信，重新停写、空游标全量重建，不只补NULL |
| verify 非空游标、连接目标/UUID 不符或只读/锁等待保护未生效 | 运维入口非零退出，不推进切换 |
| 差分缺列/陈旧事实、任一侧错误或结果差异 | 非零退出；双方相同错误也不通过，不回填或降级为候选全表 Python 筛选 |
| 运维容器无JSON/坏JSON/无整数exit_code，或Docker非零 | 非零退出并记录受限脱敏诊断，保留有效工具游标；Docker非零优先，原tool_exit_code单独保留；不把导出或空报告当完整基线 |
| 客户端非 TTY、GetPassWarning、非法控制目录或已有结果目标 | 明确停止，不回显降级、不覆盖旧证据 |
| SSH 发送背压、半行响应、断连、HTTP/身份或验收合同失败 | 安全失败并停止阶段；写入结果未知保留标记，不自动重试或创建替代任务 |

## 5. 正常、缺省、错误场景

正常：有效verified批准被approved筛选和QA计数共同识别；文件独立变化或到期后下一请求成为unreviewed，job raw不变。缺省：QA未传含direct，all限翻译；不从旧QA晋升正式批准。错误：页内再读主件导致“筛approved但显示unreviewed”，或只在回填时保存有效状态。

运维实例：uid0/cap-dropALL读取镜像uid1000所有的0600源码会在JSON入口前PermissionError；只补DAC_OVERRIDE后应能导入，rootfs与代码挂载写入仍须EROFS。失败尝试留存，完整基线在新0700目录重建，不覆盖旧证据。

受控客户端固定 direct 的 gs-003 新任务，精确 ID 搜索须 total/items=1、filtered_summary={列表条目当前status:1}、QA四固定键全0、V汇总包含该状态至少1。详情与列表是两次请求，非终态允许正常进度变化；只有两次均终态才严格比较 status/review/quality，不能把 running→succeeded 当查询缺陷。

## 6. 必要验证

固定O/C独立进程调用完整线上list/read view作差分，不能仅拿新纯query或SQL自身生成期望。SQLite与真实MySQL覆盖类型/NULL/Unicode、三统计域、双表两连接快照、receipt条件错误与窄guard；完整API含实际表格和发布成功链，证明1条页记录仅解码1次但仍执行至少8次即时重核。

真实MySQL入口`tests.test_document_job_list_query_v2_mysql`仅在授权环境显式启用`MD2WORD_TEST_MYSQL=1`及独立HOST/PORT/USER/PASSWORD，不接受已有库名、不读.env，只创建和删除自身UUID库。记录实际列collation与前后业务两表DDL摘要、库/隧道清理，fake或skip不作引擎证据。

候选原生镜像使用冻结线上镜像基底，只在无网络/业务挂载的测试容器验证，不能据此启动业务API/Worker。业务双表历史预检、停写、备份、正式回填、切换和线上验收另行完成。

发布运维验证须区分准备证据与窗口结果：预检核对镜像、Compose、运行态及挂载；备份演练覆盖整个库和实际对象/配置卷，精确 COUNT 与内容/元数据相符。双表 snapshot 不能证明其余表或对象卷未变。一次性 `query_diff.py` 复用同一数据库快照的 jobs/files、原列寻址和 publication 保护集合，将 raw 仅经内存管道交给独立 O；计数直接比较，页内有序 ID/review/quality 用 SHA-256 摘要比较。离线测试应捕获陈旧投影、错误分支、权限/全分页及快照变化；真实业务差分只能在授权窗口记录为通过。

正常会话客户端的离线测试对照冻结实际路由/模型包装，覆盖正常登录/me/预检/上传创建/状态、身份与文件合同、无回显失败、凭据不泄漏、完整发送/响应截止、未知写不重试、阶段停止和原子发布权限。fake HTTP/SSH 不证明真实认证或受控通道可用；必须等用户手动输入后的 login/preflight 安全结果及新鲜线上核对通过，才能进入迁移窗口。

运维诊断测试用真实本地子进程生成合成失败，断言退出码、单JSON、脱敏/0600/独占、坏stdout丢弃及诊断保存失败保留主错；固定命令只增加DAC_OVERRIDE。真实无网原生探针须证实CapEff=0x2、NNP=1、受限源码SHA匹配和rootfs/ops写入EROFS，再复验只读snapshot；离线命令断言不能替代这些运行证据。

## 7. 错误与正确做法

错误：只保存raw review，或在file变化时刷新所有job，或缓存首次job撤掉表格证据重核。正确：各实体维护静态事实，SQL在同快照按as_of计算有效状态；即时guard在原每个重核点读窄当前事实。原锁序、账本、审计和对象认证继续由既有owner承担。

错误：无JSON时丢弃全部失败线索，或为读0600代码恢复容器全部能力。正确：受限脱敏诊断明确失败，仅补实证所需能力并实际验证只读边界。[Docker运行约束](https://docs.docker.com/engine/containers/run/)与[Linux能力语义](https://man7.org/linux/man-pages/man7/capabilities.7.html)用于核对该合同，运行结果仍须本环境证明。
