# DocumentJob 有效复核列表查询 v2

## 1. 范围与状态

适用于保持线上有效复核语义的SQLite/MySQL列表下推、派生事实和双表回填。2026-10-30已按冻结113文件清单完成v2源码接回根checkout，文件SHA/mode及实际根目录92项针对测试通过，原暂存及其他未提交工作保留，未提交或推送；本地接回证据见任务 `10-30-document-job-query-pushdown` 的v2-root-writeback.md。同日hostdzire已通过固定候选完成迁移与切换，实际验收见该任务v2-live-execution.md；本地接回未执行新的线上发布或迁移。候选路径/源码产物见该任务release/v2及evidence，本地接回与线上交付分别以对应执行证据为准。

## 2. 接口与存储

- 外部GET参数与字段保持；service列表items仍是`(job, available_actions)`。
- 内部`DocumentJobListQuery.as_of`为单次aware UTC观察时刻；`DocumentJobListResult.observed_results`包含每个页内job ID的明确File或None，不允许缺键时重读。
- `document_jobs.list_query_json`存储版本3；`document_files.review_query_json`存储版本2；SQLite TEXT/MySQL LONGTEXT，payload权威，不新增索引。完整规范 key 已拆至独立列，查询 JSON 只保存其他事实；非generated_word的独立 key 为空串，不能与漏回填NULL混淆。
- `is_document_job_table_evidence_snapshot_current(expected) -> bool`在每个原重核点独立读取最新事实，只返回结果，不返回完整payload；原archived/九字段tuple和deleted前提不增减。job ID仅用于原collation寻址。
- 显式迁移保留dry-run/apply/verify，新增`--after-file-id`与原`--after-job-id`各自游标；报告`tables.document_files/document_jobs`各自计数/成功游标。apply先文件后任务；verify禁止非空游标，在同只读快照全量验证两表。
- 本轮可用运维入口位于任务 `11-06-list-loading-performance/research/release_ops/`，不在生产镜像内。`migrate.py` 每条实际连接核对 `--expect-database/--expect-server-uuid`，仅取显式 `JOBS_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`，调用所选完整镜像的原 owner、`initialize=False`；dry-run/verify 会话只读，两类锁等待10秒。`snapshot.py snapshot/compare`核对整个业务库原列/结构，恢复验证必须用`--include-derived`比较全部列，scope混用失败；`query_diff.py capture`要求隔离UUID、`--deny-server-uuid`生产UUID、aware `--as-of`及审核的真实角色矩阵，比较完整router响应摘要，包括动作/统计/顺序，不是HTTP认证证明。真实入口、错误分类及已执行离线用例见该目录README；旧任务 `release/ops/` 引用不能当成本轮现成工具。
- 历史任务 `10-30-document-job-query-pushdown` 的 `ops_container.py --execute` 固定一次性容器使用 uid0、`--cap-drop ALL --cap-add DAC_OVERRIDE`、NNP和只读rootfs/ops/baseline，仅证据目录与tmp可写。镜像应用用户所有的0600源码需要该单项能力；不恢复全套默认能力，不改镜像/业务文件权限或账号。
- 历史任务 `10-30-document-job-query-pushdown` 专用 `evidence/v2-normal-session-client.py --control <本轮唯一0700目录>` 由用户在自己的 TTY 手动输入现有用户名和隐藏密码；固定 SSH `hostdzire`、后端 `127.0.0.1:18000`，使用正常 `auth/login` 与 `auth/me`。控制文件仅允许 `preflight/acceptance-start/acceptance-status/quit` 四动作，按 `request-NNNN.json` / `result-NNNN.json` 递增编号。

## 3. 合同与状态归属

有效复核依赖当前文件和时钟，不缓存最终分类。job静态事实复用effective_quality/receipt_identity原owner；file事实由每次_write_file同行维护，包括不增加revision的删除预留。create、任务_write_job、状态回填及正式复核导入直接SQL旁路均同步事实；从最终将持久化payload再解码生成，不使用JSON转换前的模型。

三统计域：summary=V（权限/归档/删除）；QA summary=B（再加status/q/date）的翻译任务，固定四键且不受QA选项影响；filtered_summary/total/items=F（再加有效QA选项），分页前汇总。完整筛选/聚合/排序/分页由SQL执行；整次SQL列表请求包括动作构建，完整任务payload解码次数不超过页条数。已有页内model_copy不算重复解码。

列表请求不再独立扫描两张全表检查 shape；就绪检查合入既有的文件 ID 一致性聚合。先安全判断任务可见性，再完整校验 V 域任务及完成态关联到的当前文件；不等到分页后才校验，不受 status/q/date/QA 筛选缩小。决定可见性的字段缺失、类型错误或 JSON 损坏时必须失败关闭，不能因 SQL NULL 或错误字段使任务静默消失。只有可见性可以可靠排除的任务、与请求无关的文件，才不在该请求做完整 shape 校验。缺列、V 域缺投影/坏形状/不支持版本仍为 `DocumentJobListProjectionUnavailable`，由 service 保持 503；校验与后续统计/分页处于原同一只读快照，不缓存跨请求就绪结果。

后续文件 JSON 提取使用 `CASE WHEN JSON_VALID(f.review_query_json) THEN f.review_query_json END` 作为解析输入，避免优化器先求值文件谓词、后排除不可见任务时解析到无关坏 JSON。首条就绪聚合仍校验原始文件投影并先行抛错，因此此解析保护不允许 V 域坏文件作为 NULL 静默通过。

全库事实与 payload 一致性继续由显式迁移的全量 verify 保证，不把 B08 的 schema 版本或一次启动成功当作投影正确证明。应用写路径必须在同次写入中从最终持久化 payload 生成投影（包括更新、删除预留、复核与旁路迁移）；运行中被破坏的 V 域投影下一请求仍会被发现。此优化不改变两个规范化大 key 的存储或相等比较，也不改变 file 后端与异常中心的原始记录读取路径。

SQL关联当前文件保留原寻址语义：MySQL按file_id列collation寻找，随后精确核对payload.id与请求ID；不能用binary JOIN把原ID错误变成缺件。权限/复核业务字符串和规范文本仍binary比较。所有列表统计/页选择与文件观察在同连接只读快照，MySQL显式RR；不在事务中做对象I/O。

比较有三个owner：receipt_identity沿原序列化摘要；descriptor按原dict相等；receipt按模型相等、仅排除etag/updated_at/expires_at/revision，expiry另比较。规范文本保留Python数字相等、NULL/缺键、数组顺序、typed日期及NaN/Infinity，不能以普通JSON或新SHA替代严格相等。MySQL JSON_TYPE的INTEGER和UNSIGNED INTEGER均是整数事实，数值比较仍使用精确signed微秒；不接受浮点或字符串伪数。

单请求固定as_of；下一请求自然反映到期。SQL与页内复核复用同次元数据观察；列表当前页的 publish 动作仅按既有状态条件判定，publication_evidence 保持 not_checked，不读取发布证据正文或执行证据文件回查。详情、发布前检查与 POST 提交保留完整实时核验；列表显示可点不保证提交成功。预览/表格/新代深度动作仅对当前页执行，保留实时外部认证和POST重核。因此页外对象故障不再拖累本页，但V域有效复核的元数据错误保持。file后端保留原读取与历史校验，不承诺跨两集合原子快照。

读视图以默认开启的显式参数控制发布证据深度核验，仅任务列表与异常中心列表的页内动作构建关闭；不得根据 `observed_result` 是否存在推断。此例外不适用于详情、发布前检查、异常诊断或批量操作等其他调用方，不改变其他动作、非管理员行为或响应字段。沿用现有读视图规则，`publish.enabled=true` 时返回的 `delivery_status` 投影为 `ready_to_publish`；证据异常时列表与完整核验的详情可能不同，不写回持久化状态。

`GET /api/v1/document-job-incidents` 保留全部可见任务的必要元数据分类：有效复核、重试资格、停滞与降级页，以及原建议/证据摘要参与的搜索。有效复核与重试资格复用既有 owner，不以原始状态替代有效状态；分类阶段不读取文件内容、不构建完整动作；主件到期沿用逐条分类时刻判断，请求起始时间只保留原停滞计算职责。页内复用分类阶段已校验的主件/下载观察，避免分页期间换件或到期使条目与统计分离。仍对完整过滤集合排序并计算 total/summary，然后仅为当前页任务构建完整动作，publish 复用同一轻量参数并保持 `publication_evidence=not_checked`。不改变分类、筛选、排序键和方向、分页、统计口径、非 publish 动作或可见性，也不将这次优化扩大为 SQL 下推或缓存。

异常列表首次有效复核与分类使用局部文件 `read_session()` 复用物理连接；每次读取仍为独立短事务，保留逐次时钟、完整模型/ID和保护关系检查。分类结束即关闭连接，页内继续复用观察；默认详情/诊断/POST不变。签名、错误顺序与真实RR验证由[数据库读取会话合同](database-guidelines.md#异常列表的局部读取会话)拥有。

正式迁移验收期间停止全部 job/file 及全库备份相关写者；先备份与隔离恢复演练，再 apply、空游标全量 verify、原列 before/after 比对和冻结 O/C 差分，完成后才启动任何新 API/Worker。应用启动仍可能运行原 schema/seed/recovery，不能当只读验收。数据覆盖恢复与兼容镜像代码回滚分开授权，旧写者恢复后两表重新从头构建。

`DAC_OVERRIDE`可绕过读写执行DAC检查，不能称只读能力；写入限制由只读rootfs及挂载独立保证。运维无有效JSON时保留真实`docker_exit_code/ops_phase/ops_error_category`，坏stdout不输出/保存；失败stderr先按实际配置凭据及JSON/repr形式脱敏，再于当前执行者所有的0700实际证据目录独占创建0600随机诊断文件，报告只返回文件名。诊断保存失败只附`save_failed`，不替换主错误或退出码；未知写结果不重试。

正常用户验收不得绕过原 JWT/权限：密码仅经固定 SSH stdin 正常登录，JWT 仅远端单进程内存，输出只有安全摘要；凭据不接受 argv/env/file 输入，不写控制文件或日志。正常登录会写原 auth.login 审计，安排在 T0 前。工具不支持的浏览器标记或受限终端操作不能靠其他电脑操作绕过；由用户本人手动启动已验证客户端。

有限 SSH 行协议的发送和完整响应读取共享一个 90 秒截止时间；响应最多 64 KiB。请求与结果使用 `publish_json`：同目录0600临时文件完整写完并关闭，再 `os.link` 独占原子发布，最后清临时文件；不能先暴露半 JSON，也不能用覆盖式 rename 丢失旧结果。客户端同目录禁止重启；一次样本创建尝试后不重试，任何失败退出并关闭 SSH，最长等待一小时。

## 4. 校验与错误矩阵

| 情况 | 行为 |
| --- | --- |
| 真缺件或未通过完成态/归属/type/status观察门 | 按原review规则失效；不能把任意JOIN文件直接传入复核 |
| 下载检查ApplicationError、删除预留/到期 | 保留已观察file；删除预留先于expiry比较 |
| 可达naive/aware错误、descriptor溢出/质量结构错误 | 按原前缀显式失败；前序已返回不额外触发，published不吞异常 |
| V 域投影或其关联文件缺失/旧版本/坏形状，任务可见性无法可靠判断，或缺列 | 明确不可用/503；不静默漏数、不GET回填或Python全量回退；无关行由全量 verify 检查 |
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

固定O/C独立进程调用完整线上list/read view作差分，不能仅拿新纯query或SQL自身生成期望。SQLite与真实MySQL覆盖类型/NULL/Unicode、三统计域、双表两连接快照、receipt条件错误与窄guard；完整API含实际表格和发布成功链，证明1条页记录仅解码1次。列表发布状态准入例外不再要求发布证据即时重核次数；表格与发布完整核验入口的原即时重核合同保持。

列表发布例外用定向测试验证：管理员待发布任务的 `prepare_publication_evidence` 与 `read_file_content` 零调用，证据检查为 `not_checked`；状态不符仍返回原禁用原因。证据异常时允许列表可点，但详情、发布前检查与 POST 必须保留原拒绝及 reason_code；同时比较其他动作和非管理员结果。错误做法是全局跳过证据核验，正确做法是仅列表显式关闭并保留默认完整核验。

真实MySQL入口`tests.test_document_job_list_query_v2_mysql`仅在授权环境显式启用`MD2WORD_TEST_MYSQL=1`及独立HOST/PORT/USER/PASSWORD，不接受已有库名、不读.env，只创建和删除自身UUID库。记录实际列collation与前后业务两表DDL摘要、库/隧道清理，fake或skip不作引擎证据。

就绪校验定向回归须捕获实际 SQL：普通无日期筛选请求由 13 条 SELECT 降为 11 条，不再有两表独立全表 shape COUNT；当前页、空页与空结果均保留该性质。首次成功查询后破坏 job/file 投影，覆盖 NULL、坏 JSON、缺键及版本错误，并分别验证当前页与仅 V 统计域仍失败。复用 writer 定向用例证明同行维护；有效数据与 file owner 比较三统计域、筛选、排序和分页。生产原两次独立扫描约 5.2 秒仅是移除的查询预算，合并校验成本及真实 MySQL 净收益须单独测量，不能按 SQL 条数直接推断。

候选原生镜像使用冻结线上镜像基底，只在无网络/业务挂载的测试容器验证，不能据此启动业务API/Worker。业务双表历史预检、停写、备份、正式回填、切换和线上验收另行完成。

发布运维验证须区分准备证据与窗口结果：预检核对镜像、Compose、运行态及挂载；备份演练覆盖整个库和实际对象/配置/Redis恢复点，精确COUNT及全列内容/元数据相符。默认迁移snapshot排除获准派生值，不能替代恢复全列模式或对象卷核验。本轮完整router差分在同一T0的隔离实例顺序执行O旧2/1→C新3/2→R旧2/1，各阶段使用完整冻结镜像的独立进程、真实读取依赖和角色，固定aware时钟，比较完整响应摘要，先同侧双跑再跨阶段对照；不得以双方同错误、空case或少量角色样本证明通过。每阶段进程退出、对应owner全量verify、原列/其他表/对象保真均为门槛。离线用例应捕获UUID不符、恢复派生值损坏、scope混用、其他表/原payload改变、重复行丢失、写入被捕获及错误伪相等；真实差分/回退只能在授权窗口记录为通过。

历史正常会话客户端的离线测试对照冻结实际路由/模型包装，覆盖正常登录/me/预检/上传创建/状态、身份与文件合同、无回显失败、凭据不泄漏、完整发送/响应截止、未知写不重试、阶段停止和原子发布权限。fake HTTP/SSH 不证明真实认证或受控通道可用；必须等用户手动输入后的 login/preflight 安全结果及新鲜线上核对通过，才能进入迁移窗口。

历史ops_container运维诊断测试用真实本地子进程生成合成失败，断言退出码、单JSON、脱敏/0600/独占、坏stdout丢弃及诊断保存失败保留主错；固定命令只增加DAC_OVERRIDE。真实无网原生探针须证实CapEff=0x2、NNP=1、受限源码SHA匹配和rootfs/ops写入EROFS，再复验只读snapshot；离线命令断言不能替代这些运行证据。

## 7. 错误与正确做法

错误：只保存raw review，或在file变化时刷新所有job，或缓存首次job撤掉表格证据重核。正确：各实体维护静态事实，SQL在同快照按as_of计算有效状态；即时guard在原每个重核点读窄当前事实。原锁序、账本、审计和对象认证继续由既有owner承担。

错误：无JSON时丢弃全部失败线索，或为读0600代码恢复容器全部能力。正确：受限脱敏诊断明确失败，仅补实证所需能力并实际验证只读边界。[Docker运行约束](https://docs.docker.com/engine/containers/run/)与[Linux能力语义](https://man7.org/linux/man-pages/man7/capabilities.7.html)用于核对该合同，运行结果仍须本环境证明。

## 8. 完整 key 拆列（2026-11-06 设计，2026-11-07 已验收）

- job 独立列为 `list_descriptor_key/list_receipt_key/list_table_snapshot_key`；file 为 `review_descriptor_key/review_receipt_key`，类型 SQLite TEXT/MySQL LONGTEXT。原 `equality_key`、descriptor、receipt 与 table snapshot owner 不变，不截断或散列替代；MySQL CAST AS BINARY、SQLite COLLATE BINARY 保留尾随空格、大小写和完整文本相等。
- `document_job_list_storage_from_raw` / `document_file_review_storage_from_raw` 从最终 payload 调用原完整语义投影，再拆出 key、更新存储版本。create、共享 writer、状态回填、正式复核导入和显式列表回填必须同行维护全部列；缺稳定时间时整组置 NULL。旧完整投影 builder 仍是内部语义事实，不可直接序列化回当前查询列。
- shape 检查新版本和完整列就绪；SQLite 另外拒绝 BLOB。缺列、旧版本、NULL 明确不可用，不GET回填、不回退解析旧大JSON。file 后端没有此派生布局，继续读取权威记录，结果必须与SQL后端一致。拆列与请求内就绪合并一同使用：首次关联聚合检查 V 域及其关联文件；不恢复独立全表 assert_ready 扫描。
- 独立入口 `scripts/ops/migrate_document_job_list_keys.py` 复用原迁移流程，支持 dry-run/apply/verify、两表独立游标、逐列DDL前滚、批次提交后推进游标、整组比较和成功重跑零UPDATE。旧入口同步升级，不再写回旧布局；只改双表派生列，不改payload、时间或job_events等其他表。
- 仅添加列而未回填时新版列表/窄guard失败关闭；新版API/Worker可正常维护其实际写到的行，但局部写入不代表全表就绪。全量回填并verify后新版正常；旧API/Worker不支持新JSON版本，禁止混部。旧写者一旦恢复，所有新列视为陈旧，再升级须两表空游标重建。
- 当前schema仍走CREATE/ALTER + INFORMATION_SCHEMA/PRAGMA；B08只完成设计，不能声称已有版本账本。生产停写、备份恢复演练、执行顺序、代码回退须先重建旧JSON及再升级重建规则见[当前整合设计及冻结迁移方案](../../tasks/11-06-list-loading-performance/design.md)，所有生产操作需另行授权。
- 定向证据涵盖大key体积、严格比较、file/SQLite列表与Python owner对照、writer原子性、干跑零写和中断恢复；MySQL SQL形状/fake不等于引擎性能。源候选此前未具备真实 MySQL 证据；当前整合任务使用独立 MySQL 8.4.13 做定向校验，结果以该任务 research 为准。生产引擎的本次验收环境为 8.4.9；本任务已于2026-11-07按后续明确授权完成生产迁移和线上性能验收，实际结果见[生产执行记录](../../tasks/11-06-list-loading-performance/production-execution.md)。这是该次发布的证据，未来生产操作仍须单独授权。

本轮运维正确/错误示例：恢复验证误用默认snapshot会漏掉派生列损坏，正确做法是源/恢复均使用`--include-derived`且全列scope一致；迁移后才使用原列scope并配套owner全量verify。上线后已有合法新业务时，回退保真应比较再次停写后的当前基线，而不是T0。Celery空闲不证明外部MinerU回调结束，应先挡新业务并保留回调/Worker排空，再封回调停API、消费最后在途后停Worker。工具不替代这些外部执行门槛。
