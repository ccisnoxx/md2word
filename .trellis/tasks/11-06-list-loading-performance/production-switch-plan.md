# 生产切换与回退审批方案（2026-11-07）

**状态：2026-11-07已按授权完成执行并通过线上验收，任务completed。** 最新现场结果见production-execution.md。原构建阶段说明与窗口前置条件保留，不能把下文历史未执行描述当当前状态。批准未来窗口时应明确包含下述入口临时维护、排空、备份及隔离演练；全部前置门槛通过才允许生产迁移。全库覆盖恢复不包含在常规代码回退中。

## 1. 已固定的身份与产物

| 对象 | 已核实值 |
| --- | --- |
| 发布源码 | `b8b2779a9ee678f778ddb95890cebc3a0faff55e`（PR #34 merge commit） |
| 目标 | SSH alias `hostdzire` / 主机 `scrapy` / linux/amd64 |
| 发布目录 | `/root/md2word-releases/b8b2779a-list-loading` |
| 新镜像标签 | `md2word-p0:b8b2779a-list-loading` |
| 新镜像固定引用 | `md2word-p0@sha256:cbab7900f5172e5d24bcd743e5a2e8fcc73fcc1adb79d42392504862084e0667` |
| 新 image ID | `sha256:cbab7900f5172e5d24bcd743e5a2e8fcc73fcc1adb79d42392504862084e0667` |
| APP_VERSION / DEPLOYMENT_ID | `b8b2779a` / `hostdzire-20261106T172447Z-b8b2779a-list-loading` |
| 旧完整源码 | `28cacd8a3afea2cd02fc36230ad9d6bc0e7b89e8`，位于`rollback/source` |
| 旧 image ID | `sha256:77176d1903e9f266814b9ec3464551d1920c50b33683f3707889d570243dac7a` |
| MySQL目标 | 库`md2word`，8.4.9，UUID `a40f680d-5c49-11f1-b3c3-56d31c1c325b` |
| Compose project | `md2word-p0` |
| Compose工作目录 | `/root/md2word-releases/template-compat-c1f7e8a1468f-20261029` |

旧9层清单见`release-preparation/previous-compose-files.json`，新10层见`release-preparation/compose-files.json`及`compose-files.txt`。只修改API/Worker的image、APP_VERSION、DEPLOYMENT_ID六处；旧配置渲染后的environment与mounts已与运行容器逐项核对。新override使用已inspect核对的本地digest引用，未来`up`必须`--pull never --no-build --no-deps`，不动MySQL/Redis。

镜像无网只读依赖/import冒烟通过，新341个运行文件与指定Git archive一致；旧340个文件与旧冻结源一致，原迁移实际版本job/file为2/1，新为3/2。两版镜像保存在`release-preparation/release-images.tar`（165046272字节，SHA256 `7a192020e3c94164b6f3b1673ee15411e87fa601313201245b25ca37b4096b83`）。这不是业务数据备份。完整构建证据见[research/production-build.md](research/production-build.md)和[production-build-manifest.json](research/production-build-manifest.json)。

## 2. 本轮已准备、尚未激活的入口配置

实际server_name为`md2word.962850.xyz`（不要由历史文件名推断域名），监听`10.0.0.2:80/443`并启用proxy_protocol。活动站点：`/etc/nginx/sites-enabled/md2word-api.962850.xyz.conf`，原SHA256 `b7ff404fa25dbfe8bc7801234248d5ca25c691cdc5a5530d8a37e3fe9aaa5b60`。三份配置保存在`release-preparation/nginx/`。

- `original.conf`：原配置，切换成功或迁移前取消窗口时恢复。
- `drain.conf`：只在原TLS server增加 `if ($uri != "/api/v1/mineru-callbacks/result") { return 503; }`；普通入口进入维护，原回调路径及原代理/校验链保留。SHA256 `30b2d032b7ebded24bb8ed8596fcd0cc1a24799404f2e600980965afb8b92d04`。
- `freeze.conf`：只在原TLS server增加 `return 503;`；排空后关闭全部公网入口。SHA256 `b00a6be38d67ff3f9bf20bcbeb007859feea87996d5c4e0bb49c7b65369803d6`。

两份候选分别通过独立全局include配置的`nginx -t`。未覆盖活动文件、未reload，尚无实际流量门禁验收。未来替换前重新核对原站点hash、TLS include/现有配置并备份；在`/etc/nginx`内创建同权限临时文件，原子替换已核对的单个站点，`nginx -t`成功才reload；失败恢复原文件再检查。不得修改其它站点、dmit、WireGuard或共享nginx主配置。普通请求503及真实回调链的验收作为窗口第一道门槛；不伪造业务回调。

## 3. 窗口前检查与责任边界

执行者为获批的本任务运维会话；批准者为用户。逐项记录执行人、UTC开始/结束、真实退出码及证据路径。未指定窗口开始时间前不执行以下生产动作。预留时长不能由本地合成benchmark推断；先在窗口内完成备份/隔离演练，记录真实耗时，再按剩余窗口决定是否进入生产写入。预定截止前未完成门槛则取消切换，恢复旧服务/入口。生产写入前必须留足已实测的旧JSON重建时间、服务恢复时间及验收余量；不满足就不开始apply。

现场再次核对：旧API/Worker完整image ID、源版本、9层Compose、配置hash/挂载、DB UUID/版本/库名和全部34表、MySQL/Redis健康及磁盘/可用内存。任一变化先停止复核，不能覆盖其他发布。当前34表都是InnoDB，已用root只读元数据确认无view/routine/event/trigger，列类型为bigint/int/longtext/text/tinyint/varchar，无当前载体拒绝的浮点类型；event_scheduler=ON；未来仍须重查，不能以历史空列表豁免定时写者。

实际对象存储是local_object，`/app/var/object_artifacts`，整个`/app/var`由项目var卷持久化。当前var约438MiB、MySQL卷约690MiB、Redis卷约19MiB；空闲约59GiB。这些是容量盘点，不是dump/恢复性能证据。隔离演练只建一套专属MySQL实例，顺序执行O→C→R，不并行两套；不挂生产datadir、不发布端口，使用internal网络、固定同版MySQL镜像、event_scheduler=OFF。新实例建议1GiB内存/1CPU、运维容器512MiB/1CPU；启动前确认共享主机仍有实际余量，资源不足取消演练，不挤占现有服务或临时扩容。

本窗口仅影响md2word。现存网络成员/挂载盘点仅API、Worker、MySQL、Redis四个；root cron无md2word/Celery直接匹配，已列timer无本业务调度。此检查不能证明不存在外部人工SQL/远端调度：窗口执行者必须确认停止并记录cleanup/import/review/state回填、外部脚本、人工SQL、同库其它连接和对象写者，且在窗口内持续保持。不得把“停两个容器”当作全部排空证明。

## 4. 排空到统一恢复点T0

1. 激活已批准的drain站点配置。普通请求503；旧API和两个队列Worker继续运行处理已有任务和真实回调。不修改业务记录、不取消Provider任务、不purge/requeue。
2. 同时核对真实DB非终态job、callback pending/running消息、当前代translation batch/lease，以及Celery所有节点active/reserved/scheduled、两个队列及优先级子队列、unacked/hash/zset。`active=0`或两队列空不充分：callback模式在外部MinerU未完成时会让Celery调用先返回。回调HTTP200也不等于已消费。
3. 任一未知Provider提交、running/parsing任务、未处理回调、节点无回复或未解释租约均阻断；排空超时在迁移前恢复原入口和旧服务，保留队列及业务状态，不自动修复/重放。源码与准确检查范围见[research/production-execution-plan.md](research/production-execution-plan.md)第9节。
4. 全部收敛后激活freeze配置，再优雅停止API；Worker继续处理最后在途投递。复查DB/broker门槛通过后才warm停止Worker。使用`docker stop --timeout -1 <准确容器名>`并持续监控，不能以默认超时SIGKILL截断事务；先检查StopSignal和REMAP_SIGTERM，当前StopSignal未覆盖。超时先记录状态/恢复路径，不强杀。
5. 核对两个进程均退出、DB无业务写事务/DDL、没有剩余写者和对象写入；数据库及Redis保持运行。此时固定UTC `T0/as_of`，后续备份、演练和生产迁移期间维持停写。旧API/Worker在生产迁移verify通过前不得启动；应用bootstrap会写入，不能用应用启动做前置探测。

## 5. 备份与隔离恢复门槛

备份根目录：`/root/md2word-backups/list-loading-b8b2779a/<T0-UTC>`，独占创建、目录0700、文件0600、umask077，不覆盖已有证据。保留至用户批准清理；本任务不自动删除。每一步独立记录exit code/字节数/SHA256，避免管道或后续hash覆盖失败状态。

**数据库**：使用当前MySQL 8.4.9容器内已确认存在的mysqldump，完整备份业务库md2word的所有表、视图、routine、trigger、event。凭据在现有容器秘密边界内注入，不在argv或聊天中展开；例如由容器内已存在MYSQL_ROOT_PASSWORD设置子进程MYSQL_PWD，stdout直接写受限SQL文件，stderr写受限日志。使用参数：

```text
mysqldump --single-transaction --quick --routines --events --triggers --hex-blob --no-tablespaces --set-gtid-purged=OFF --databases md2word
```

显式带既有备份账号，先核实权限涵盖所有元数据及表；app用户看不到某些对象时不能将其当不存在。不能热tar正在运行的MySQL datadir，也不擅自导出/恢复共享mysql系统库。源库同时使用下述snapshot `--include-derived`记录全部列的稳定摘要；另保存默认迁移摘要。

**对象与配置**：用已核实GNU tar的`--acls --xattrs --numeric-owner`完整归档项目var卷（包含对象、上传/配置/中间产物），以及实际3个只读bind（账号JSON、模板docx、模板yaml）、基础.env、全部9层Compose、实际引用的env_file、受限实际容器environment快照、原nginx站点。完整精确源路径以构建manifest的mounts和compose_files为准；每个归档有独立文件名，不复制私钥到任务记录。所有源在T0保持稳定；恢复只写专属新卷/控制目录，保留owner/mode/mtime/link/ACL/xattr，逐条类型/内容hash与元数据核验，不跟随链接离开恢复根。源备份仍root私有；供镜像默认用户读取的控制文件只在隔离控制副本上设置必要权限，不chown原对象或生产卷。

**Redis**：当前DB0、`appendonly=yes`、dir `/data`、dbfilename `dump.rdb`、appenddirname `appendonlydir`。在获批窗口通过既有认证连接执行一次BGSAVE并验证本轮生成完成，保存RDB hash和队列/优先级/unacked摘要；不得凭旧LASTSAVE通过。用同版Redis在无端口、无Worker的专属环境进行RDB-only恢复验证，检查队列类型/有序内容/数量与未确认集合；带TTL缓存按绝对到期解释，不能豁免丢失的业务消息。原Redis及AOF卷保留不变，不能热tar一个rewrite中的AOF并宣称可恢复，也不以备份演练名义覆盖线上Redis。

**恢复**：使用新建专属MySQL数据卷和internal网络，同版8.4.9镜像，无生产datadir/auto.cnf、无外网/发布端口，event_scheduler关闭、无复制/应用/Worker。逻辑恢复原同名库，恢复UUID必须与生产不同且明确记录；`expected UUID`以后始终使用该恢复实例实值。导入成功后，用`--include-derived`对照所有列及schema、全部34表真实COUNT/hash，恢复对象/配置也全量对照；任何缺表、权限、DEFINER、事件或内容差异先停止，不删对象或跳过错误。

只有实际恢复核验通过，备份才可用。当前本轮尚未执行以上备份/恢复动作，不能把镜像归档、文件存在或dump退出0当恢复证据。

## 6. 已落实的运维载体及隔离O→C→R演练

任务专用目录：[research/release_ops](research/release_ops/README.md)，位于冻结生产镜像之外，未来只读挂载到`/ops`，工作目录`/app`，`PYTHONPATH=/app`。真实连接只接受显式五个JOBS_MYSQL_*环境，不读取.env、每条物理连接绑定UUID和库名；原owner保持initialize=False。载体6文件已冻结到远端`/root/md2word-releases/b8b2779a-list-loading/release-ops`，归档SHA256为`63b2d9ec86bbf15eaf4c1bf3483d0dca745c1d807db4203e68fc89415d1d245a`；清单见[release-ops-manifest.json](research/release-ops-manifest.json)。12项离线用例及新旧镜像各3次无网只读CLI导入冒烟通过，但尚未执行真实恢复库/生产迁移。将此SHA清单与新旧image ID附于每步记录，任何文件变化先重新核对直接受影响验证。

- `migrate.py`调用当前所选完整镜像的原migration owner，原报告、错误、版本和逐批事务不变。
- `snapshot.py`默认模式比较除两个JSON及五个新key值外的全部原列/其他表；`--include-derived`用于备份恢复全列相等。结构只能新增五个nullable LONGTEXT，无新索引；原列结构也必须相同。浮点/视图等当前不支持类型明确失败，不以近似结果通过。
- `query_diff.py`只允许恢复UUID，明确deny生产UUID；读取真实active admin/operator，装配真实读取依赖，固定aware UTC，对整个router响应（包括顺序、统计、动作）计算摘要。两边相同错误、空报告均失败。它不签JWT，不是HTTP/浏览器鉴权证据。

只在专属internal网络运行，无外网、无应用启动、无Worker，rootfs和对象/控制文件只读；所有证据独占0600保存。正式cases.json在恢复侧根据真实账号/可见域生成并审核冻结；覆盖每种角色两入口默认、所有分页/越界空页、无匹配/Unicode搜索及实际状态/QA/排序/到期/发布/表格动作，不能用两个示例case当正式矩阵。缺样本明确记录。每侧相同时钟/矩阵连续两次capture并compare通过后，再跨阶段比较。

O→C→R使用同一套恢复实例的三个顺序状态，独立进程各用完整冻结镜像：

1. **O旧布局**：恢复全列/对象相等 → 旧owner空游标verify（2/1） → 旧完整router两次capture与确定性对照。所有O进程退出，确认全列仍等于T0；保存旧响应摘要作冻结基线。
2. **C新布局**：新镜像dry-run逐批扫全量 → apply从双空游标逐批files→jobs → 双空游标verify（3/2） → 默认snapshot与T0比较并`--require-new-keys` → 对象/配置不变 → 新完整router两次及与O比较。
3. **R回退布局**：C进程全部退出 → 旧完整镜像dry-run/apply从双空游标重建2/1 → 旧verify → 原列/其他表/对象不变、五列保留 → 旧完整router两次及与O比较。不启动旧writer，不DROP列。

任何未知写结果、非派生列差异或污染都停止；不能把污染的阶段当T0继续。必要时从已验证备份重新恢复专属实例，不能恢复覆盖生产。O/C/R每个阶段记录耗时、峰值资源和完整报告，形成实际窗口预算及旧版可回退证据。

## 7. 生产迁移与失败停止点

仅在上述演练全部通过、身份/config再次核对一致、停写仍成立且剩余窗口足够时，才按单独批准进入生产apply。网络切换到已核实的项目网络，环境取T0受限运行配置，UUID固定为本页生产UUID；保留readonly rootfs、无生产对象可写挂载、固定image和只读ops，写库仅发生在显式apply。

实际容器内入口如下（UUID从本页固定值读取；凭据仅环境）：

```text
python /ops/migrate.py --expect-database md2word --expect-server-uuid <生产UUID> --dry-run --batch-size 100
python /ops/migrate.py --expect-database md2word --expect-server-uuid <生产UUID> --apply --batch-size 100
python /ops/migrate.py --expect-database md2word --expect-server-uuid <生产UUID> --apply --batch-size 100 --after-file-id <last_successful_file_id> --after-job-id <last_successful_job_id>
python /ops/migrate.py --expect-database md2word --expect-server-uuid <生产UUID> --verify --batch-size 100
```

dry-run各表用last_scanned续读至全量，不能复用dry-run游标开始apply。apply只推进已经提交的last_successful；files未完时jobs pending，保留既有成功游标。不自动重试未知写结果，不以exit0当全量完成。最后verify必须双空游标、exit0、all_ready=true、两表complete、无schema_missing/errors/mismatches。然后默认snapshot对比T0（require-new-keys），并核对对象/配置未变。DDL失败保留已加列，不DROP；任一门槛失败维持停写，进入旧JSON重建路径。

## 8. 同版本启动、回退和上线验收

所有旧API/Worker保持停止，核对新digest存在。用已保存JSON清单组装argv，不用eval或未经校验的shell字符串：

```python
files = json.loads(Path(RELEASE_DIR + '/release-preparation/compose-files.json').read_text())
argv = ['docker', 'compose', '-p', PROJECT]
for path in files:
    argv += ['-f', path]
subprocess.run(argv + ['config', '--quiet'], cwd=COMPOSE_WORKDIR, check=True)
subprocess.run(argv + ['up', '-d', '--no-deps', '--no-build', '--pull', 'never', 'api', 'worker'],
               cwd=COMPOSE_WORKDIR, check=True)
```

再次核对API/Worker的实际image ID均为本页新ID、APP_VERSION/DEPLOYMENT_ID一致、ready/Celery健康。freeze期间从已核实的本机`127.0.0.1:18000`或容器通道核对健康，公网请求此时预期为503，不能据此误判新进程不健康。保持freeze入口直到新进程身份与健康完成；然后恢复原站点并正常认证验收。MySQL、Redis和它们的卷不重建，不允许新旧写者混跑。

**常规回退**：发生迁移失败、完整结果差异、实例不符或上线不达标，先维持/重新进入上述drain→freeze，所有新写者停止并排空。在再次停写后采集当前原列/其他表/对象基线，保留此前已合法产生的新业务；用旧完整镜像的migrate.py从当前权威payload重建job/file 2/1，全量verify并与这份当前基线核对保真通过后，改用previous-compose-files.json的原9层启动统一旧API/Worker，核对旧image ID，再恢复原入口。五个新列保留；旧writer恢复后它们整体视为陈旧，再升级必须双表从头重建，不能只补NULL。

**覆盖恢复**：新版本已恢复写入时，不自动用T0覆盖新业务。只有另行明确批准恢复点、丢弃范围、对象/Redis同点恢复及消息去重决定，才执行全库覆盖恢复；普通回退授权不等于数据覆盖授权。保留全部证据，不清理共享Docker资源。

**上线验收**：正常登录会话下，两个默认首页各连续三次成功，API中位数≤2秒；页面进入到数据或明确空状态≤3秒。记录版本、角色、筛选/页大小、每次耗时，核对权限、分页、搜索、total/summary、动作；错误后loading检查在本地/隔离受控失败路径完成，生产不故意破坏数据或依赖。全部通过才关闭任务；构建/离线测试/健康检查都不能代替这些AC。

## 9. 构建完成时的审批快照（历史）

本轮已完成：固定源码/镜像、无网镜像检查、旧镜像完整冻结、未激活Compose和入口候选、现场只读身份/容量盘点、本地运维载体及直接验证。待批准的窗口动作：入口drain/freeze及reload、停止/排空写者、业务数据备份与隔离恢复/双向迁移演练；只有全部门槛通过后才进入另行批准的生产迁移与统一切换。若用户一次批准包含上述全部步骤，仍必须顺序执行并保留停止门槛，不跳过演练。覆盖恢复始终单独确认。

以下为窗口审批前快照，最新全部执行结果见production-execution.md：当时没有生产数据备份、恢复/回退演练、正式差分矩阵结果、迁移耗时或线上性能达标证据。任务保持in_progress，所有这些未执行项明确列入下一阶段审批，不能把本方案或工具存在写成通过。镜像构建和本地材料没有自动提交新代码或归档任务。
