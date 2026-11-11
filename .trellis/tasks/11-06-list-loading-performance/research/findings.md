# 调查证据与限制

日期：2026-11-06（Asia/Shanghai）。调查时 root HEAD=25860865，初始工作树干净。

## 本轮直接证据

- 公开 `GET https://md2word.962850.xyz/api/v1/health/ready`：HTTP 200，version=28cacd8a，deployment_id=hostdzire-20261106T152635Z-28cacd8a，effective_repository_backend=mysql；curl total=0.905806s、ttfb=0.899743s。只保留所需字段，不保存完整配置/健康响应。
- `git merge-base --is-ancestor 74cea825 28cacd8a` 返回 0；`git diff --stat 28cacd8a HEAD -- app frontend` 无输出。由公开版本和仓库关系推断线上声明版本已含发布证据轻量优化；没有通过 SSH 核对实际镜像文件。
- 相关部署记录：`.trellis/tasks/archive/2026-11/11-06-table-placeholder-failure-diagnostics/deployment.md`，记录同版本及 API/Worker 镜像身份。本轮未重跑其部署验收。
- `JobsPage.vue:571` 和 `IncidentTriagePage.vue:728` 的请求均有 finally 清理 loading；`api/client.ts:17` 的超时为 50,000ms。这只是代码事实，不能排除页面重入或线上加载异常。
- `document_job_list_query.py:120-121` 对两张表独立 shape 校验；MySQL 仓储在 RR 只读事务调用该查询。
- `mysql/document_jobs.py:117` 的 list_document_jobs 查询所有 payload 并逐行解码；`service.py:1438` 才做可见性过滤及 _effective_job；`incidents.py:86` 再分类。`service.py:828` 与 `service.py:2812` 是可能重复的文件观察位置，保留不同观察时序，不能直接合并。
- 既有 `test_expiry_before_classification_matches_full_scan` 和 `test_page_reuses_classification_observation_and_preserves_result_gates` 已明确到期与主件门控合同，本轮只阅读、未执行。

## 并行候选（只读获取，非本轮运行结果）

1. `${TASK_WORKTREE_ROOT}/list-ready-once/.trellis/tasks/11-06-list-ready-once/`：PRD/design/implement/validation 记录 13→11 条 SELECT、61 项定向通过，真实 MySQL 未跑。记录引用历史生产两条校验合计 5.19 秒，但本轮没有取得该线上原始 trace，因此只作历史线索；净收益不能直接等同 5.19 秒。实现为请求内合并校验，不是按名字理解的启动时只检查一次。
2. `${TASK_WORKTREE_ROOT}/list-key-columns/.trellis/tasks/11-06-list-key-columns/`：已有五个全文列、投影版本 job v3/file v2、迁移和验证记录。合成 JSON 体积下降 99%以上不等于真实接口收益。Docker daemon 不可用导致真实 MySQL not_run；禁止据此声称完成引擎或线上验收。
3. 两 worktree 均有未提交修改，共享 SQL/spec 文件有重叠；未修改、提交、合并、复制其产品代码，未改变其任务状态。

## 尚未取得

认证的 document-jobs/document-job-incidents 实际请求计时、浏览器首屏计时、最新生产数据量、完整 SQL/解码/动作分段测量、两个候选组合后的真实 MySQL 结果。本轮没有访问 VPS、没有登录/导出认证信息、没有新增业务请求或运行应用测试。

## 实施阶段新增实测（跨 2026-11-06/07，Asia/Shanghai）

已获用户批准进入实施。Chrome 复用原已登录 admin 页面；任务首页3次中位数13.191875秒，异常首页3次中位数2.350973秒，任务翻页13.188278秒，无匹配搜索11.897307秒。全部200。原异常页面已恢复、Network采样关闭，未修改设置或业务数据。详见 browser-baseline.json；DOM就绪计时未可靠取得。

通过hostdzire只读核验当前API镜像与部署记录一致，未重启/部署。独立Python进程只导入当前安装模块并使用initialize=False，MySQL连接会话transaction_read_only=1；没有调用应用启动/初始化。production_readonly_probe.py经SSH stdin送入现有容器，不写远端文件，仅输出计数/体积/耗时。全库119任务/1928文件，单一tenant/company域，默认列表74条，与浏览器一致。线上MySQL8.4.9。原13条SQL合计11.419752秒、仓储11.734191秒；Q00=3.044212、Q01=2.253691秒。job查询JSON平均111623字节、最大2377676；file查询JSON平均8995字节、最大2376229。实际文件/任务payload未导出。

异常路径：读取119个payload 0.010649秒，模型解码0.068135秒；74可见任务的首次有效复核0.001220秒、文件读取0次；分类主件视图1.943747秒，文件读取68次合计1.449863秒。此阶段探针不构造用户身份、不调用HTTP鉴权，不计页内动作/序列化；最终API耗时以上述真实浏览器样本为准。

独立本地MySQL已建立，用于候选真实引擎验证；8.4.13 arm64与线上8.4.9及主机资源不同，性能只作机制验证，不等于上线验收。
