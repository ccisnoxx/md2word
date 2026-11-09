# 生产窗口切换脚本独立复核

范围：只读审阅主会话复制的 `window-production-switch.py` 和实际远端 `window_lib.py` 的本地副本 `window-lib.py`，与已审冻结release-ops及当前生产切换合同对照。本复核不执行脚本、不SSH、不连接数据库、不启动容器、不运行产品或运维测试，也不编辑待执行脚本。生产是否已迁移/恢复入口以主会话真实执行记录为准。

## Findings (fixed)

- **P1：全环境与挂载相等检查晚于新写者启动，已关闭。** 原脚本先 `compose up api worker`，随后才比较实际容器完整env与挂载，可能在Compose插值漂移时让新写者先写入错误目标。主会话已把相同argv/cwd的 `compose config --format json` 放到production-migration状态和apply之前；包含新镜像默认ENV的有效环境须等于T0加两处发布标识，挂载、command、entrypoint、user、working_dir、network和ports也必须等于T0。渲染image核对已审核的固定digest引用，生产启动之后仍检查实容器image ID、全部env和挂载。已核对实际代码顺序，修复满足原问题。
- **P2：入口恢复失败后磁盘配置不再freeze，已关闭。** 原脚本替换活动文件后若 `nginx -t/reload` 失败，会遗留开放入口文件。新脚本在该失败路径原子还原freeze候选，并重做nginx校验及reload，记录退出码后重新抛错；失败不会继续设置new-live或写成功结果。恢复reload也可能失败，其实际结果由受限记录明确保留，不能仅凭进入异常分支宣称运行入口已恢复。没有新增数据库覆盖恢复。
- **关键委托已补读。** `window-lib.py` 的目标、迁移循环、verify和snapshot比较已核对，见下方合同；此前“缺少依赖副本”状态已关闭。
- **最终四处修订已定向核对。** 第29—32行inspect已批准image_ref，断言其Id等于NEW后才使用该镜像Config；第70行在up前重新渲染并要求与迁移前完整rendered相等；第11行保存并校验活动freeze的字节，第113行失败时写回同一批字节；第4行设置 `os.umask(0o077)`，在新增日志/报告写入之前生效。未发现这四处修订引入新的合同问题。

## Findings (not fixed)

本轮两项具体问题和依赖证据缺口均已闭环，未发现新增阻断。该结论是脚本静态合同结论，不表示尚在运行的演练或生产切换已经成功，也不替代原批准门槛。

## window_lib关键委托

- `target()`固定库名md2word和窗口生产UUID；clone模式才读取恢复UUID。生产调用使用T0捕获的api.env、项目网络、OLD/NEW完整镜像，绑定只读ops目录、只读rootfs且无生产对象可写挂载。已审 `common.connection_factory` 对每条实际交给owner的连接核对数据库和server_uuid，之后按模式设置只读/可写事务，不是用另一条预检连接代替绑定。
- `migrate_all`每次调用都从空file/job游标开始，dry-run推进last_scanned，apply只推进last_successful；错误或工具非零立即停止，不自动重试未知写结果。两表status均complete且has_more均false才结束，100批上限耗尽会显式失败，不冒充完成。
- `verify`不带游标调用冻结owner；owner内部按batch遍历全两表，外层要求all_ready、两表complete、无schema_missing/mismatches/errors。没有把单批成功或工具exit0单独当完整通过。
- `op`将完整stdout/stderr保留在受限窗口文件，解析失败、容器非零或报告非零均抛错。主脚本只打印迁移批数/行数和verify摘要，不打印游标或业务payload。`compare_snapshot`调用已审比较器，非零比较结果断言失败；默认原列比较保留其他表，生产迁移后显式要求新key。

## 已核对的直接顺序

- 显式生产apply之前要求 `state.stage == rehearsal_passed`、rehearsal-result.passed、剩余窗口大于15分钟、活动入口freeze哈希、冻结ops哈希、旧API/Worker停止、MySQL/Redis身份及启动时间不变且仍运行、无DB事务和复制连接；再做源全列、var对象和配置与T0保真比较。rehearsal标志的完整证据由外层演练负责生成，切换脚本不会自行补齐尚未通过的R轮。
- apply后调用全量verify、默认原列snapshot并要求新key，以及对象保真检查。未出现DROP、原payload重写、dump覆盖恢复或生产var回灌命令；具体迁移owner行为沿用已审冻结载体。
- Compose只指定 `api worker`，带 `--no-deps --no-build --pull never`，不请求重建MySQL或Redis。新进程必须统一NEW image ID、T0全部env加APP_VERSION/DEPLOYMENT_ID两处变更、原挂载。
- freeze期间使用本机18000的ready通道，检查新版本、mysql/celery backend和全部required checks；Worker等待检查只有一个Celery节点且恰好两条预期队列。该检查有等待上限并在失败时停止，不以日志存在代替Worker就绪。
- 只有新进程身份、ready、Worker队列及日志门槛之后才恢复nginx入口。最终状态为 `new-live-pending-acceptance`，未把健康检查当作正常认证与性能验收完成。
- 当前失败默认抛出并停止，没有自动用T0覆盖生产；常规旧JSON回退需由主会话按批准顺序停写/停新写者、取当前基线后单独执行。

## Verification

- 静态复核：已读脚本、实际lib副本、直接健康响应和既有迁移owner合同；两处修复已闭环。
- 最终复核副本SHA-256：`window-production-switch.py` 为 `ddb9e4e3f5e845ad9a893c8d7fe5846437561790e20080257a1ca6b0e8754100`；`window-lib.py` 为 `d333d98fabf995e1f9859371f16b0d3da06700fe52c37f0ed219b8eed6e9114a`。
- 主会话另报实际读取 `compose-review.image_ref` 确为已批准的 `md2word-p0@sha256:cbab7900f5172e5d24bcd743e5a2e8fcc73fcc1adb79d42392504862084e0667`；两角色真实只读渲染前置比较已通过，记录在远端 `window/pre-start-render-precheck.json`，最终inspect引用并断言Id的片段也已在真实daemon只读通过。这是主会话执行证据，本复核未重复远端操作。up前重比渲染输入已加入脚本，但此处不将尚未执行的生产流程写成通过。
- Tests / Lint / TypeCheck：未执行；本轮只读派发明确禁止测试。
- 已知O/C各109cases双跑及跨版本一致、R迁移verify/原列/对象保真通过、R两轮router仍运行，均为主会话派发事实；本报告不改写为全部演练或生产切换已通过。
- 本复核只新增中文报告；未改产品、冻结载体或执行脚本。
