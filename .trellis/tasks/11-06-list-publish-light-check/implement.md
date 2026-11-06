# 实施与验证

1. 读取 PRD/design、backend 目录/错误/质量/列表查询合同，核对实际读视图调用链。
2. 子代理仅修改 service.py 与定向测试；主会话同步 Spec 和任务文档。
3. 新增列表零读取、状态拒绝矩阵、默认深度路径与 POST 拒绝、其他动作/非管理员保持的测试。复用本地替身，禁止真实外部服务。
4. 使用 PYTHONDONTWRITEBYTECODE=1 /Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest 加具体新增模块和现有类/方法；现有失败须在内存载入 git HEAD 的 service.py 后复现，不修历史测试。临时资源须清理，不能留下工作树临时目录或修改仓库外文件。
5. trellis-check 子代理独立审查默认值、唯一轻量调用方、POST 合同与测试证据；复用已通过检查，不跑广泛测试。检查 git diff/status 后按 schema 报告，不归档或记录会话。

## 执行结果

产品代码仅新增默认 True 的 check_publication_evidence 参数链，唯一 False 位于 list_jobs；未修改 schema/router/POST/前端/incidents。Spec 和 API 文档已按授权同步。修改的 docstring、注释和测试提示均为中文。独立 trellis-check 只读审查及夹具增量复核无未解决发现。

所有测试使用 PYTHONDONTWRITEBYTECODE=1 与 /Users/sc/PycharmProjects/md2word/.venv/bin/python；外层 Python TemporaryDirectory(dir=本任务目录, prefix="validation-") 将 TMPDIR 传给测试子进程，完成即清理，没有 worktree 外测试文件写入。

首轮实际子命令：

```sh
/Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest tests.test_document_job_list_publish_light_check tests.test_document_job_list_query_v2_service.DocumentJobListV2PublicationTests.test_legacy_real_table_report_publication_action_is_page_bounded tests.test_document_job_download_availability_api.DocumentJobDownloadAvailabilityApiTests.test_list_detail_and_incidents_use_the_same_metadata_only_owner tests.test_document_job_download_availability.DocumentJobDownloadAvailabilityTests.test_default_download_actions_share_existing_issuance_rejections
```

6 方法 / 3.524 秒：新增两 API 方法及既有页内解码方法通过；新增状态夹具有 2 错误；两个旧方法有 1 失败和 11 错误。单跑新增状态类定位后修正：用真实发布替代禁止的普通 published 更新，running 使用 unreviewed。随后仅运行受影响目标：

```sh
/Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest -v tests.test_document_job_list_publish_light_check.DocumentJobListPublishLightCheckTests.test_admin_list_skips_evidence_but_default_read_views_verify tests.test_document_job_list_publish_light_check.DocumentJobListPublishStateTests
```

2 方法 / 1.847 秒，OK。最终新增 3 方法和直接修改的既有 1 方法全部通过；其他成功结果按未变输入复用，未为汇总重跑。

基线复现：同样隔离临时目录，通过 Python stdin 子进程用 subprocess.check_output(["git", "show", "HEAD:app/domains/document_jobs/service.py"], text=True) 取源码，再 exec(compile(source, service.__file__, "exec"), service.__dict__) 仅加载到内存；确认 build_job_read_view 无新增参数后，unittest.loadTestsFromNames 运行上述两个旧方法。结果 2 方法 / 1 失败 / 11 错误，与候选相同，未修改旧测试：

- incidents diagnostics 经 list_files → verified_current_preview_files → read_current_preview_evidence 读取预览，触发旧“GET 不读取正文”断言。
- 下载动作旧夹具的 11 子案例在创建文件时因“新文件对象路径缺少固定位置的独立 file_id”失败。

## 验收证据

- AC-1：file/SQLite 管理员列表 prepare_publication_evidence=0、read_file_content=0；既有实际表格发布夹具 guard=0，页内解码约束保留。
- AC-2：12 组状态矩阵及真实已发布拒绝，内部检查精确等于原 not_checked 对象。
- AC-3：默认 observed_result 读视图、build_available_actions 和 publications 前检查继续深核；坏证据详情/前检查保留 publication_result_unavailable、publication_storage_unavailable、publication_hash_mismatch。
- AC-4：列表 enabled，POST 对三类错误仍为 409/503/409，error_code 与 reason_code 保持；无发布记录或持久任务变化。
- AC-5：其他动作及非管理员动作字典与默认深核视图一致；ready_to_publish 仅返回投影，坏证据详情保留原状态。
- AC-6：异常中心在筛选分页前对全部可见任务执行默认深核，本次未修改；建议另行评估。

git diff --check 通过。测试临时目录已清理。未执行全仓/完整前端测试、真实 MySQL/生产/Provider/MinerU、线上或发布门禁；未提交、推送、发布、archive/add_session。任务为 review，表示待外部验收，不代表 Claude 已验收。

## 第二轮执行计划

1. 保留第一轮全部差异，读取新增异常分类/分页调用链。
2. implement 子代理拥有 incidents.py/service.py 与定向测试，主会话拥有文档；最小抽离分类所需观察并分页后构建完整动作。
3. 新增真实服务/API多任务计数与改前对照，覆盖筛选/排序/分页/计数、有效复核失效、重试原因、降级/停滞、非admin、空页；禁止真实外部服务。前后基线读取 git HEAD incidents.py（第一轮未修改），服务使用当前第一轮候选即可。
4. 运行新增模块、异常中心既有具体方法与上一轮 3 方法+直接更新的列表方法；旧失败仅内存基线复现，不改旧夹具。所有测试 TMPDIR 置于本任务 TemporaryDirectory 内，退出清理。
5. 独立 trellis-check 只读检查语义等价与成本界限，主会话同步 Spec/API、最终 diff/status 和结果记录。不 commit/archive/add_session。

## 第二轮最终结果

本轮修改 incidents.py、service.py 必要共享观察和 retry owner、新增 test_document_job_incident_publish_light_check.py；主会话同步 Spec/API。完整动作仅页内构建，分类保留原有效复核主件门控与 retry 条件。分类前到期按原实时钟失效，分类后以 observed_result_view 复用已校验结果，避免条目与统计不一致。没有第二个发布控制开关、schema、前端或路由改动；diagnostics/bulk保持原完整路径。独立只读审查及最终时钟修正复核无未解决发现。

新增分类前到期回归先在旧候选验证 RED（1 方法 / 0.013 秒，旧候选保留 blocked，旧全量流程 total=0），随后移除 helper 的 as_of 参数。最终实际子命令如下；外层始终 PYTHONDONTWRITEBYTECODE=1，TemporaryDirectory(dir=本任务目录, prefix="validation-") 设置子进程 TMPDIR，退出即清理：

```sh
/Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest -v tests.test_document_job_incident_publish_light_check tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_queue_filters_priority_and_diagnostics tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_bulk_retry_skips_non_retryable_and_refreshes_status tests.test_degraded_page_display.DegradedPageDisplayApiTests.test_detail_and_incident_queue_list_degraded_pages
```

7 方法 / 3.103 秒全部通过（新增异常 4 方法、既有异常 3 方法）。新增模块首次两个夹具错误为非法 queued stage、普通更新不能改质量贡献，已按合法 uploaded 及既有发布夹具锁内历史槽方式修正，不涉及产品兜底。

本轮先前实际运行的组合命令：

```sh
/Users/sc/PycharmProjects/md2word/.venv/bin/python -m unittest -v tests.test_document_job_incident_publish_light_check.DocumentJobIncidentMetadataTests.test_page_reuses_classification_observation_and_preserves_result_gates tests.test_document_job_list_publish_light_check tests.test_document_job_list_query_v2_service.DocumentJobListV2PublicationTests.test_legacy_real_table_report_publication_action_is_page_bounded tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_queue_filters_priority_and_diagnostics tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_bulk_retry_skips_non_retryable_and_refreshes_status tests.test_degraded_page_display.DegradedPageDisplayApiTests.test_detail_and_incident_queue_list_degraded_pages tests.test_document_job_download_availability_api.DocumentJobDownloadAvailabilityApiTests.test_list_detail_and_incidents_use_the_same_metadata_only_owner
```

9 方法 / 4.450 秒，8 通过、1 历史失败。其中 AC-11 的第一轮新增 3 方法和既有页内方法均通过；最终时钟修正只影响异常 classification helper，普通列表不调用该 helper，故复用 AC-11 成功结果。

旧 metadata-only 方法通过 Python stdin 内存同时加载 HEAD service.py 与 HEAD incidents.py 后复现：1 方法 / 0.874 秒，1 同样失败、0 错误。diagnostics → list_files → _list_files_for_job → read_current_preview_evidence → read_file_content 触发旧“GET 不读取正文”断言；本轮保留诊断行为，未修改旧测试。上一轮旧下载对象键夹具问题未维护，本轮不重跑无关方法。

最终真实 HEAD 源码对照：使用 types.ModuleType("incident_head_baseline")，从 git show HEAD:app/domains/document_jobs/incidents.py 取得源码并 exec(compile(...), old.__dict__)；仅该测试子进程把新测试模块 full_scan 替换为 old.DocumentJobIncidentService(incidents.document_job_service).list_incidents(**query)，并冻结旧 incidents.utc_now=fixtures.NOW。持久测试仍冻结旧全量编排，不读取动态 HEAD。

运行 test_all_filters_sorts_summaries_roles_and_empty_pages_match_full_scan、test_expiry_before_classification_matches_full_scan、test_api_only_builds_page_actions_and_keeps_diagnostics_and_bulk_full，3 方法 / 2.269 秒通过；共 185 个前后对照请求（45 查询×2角色×file/SQLite=180，分类前到期1，API4）。计数 spy 的初次临时脚本嵌套错误已修正，仅测量脚本受影响，最终对照通过。

每个API场景为5可见任务、1页内结果，file与SQLite一致：

| 角色/版本 | 完整动作读视图 | prepare_publication_evidence | read_file_content |
| --- | ---: | ---: | ---: |
| Admin HEAD | 5 | 1 | 12 |
| Admin 最终候选 | 1 | 0 | 0 |
| Operator HEAD | 5 | 0 | 0 |
| Operator 最终候选 | 1 | 0 | 0 |

AC-7、AC-8：零内容读取、完整动作次数仅页内；筛选必须全量保留 retry/有效复核/降级/停滞及搜索摘要元数据。
AC-9：全部分类/筛选/排序/分页/summary对照相等，包含空页、角色隔离、复核失效、分类前及分类后到期边界。
AC-10：publish 状态准入/not_checked，其他动作保持；diagnostics/bulk-refresh默认完整核验也有运行证据。
AC-11：第一轮4个定向方法本轮重跑通过，AC-1～AC-5保护保留。AC-6原调查结论已回答，本轮按后续授权优化列表，诊断/批量路径保持。

最终 git diff --check 通过，测试临时目录清理完毕。仍需全量扫描可见任务元数据以保持筛选/统计，没有SQL下推或总耗时承诺；未运行生产/真实MySQL/Provider/MinerU、完整前端/全仓/发布门禁。未提交、推送、发布、归档或add_session。任务review只表示待外部验收。
