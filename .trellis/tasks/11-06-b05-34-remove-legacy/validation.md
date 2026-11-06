# 最终验证记录

## 结论

旧转换/任务实现移除完成；AC-1/2/3/4/6 已有本地证据，AC-5 的两项指定用例仍为基线失败。额外定向检查还复现两项历史夹具失败，不修改历史夹具或正式行为来使其变绿。

59 个文件删除，共 15512 行；已跟踪整体 diff 新增 307 行、删除 19606 行。逐文件与逐测试理由见 deletion-inventory.md/json；170 个原方法名消失，其中 169 项旧专属用例移除，1 项仅去掉旧导出断言后重命名，正式断言保留。

## 执行环境

所有 Python 命令使用 `/Users/sc/PycharmProjects/md2word/.venv/bin/python`、`PYTHONDONTWRITEBYTECODE=1`。测试 `TMPDIR` 指向本任务目录，自动清理；compileall 缓存使用 `/Users/sc/.codex/tmp/b05-34-compile-cache`（用户允许的 Codex 缓存）。未访问生产、真实数据库、Provider 或 MinerU，未运行 discover、前端完整测试或发布门禁；只移除 check_release.py 中4个已删测试目标，没有调用该门禁。

## 指定检查

- 删除前与整合后均执行 `python -m unittest -v $(cat .trellis/tasks/11-06-b05-34-remove-legacy/test-targets.txt)`：26 项，24 通过、同样 2 项失败。方法全名见 test-targets.txt，输出为 baseline-tests.log / post-tests.log。
- 已通过全部用户指定 direct、四方向真实阶段边界、fan-in失败落库、v1 renderer回退、renderer evidence 阻断、正式最小 MinerU→DOCX。
- 指定 OpenAPI 导出/临时快照一致性及旧HTTP入口404测试最终仍通过；最终额外 HTML 跨行跨列表格渲染测试通过，见 final-contract-tests.log。该次批量命令误写一个额外类名导致加载错误，随后纠正为真实类名单独执行并识别下述既有失败；不计为产品故障。
- `import app.main; build_runtime(test_settings)`、`create_celery_app(memory_settings)`、`celery.loader.import_default_modules()` 通过，注册 document_jobs.run 与 document_jobs.translate_batch；没有启动真实broker连接，见 runtime-smoke.log。
- `PYTHONPYCACHEPREFIX=/Users/sc/.codex/tmp/b05-34-compile-cache python -m compileall -q app scripts` 退出0。
- `python .trellis/tasks/11-06-b05-34-remove-legacy/verify_removal.py`：408 Python文件 AST 通过，重点符号引用76→0，59个已删模块的AST导入及文本引用0。
- `git diff --check` 通过。docx_rules、table_html_parser、正式 document_jobs/DocumentIR/renderer/MinerU callback 源文件与 HEAD 无差异。

## 其他定向验证

- runtime-removal.md：三个共享规则模块21项通过。
- jobs-removal.md：共享模型4项通过。
- persistence-removal.md：三后端正式metadata、event持久化、schema与runtime/readiness共6方法最终通过；首次遗留旧夹具变量引用已删后单独重跑通过。
- `python -m unittest -v $(cat .trellis/tasks/11-06-b05-34-remove-legacy/additional-test-targets.txt)`：31项，25通过，5项pilot测试夹具问题修复后按下述8项验证通过，1项正式文件保留期用例为基线失败。保留正式配置、MinerU下载边界和假发送测试。
- compatibility-tests.log：真实pilot preview、非pilot拒绝、kill switch、注入发送端去重、rate limit、配额控制、pilot配置状态以及health metrics共8项通过。测试使用合成旧许可告警，不代表正式发送链路可激活。
- `python -m unittest -v tests.test_mineru_result_root_uniqueness.MinerUResultRootUniquenessTests.test_single_root_prefers_v2_over_legacy tests.test_mineru_result_root_uniqueness.MinerUResultRootUniquenessTests.test_legacy_only_in_single_root_is_selected`：2项通过。
- 独立只读复核最终无剩余可操作缺陷，见 review.md。

## 保留的基线失败

1. `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_health_ready_blocks_p0_document_jobs_in_production_when_required_config_missing`：旧断言期待 mineru_callback_url_missing，现有正式逻辑未生成此blocker；修改前后相同。
2. `tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_failed_mineru_callback_is_queued_then_worker_marks_failed`：创建响应缺job_id，后续 KeyError；修改前后相同。
3. `tests.test_artifact_retention.DocumentFileRetentionTests.test_document_file_retention_plan_marks_expired_without_deleting_objects`：旧对象路径缺独立file_id，被现有文件身份合同拒绝；以git archive HEAD在任务临时目录复现，retention-baseline.log。
4. `tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_prefers_v2_content_and_keeps_legacy_only_fallback`：旧双版本夹具被当前唯一结果根目录校验拒绝 mineru_content_list_ambiguous；以git archive HEAD隔离复现，legacy-input-baseline.log。两个当前单根目录选择测试通过，正式代码未改。

## 保留边界与风险

- OpenAPI所有180个paths不变，仅HealthMetricsResponse/HealthOpsAlertItem/HealthOpsAlertSummary旧stage内容删除。HEAD已有 DocumentJobFailureDiagnosticResponse.source_page_count/page_count_basis 两字段缺失于仓库快照，隔离生成已复现（openapi-baseline-drift.log）；本次不补无关内容，因此不能声称仓库快照与所有当前schema完全同步。
- `job_events` 三后端仓储类AST与DDL保持，正式SQLite/MySQL document_jobs.py逐字未变。jobs/job_files/stage_messages只移除CREATE；现存空表交B08，不执行DROP。
- `stage_message_lease_seconds` 被正式callback执行使用，保留。健康metrics.jobs和stage_messages为空对象以保持现有前端读取合同，无旧仓储读取。
- 真实Slack pilot固定许可旧告警码的规则保持；健康不再产生该旧告警，当前无active发送目标。迁移告警许可需另行授权；本次未改变权限或外发行为规则。
- 新增或实质修改的注释、docstring和文档为中文；共享业务实现未添加无关说明。
- 未commit/push/发布/归档/add_session，未改任务manifest。任务状态是本地工作报告，不表示用户或Claude已验收。
