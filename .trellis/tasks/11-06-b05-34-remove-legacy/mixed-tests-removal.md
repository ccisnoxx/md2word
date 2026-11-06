# 混合测试删除

- `tests/test_fastapi_jobs_backend.py::test_health_ready_reports_stage_spool_status_counts`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_callback_rejects_non_parsing_job_status`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_find_job_for_callback_reads_nested_source_pdf_context`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_replay_pending_replays_pending_and_running_stage_messages_only`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_dispatch_skips_completed_conversion_message_without_rerunning_conversion`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_dispatch_skips_replayed_mineru_submit_after_batch_recorded`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_dispatch_skips_duplicate_callback_after_job_completed`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_enqueue_parsed_result_conversion_downloads_zip_and_completes_docx`：仅覆盖旧 stage/jobs 实现及其仓储。
- `tests/test_fastapi_jobs_backend.py::test_convert_parsed_result_fails_when_result_zip_download_fails`：仅覆盖旧 stage/jobs 实现及其仓储。

正式告警测试改用 callback 失败夹具，保留原权限、审计、去重与禁止真实发送断言。
