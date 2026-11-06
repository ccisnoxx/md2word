# 设计
从 main/AppRuntime 移除旧装配和启动重放；正式 DocumentJob 恢复保持。删除旧 jobs 私有服务、路由、仓储、schema 三张旧表的 CREATE，保留 job_events。健康检查仅移除旧消息/旧 jobs 读取，其余字段与判断保持。
旧运行时按真实 import 图删除，table_html_parser 与 docx_rules 保留，不改正式 IR/renderer 行为。发现未预期正式依赖时保留并记录依赖链，不猜测替代。混合测试只删旧实现测试与夹具，正式测试保持。
生产三张空表留给 B08 治理，本任务不新增或执行 DROP。
