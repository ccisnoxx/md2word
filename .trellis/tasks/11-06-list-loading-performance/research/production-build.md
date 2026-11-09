# 生产镜像构建结果（2026-11-07）

本轮已获用户批准：按固定提交构建镜像、固定版本，并准备生产切换/回退审批包。停写、备份恢复演练、生产迁移与切换没有执行。

## 固定产物

- 源提交：`b8b2779a9ee678f778ddb95890cebc3a0faff55e`。
- SSH目标：`hostdzire`，运行主机`scrapy`，linux/amd64。
- 发布目录：`/root/md2word-releases/b8b2779a-list-loading`。
- 镜像标签：`md2word-p0:b8b2779a-list-loading`。
- 镜像ID：`sha256:cbab7900f5172e5d24bcd743e5a2e8fcc73fcc1adb79d42392504862084e0667`。
- Compose固定引用：`md2word-p0@sha256:cbab7900f5172e5d24bcd743e5a2e8fcc73fcc1adb79d42392504862084e0667`。该引用已在目标daemon上inspect核对；产物在目标主机本地，镜像归档可用于恢复。
- `APP_VERSION=b8b2779a`，`DEPLOYMENT_ID=hostdzire-20261106T172447Z-b8b2779a-list-loading`。
- 源提交标签写入OCI revision/version，构建日志位于`release-preparation/build.log`。

## 构建和最小验证

实际daemon无registry mirrors、无HTTP/HTTPS proxy；活动builder是default/docker，linux/amd64。使用原始固定引用正常docker pull，成功：`docker.io/library/python:3.11.18-slim-trixie@sha256:b701198cb708b68d9413ca67d6311bd97c9389a2c5fe4da0511fc652642366cd`，未改registry或基础版本。

从远端bare source获取指定提交并git archive导出，开发目录未入运行包。从上一release复制57个wheel，逐个核对固定官方来源hash与当前lock完全匹配，不含pip工具wheel。使用维护中的docker/prod/Dockerfile构建，无生产.env/业务卷进入构建。

新产物无网络、只读rootfs、独立tmpfs、512MiB/1CPU临时容器的`pip check`及`import app.main, app.workers.celery_app`通过，Python 3.11.18。没有运行应用lifespan或连接生产依赖。镜像app/scripts/resources/sitecustomize共341个文件与固定Git archive逐文件SHA256一致，总manifest SHA256=`4b11672f55d2404c53eef1e1456e266e900537e65de2e7ddcf0530729b414353`。相关产品源码未变，复用已通过应用用例；新增检查仅覆盖本轮镜像产物。

## 编排准备

复核原9层Compose渲染后的全部environment与挂载与正在运行API/Worker一致。新建第10层`compose.override.yaml`和完整`compose-files.txt`，config比较只有6处变化：API/Worker各自的image、APP_VERSION、DEPLOYMENT_ID。没有执行compose up/stop/restart；未来用`--no-deps --no-build --pull never`只操作API/Worker，并先核对固定image ID。MySQL/Redis保持现有镜像和卷。

## 冻结回退资产

旧源提交`28cacd8a3afea2cd02fc36230ad9d6bc0e7b89e8`完整导出到`rollback/source`，旧镜像`sha256:77176d1903e9f266814b9ec3464551d1920c50b33683f3707889d570243dac7a`保留。旧镜像无网只读直接import原迁移TABLES，实际job/file版本2/1；新镜像为3/2。旧迁移脚本及全部340个运行文件SHA256与旧Git archive逐一一致，完整运行文件manifest摘要为`47552bca452ace5ab442b52cbd1a938ecaed8e820d22ed6aa314953a9282fcd8`。

两版镜像已导出到`/root/md2word-releases/b8b2779a-list-loading/release-preparation/release-images.tar`，文件权限0600，165046272字节，SHA256=`7a192020e3c94164b6f3b1673ee15411e87fa601313201245b25ca37b4096b83`。这是代码/镜像恢复资产，**不是数据库或对象备份**，不代表JSON重建回退已演练。

## 生产保持情况与证据

构建及配置准备后，原4个生产容器的ID、image、StartedAt、running状态与构建前完全一致，API/Worker继续28cacd8a。当前剩余磁盘约59.2GiB。只有独立release目录、镜像/构建缓存和本地任务材料新增，任务保留in_progress。

脱敏完整记录见[production-build-manifest.json](production-build-manifest.json)；schema身份、全部34张InnoDB表元数据、Redis持久化、卷容量、完整Compose链和前后容器身份一并保存。凭据、业务payload和账号内容未复制到本地任务记录。

## 未激活的入口维护候选

远端`release-preparation/nginx/`保存原站点、drain.conf和freeze.conf。drain在现有TLS server内仅放行原MinerU回调路径，其它请求503；freeze全部503。两份通过独立全局配置的`nginx -t`，只证明语法与include组合有效；尚未做流量运行验收、未修改活动站点、未reload。准备时发现实际include是`sites-enabled/*.conf`，首次断言在生成候选前停止，核对实际配置后修正并完成检查。候选hash见构建manifest。

## 运维载体冻结与导入检查

6个文件已复制到独立`release-ops`，归档SHA256 `63b2d9ec86bbf15eaf4c1bf3483d0dca745c1d807db4203e68fc89415d1d245a`，逐文件与已审查离线测试的源码SHA相符。旧/新完整镜像各执行migrate/snapshot/query_diff的`--help`，共6次无网、只读、cap-drop ALL、无业务挂载的CLI导入检查通过；没有执行数据采集或迁移。12项本地离线验证和5文件AST直接复用。

补充root只读schema元数据检查确认34表没有视图/例程/事件/触发器，列类型不包含当前snapshot不支持的浮点类型；不把此检查当全库保真或恢复验证。
