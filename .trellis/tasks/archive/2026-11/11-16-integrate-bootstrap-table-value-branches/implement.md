# 执行与验收

1. 核对原始提交范围、试合并结果和工作区状态。按仓库策略扫描原分支待推送的历史。
2. 冷启动候选保留 main 的运行时和语言实现，补齐 Compose 验收脚本及归档。检查语法、启动接线、Git 差异和归档一致性，按保留历史的方式提交并创建冷启动 PR。
3. 参数表按检测与实物证据、任务与交付 API 两个范围分工。检查旧报告、已认证 finding、默认关闭、名单隔离、同包事务与 main 发布阻断。使用既有 unittest，覆盖 test_parameter_table_value_column_binding、test_document_job_list_publish_light_check、test_document_job_delivery_state_api，以及分支中直接涉及的 PDF 绑定、同包核定及权限用例。根据运行代码导出并核对 OpenAPI。
4. 独立复核权限、摘要、事务、未认证阻断和兼容性。验证冲突标记清空、变更范围准确。给每个分支生成一个保留原始历史的整合提交。Trellis 任务归档使用 task.py archive --no-commit，以便记录随参数表整合提交。
5. 推送参数表 PR，确认 GitHub 合并、远端祖先关系与最终树。逐个清理已合并分支，保留原 Claude 工作区内容，同步本地 main。
