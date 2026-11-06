# 生产发布与切换审批方案

状态：本地提交已获批准；推送、发布分支集成、镜像构建及生产切换未执行。本文件为可审核顺序与门槛，执行前需补齐现场身份和运维载体；当前不申请直接执行迁移。

## 1. 发布身份与代码集成

- 候选源为分支 `codex/list-loading-performance` 的本次修复提交；提交后以 `git rev-parse HEAD` 取得完整SHA，并在交接记录中固定。
- 推送目标是该任务分支，批准后可推送；当前发布基线为本地main，目标发布分支及远端最新包含关系在集成前核对。合并/推送不因本地提交自动获得授权，不新增GitHub Actions或CI要求。
- 候选镜像建议使用 `md2word-p0:list-loading-<提交短SHA>`，APP_VERSION取发布源提交，DEPLOYMENT_ID取本次发布标识。镜像构建后记录真实image ID/digest，API/Worker必须一致；当前没有构建产物，不能把建议标签当成已验证镜像。
- 冻结旧部署完整源码/镜像及旧迁移依赖。历史已测源28cacd8a、镜像77176d…；本地baseline25860865相关scripts/docker/requirements与它无差异。这是冻结来源证据，窗口前仍需重新核对真实运行态。

## 2. 构建准备（另行确认执行）

遵守维护中的docker/prod/Dockerfile和锁：linux/amd64、CPython3.11.18、固定基础镜像、57个官方hash核对的运行wheel；requirements/wheels不在Git archive内，必须单独备齐。先核对实际daemon镜像mirror/proxy及活动builder，再按原固定引用正常拉取；不因直接curl超时改源。仅构建新API/Worker镜像，不重建MySQL/Redis。具体维护入口见research/release-preparation.md。

生产使用冻结基础Compose与既有override链。取实际容器labels及上次成功release的compose-files.txt，按顺序保留全部-f、环境、挂载和外部网络；不能使用仓库单份Compose直接up。新override只切换API/Worker镜像和发布标识；用完整config核对有效差异，不输出秘密。

## 3. 申请停写窗口前必须落实

- 新旧完整代码/镜像及依赖已固定，旧工具的2/1重建能力可复核；当前候选的旧文件名入口已经生成3/2，禁止用于回退。
- 目标DB的server_uuid、库名、版本、连接位置以及完整Compose链现场核对；迁移CLI本身不绑定UUID，需在执行载体中做明确比对。
- 全库与对象/配置卷备份的确切命令、受限保存目录、恢复点、恢复责任及隔离恢复命令。先确认恢复实证，再进入变更；不把源码目录tar当作完整备份。
- 双表原payload/时间/业务列以及其它表的行数/hash基线与比较载体；不得导出明文业务内容到会话。
- 使用固定as_of、真实可见域、完整冻结旧/新owner的结果差分载体，覆盖条目/顺序/统计和动作；任一侧报错都阻断正常验收，双方相同错误不算迁移成功。
- 写者清单：API/回调、两类队列Worker、内联执行、清理/导入/修复/回填脚本、外部调度/人工SQL；确认在途工作和事务排空。

这些现场值与运维执行载体当前尚未落实，仓库中不存在历史引用的release/ops/migrate.py、snapshot.py、query_diff.py，不能直接引用或用本任务合成benchmark代替。研究清单明确列出缺口；后续先补齐上述可审核材料，再申请生产窗口，不边迁移边临时补方案。窗口时长应基于实际备份恢复和迁移预估确定。

## 4. 获批窗口内的执行顺序

1. 按已核对清单停止全部写者并排空事务；保持数据库/Redis及对象存储现态，不启动应用bootstrap做迁移前检查。
2. 完成批准的全库/对象/配置备份与隔离恢复核验，固定原列/其它表基线及旧查询结果。
3. 明确提供JOBS_MYSQL_HOST/PORT/USER/PASSWORD/DATABASE，凭据只在原秘密边界中注入；新迁移进程initialize=False，不读取.env。核对DB身份后dry-run遍历全量。
4. apply逐列前滚、files→jobs分批回填。dry-run续扫用last_scanned_*，apply续跑仅用last_successful_*；保留每批报告和退出码，不跳过失败数据，不DROP列。
5. 双空游标verify全量，要求exit0、all_ready=true、两表complete且无errors/schema_missing/mismatches。核对原列及其它表未变、固定时钟新旧结果一致；任一项失败不启动新写者。
6. 经完整Compose链只切换并启动统一新API/Worker，保留旧release和备份。核对实际镜像ID、APP_VERSION、ready和健康状态，随后正常认证用户验收。

已存在的迁移命令形状（仅在上述前提和批准窗口内执行）：

```sh
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --dry-run --batch-size 100
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --apply --batch-size 100
python scripts/ops/migrate_document_job_list_keys.py --backend mysql --verify --batch-size 100
```

两表游标和退出码详情见research/release-preparation.md及docs/runbooks/backend.md；单次dry-run/apply退出0不代表全量就绪。

## 5. 回退与停止条件

发生数据差异、未知写结果、实例/配置不符或验收失败时停止继续切换，不自动重试写操作。按批准的回退程序保持停写，以升级前完整冻结代码的旧回填工具从权威payload重建2/1JSON，旧版全量verify后恢复统一旧API/Worker。新增列保留；旧writer恢复后再次升级必须两表空游标重建。需要覆盖恢复业务数据时单独明确批准恢复点和覆盖范围。

## 6. 上线后验收与关闭

通过正常认证会话，两个默认首页各串行三次成功，接口中位数≤2秒；从进入页面到数据或明确空状态≤3秒。记录版本、角色、筛选、页大小及样本，区分API时间和页面时间；核对管理员/操作员权限、搜索、分页、total/summary及动作。验证错误响应后loading结束时使用本地或隔离的受控失败路径，不故意破坏生产数据或业务依赖。线上正常加载亦须实测。

全部验收通过后才关闭/归档本任务；目前保留in_progress。当前本地测试结果证明候选正确性与合成收益，不代替上述生产步骤。
