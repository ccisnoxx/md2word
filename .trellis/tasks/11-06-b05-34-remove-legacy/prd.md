# B05 第 3、4 步
删除旧 stage 调度/启动重放、StageWorker、旧 jobs 服务/未挂载路由/仓储及旧转换运行时和专属测试。正式 DocumentIR + document_jobs + renderer 为唯一实现。
保留 docx_rules、table_html_parser 最小闭包、jobs 共享模型/快照/路径、job_events 全部读写与建表、DocumentIR v1 回退、正式 MinerU 回调与其余健康检查。
不迁移旧任务，不 DROP TABLE，不访问外部服务，不 commit/push，不改任务 manifest 或 worktree 外文件。
## 验收
- AC-1：app/scripts/tests 已删除符号及模块静态零引用，记录前后对比。
- AC-2：测试配置 build_runtime 与 Celery 导入、compileall app scripts 成功。
- AC-3：共享规则、表格解析、jobs 共享模型、job_events、v1 回退保留且定向测试通过。
- AC-4：指定 OpenAPI 快照与旧 API 移除测试通过。
- AC-5：用户指定正式阶段、direct、renderer、本地转换及现有健康/回调方法通过；基线失败单列不修复。
- AC-6：记录文件删除、行数及专属测试删除理由。
