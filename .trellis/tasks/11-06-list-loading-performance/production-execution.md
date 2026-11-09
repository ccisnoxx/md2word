# 生产窗口执行记录（2026-11-07，已验收）

授权：用户批准按production-switch-plan执行停写、备份/隔离恢复回退演练，全部门槛通过后生产迁移及统一切换b8b2779a-list-loading并线上验收；失败重建旧JSON回退；全库覆盖恢复未授权。

目标hostdzire/scrapy；release `/root/md2word-releases/b8b2779a-list-loading`。完整受限执行状态、环境快照、原始迁移/摘要报告在该目录window/，秘密和业务内容不复制到本地文档。窗口开始2026-11-07T00:03:23Z，初始截止01:33:23Z；保留足够回退时间，未过门槛不做生产写入。

## 生产迁移前的过程快照

- 现场旧4容器、旧新image、原nginx及ops SHA核对一致；磁盘约59GiB，内存可用约3GiB。
- 已启用drain：普通列表/ready公网503，真实回调路径GET返回原405（仅检查代理路径，没有伪造POST回调）。119个job均终态；106回调为104processed/2ignored；25translation batch均succeeded；唯一Celery节点active/reserved/scheduled均空，队列/优先级/unacked空。
- freeze后优雅停API，再复核Worker及DB/broker，warm停Worker；0业务连接/事务/事件，T0固定。MySQL/Redis原服务保持运行，没有修改业务状态或清空队列。
- SQL逻辑备份58,489,238字节、var归档455,925,760字节、配置266,240字节；34表共6,291行。原始SQL/对象/配置权限受限保存，不输出业务payload。
- 专属同版8.4.9 MySQL恢复、UUID与生产不同、internal网络/无端口/无Worker。首次比对仅库默认collation不同（entrypoint预建0900_ai_ci，dump IF NOT EXISTS未覆盖）；只校正隔离库为源utf8mb4_unicode_ci后，全列和原列两种scope均全库34表/schema一致。初次失败报告保留，生产未改。
- Redis本轮BGSAVE生成RDB并复制，专属无网络Redis加载，4个非过期键的集合/类型/规范内容和TTL相同，原AOF卷不改。
- var原卷/恢复卷分别与tar逐文件比较通过；完整Linuxmanifest对比2,751条目和18配置文件的类型/文件大小/内容/owner/mode/mtime/link/ACL/xattr通过。目录分配st_size非tar可恢复属性，工具保留原值但不比较该项，文件size和其余metadata仍严格，修复有10项直接离线回归及独立复核。
- 恢复旧owner全量verify通过，files 1,928行版本1、jobs119行版本2。
- 已生成并审核真实用户矩阵，3账号（2admin/1operator）、109cases（45jobs/64incidents）。补足生成器未覆盖的status_group及incident stage/failure/retryable/retry_count/stalled筛选；缺实际样本按原生成报告计数保留。O双跑稳定109/109；C新版dry-run 20批、apply 21批共2,047行，files版本2/jobs版本3全量verify通过，原列/其他表/schema和对象保真。C两轮109响应稳定且与O逐项一致。R旧版dry-run/apply已完成、files版本1/jobs版本2全量verify及原列/对象保真通过；R第一轮109已完成，第二轮仍在运行，尚未生产迁移。

新增辅助脚本/测试仅为外置窗口载体，未改变冻结产品镜像、业务代码或既有6文件ops。当时原生产DB原列保真及线上性能门槛仍待后续步骤，任务保持in_progress；最终结果见下节。

生产执行器独立定向复核闭环：有效Compose全env/挂载及运行参数在迁移前核对，保留启动后实际容器核对；固定image_ref已在当前daemon解析为批准的新ID；up前再次核对渲染内容未变。恢复入口失败会原子还原freeze并记录nginx校验/reload结果，不记切换成功。实际只读渲染预检已通过，两项原审查问题已关闭。

## 生产切换与验收结果

- O/C/R全部门槛通过：各双跑109个完整响应稳定，O→C、O→R逐项一致；新版与旧版重建均全量verify及原列/其他表/对象保真通过。
- 生产dry-run 20批、apply 21批共2,047行；files 1,928行版本2、jobs119行版本3，空游标全量verify通过。新增五个nullable LONGTEXT，原列/其他表、原结构和对象核验通过。
- API/Worker统一为批准的cbab7900…镜像。完整env、挂载、命令、用户、网络、端口在迁移前与T0核对，up前渲染未变，启动后实际env/挂载再核对。MySQL/Redis原容器、image及StartedAt未变。
- 2026-11-07 01:18:34.979889Z恢复原入口（北京时间09:18:34）；停写维护约75分钟。API ready、唯一Worker节点及双队列通过，期间没有新旧写者混跑。
- 正常管理员登录，默认页大小20：普通列表默认74条、首页20行；异常列表6条、首页6行。3账号（2admin/1operator）的权限/动作依据冻结真实数据109场景完整router矩阵；浏览器实际登录为admin，未冒称operator浏览器认证。

| 最终同步采样 | 连续三次API秒数 | 中位秒数 | 三次数据出现秒数 |
| --- | --- | --- | --- |
| 任务工作台 | 1.5089 / 1.5020 / 1.9201 | 1.5089 | 2.0705 / 2.0604 / 2.4470 |
| 异常处理 | 1.0227 / 1.0901 / 0.7584 | 1.0227 | 1.4833 / 1.5632 / 1.2350 |

6次均HTTP200、真实网络传输、无搜索/默认排序/page1。接口中位≤2秒、每次数据出现≤3秒均通过；三次样本不称为p95。

计时证据使用浏览器原生ResourceTiming（状态200、transferSize>0）及点击前安装的临时DOM观察器，数据就绪后双requestAnimationFrame记录可见页面，再删除观察器。初始测量受自动化动作约3.23秒固定等待影响，只是页面上界，不是实际超标；原始初测与最终采样均保留。首个受控进入与后续预热样本分列，未把它们称为进程冷启动。初始普通API三次1.8068/2.2842/1.9672秒，中位1.9672秒；异常0.7277/0.9090/1.1472秒，中位0.9090秒。

普通列表实际第二页200、20行、total74，前后页统计一致；无匹配搜索普通0.441秒、异常0.9082秒，均200并出现明确空状态。异常仅1页，上一页/下一页正确禁用。两页分别在当前标签页临时阻断列表GET形成Network Error，原错误提示可见、loading消失、刷新可用；解除阻断后正常请求及默认页面恢复。临时阻断与DOM观察器已清理。浏览器证据时间01:32:44.560Z，早于初始窗口截止01:33:23Z。

收尾复核首次误把nginx文件名里的旧子域当实际域名，公网连接关闭；改按配置中server_name `md2word.962850.xyz`后，公网ready200/status=ok/version=b8b2779a，必需检查均通过。无代理环境。01:38:49Z完成主机复核及专属演练MySQL/Redis停止，生产四容器保持运行。备份、隔离恢复卷、新旧镜像和受限报告保留；没有进行生产旧JSON重建或全库覆盖恢复。

备份目录：`/root/md2word-backups/list-loading-b8b2779a/20261107T000844Z`。完整受限原始证据：release/window/。脱敏结果见[主机验收](research/production-acceptance-result.json)、[浏览器采样](research/production-browser-acceptance.json)、[执行器复核](research/window-switch-review.md)。相关产品源码/依赖/夹具未变，既有通过结果直接复用；本轮没有重跑应用套件。外置窗口Python脚本新增/更新中文注释、docstring及开发输出。

任务已标记completed并保留原目录。本轮运维材料与记录未提交；没有运行archive/add_session或产生额外bookkeeping提交。

## 2026-11-09 本地材料整理

本次仅整理本地索引、待批准提交计划与证据清单，复用11月7日已通过结果；没有重新探测或变更生产。验收截图按原字节保存到[production-acceptance.jpg](research/production-acceptance.jpg)，原外部文件仍保留。历史审批manifest与已执行脚本不重写；材料时点、SHA差异及验证复用范围见[材料索引](research/ops-materials-index.md)。
