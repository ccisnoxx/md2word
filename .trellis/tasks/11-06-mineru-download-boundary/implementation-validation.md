# B03 实施与定向验收记录

日期：2026-11-06。基线：main@79f20cef9ca0bb1a59af635e2408e130c4935e2d。用户已在最终规划摘要之后确认实施，仍禁止 CI、全量测试、提交和推送。

## 实际变更

- URL 策略迁至 app/clients/mineru_result_url.py；HTTPS/host 规则共享，新增拒绝 userinfo、无效端口及安全解析错误，删除旧单函数模块。
- MinerUClient 的名单为必传参数；两个生产工厂注入 Settings.allowed_mineru_result_hosts，配置 resolver 保持。
- 下载专用 Session.send 在每次真实发送前检查目标，保留 Requests 的合法跳转、默认 30 次上限、TLS、代理/CA 和 trust_env 行为；不复制 API 会话凭据。
- 通过 response hook/ExitStack 释放取得的响应，包含跳转响应体读取失败、get 尚未返回且异常没有 response 的路径；不改库重定向实现。
- 最终 200 后才打开目标文件，非法地址/越界跳转/非 200 不截断既有文件。网络/策略错误为安全 MinerUError，抑制上游异常链，应用下载日志不再包含完整 URL。
- 正式 parsing/mineru_failed、legacy parsed_result_download_failed、checksum、CAS 和 Artifact 登记顺序保持。
- 新增定向测试模块；更新 callback 文档与 error-handling Spec。新增/实质修改的说明、docstring、下载日志及错误文本采用中文。

## 新增定向测试：通过

命令：

    .venv/bin/python -m unittest tests.test_mineru_download_boundary

实施代理首次执行时，新 fixture 的 single_tenant_public + eager/file 组合在创建任务阶段被 readiness 拒绝；仅把新增 fixture 改为默认 internal 本地模式后，10 个方法通过（0.644 秒）。未修改旧测试夹具。

独立检查代理发现部分合法下载的日志断言可能对空日志通过，补充保存/恢复 logger 级别、固定 INFO 和成功日志存在断言，共 3 行测试改动。T06 原本已有 assertLogs，因此不是产品缺陷或整个 AC07 缺失。该共享 setUp 改动后，仅重跑新模块：10 个方法通过（0.633 秒）。这轮结果为最终候选证据。

| 方法（均以 test_ 开头） | 计划与验收 | 结果 |
|---|---|---|
| initial_url_rejected_before_transport_and_output | T01；AC01/AC02 | 通过，包含非法初始地址、空名单、userinfo、无效端口、输出 sentinel。 |
| allowed_urls_preserve_signed_query_and_bytes | T02；AC03 | 通过，合法域/子域/端口、query、分块字节和实际日志。 |
| allowed_redirects_use_real_requests_resolution | T03；AC04 | 通过，301/302/303/307/308、相对/跨域/多跳。 |
| disallowed_redirect_never_reaches_transport_or_truncates_output | T04；AC05 | 通过，违规目标零发送，已存在文件不截断。 |
| failure_paths_are_bounded_safe_and_release_resources | T05；AC06 | 通过，循环/非 200/超时/连接/最终及跳转流中断/畸形 Location，资源释放。 |
| download_isolates_api_credentials_and_preserves_environment | T06；AC07 | 通过，API 头/auth/cookie 不复制，代理/CA 保持，日志/异常脱敏。 |
| production_factories_use_custom_allowlist_and_existing_resolver | T07；AC01 | 通过，两个真实工厂的自定义名单及原 resolver。 |
| formal_polling_rejects_initial_and_redirect_targets | T08；AC08 | 通过，真实下载器、最终 parsing/mineru_failed、无成功 Artifact。 |
| formal_callback_checks_before_enqueue_and_again_in_worker | T09；AC08/AC09 | 通过，非法初始不入队、合法先入队再拒绝越界跳转。 |
| legacy_saved_result_recovery_uses_real_downloader | T10；AC09 | 通过，真实下载器、legacy 错误码、无成功产物。 |

上述为 10 个测试方法及各自 subTest，不将子例数虚报为方法数。网络端使用假的 HTTPAdapter.send，真实客户端及 Session 重定向逻辑执行；NETRC 指向临时目录不存在的文件，未读真实开发机凭据。

## 首轮历史记录：既有 5 个方法中 1 通过，4 个基线既有错误

执行命令：

    .venv/bin/python -m unittest \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_invalid_callback_checksum_leaves_no_callback_message \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_queues_before_worker_completes_parse \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_dedupes_duplicate_delivery_before_worker \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_ignores_queued_callback_after_cancel \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_convert_parsed_result_fails_when_result_zip_download_fails

最后一个 legacy 下载失败方法通过。前四个分别在原测试文件 9561、9307、9395、9454 行读取 create_response.json()["job_id"] 时报 KeyError，尚未到达 callback/download 目标验收。新增 fixture 曾观察到同类 public 模式 readiness 503；旧方法的基线结论以以下实测为准，不推断已经覆盖其回调语义。

主代理使用原始 HEAD 的独立 detached worktree，共用同一 .venv，只对这四个计划内失败方法做对照；四个在相同行号发生相同 KeyError（4 tests，0.493 秒，exit 1）。证据：[基线原始输出](validation/baseline-targeted-tests.log)。临时 worktree 正常移除，主工作区未回退。

这确认首轮失败并非 B03 引入；当时 AC09 的 checksum/去重/取消回归未到目标断言。随后用户单独批准回调夹具专项，仅改四例为 internal 并前移创建成功断言，原 55 条断言保留，四例一次运行全部通过（1.021 秒，exit 0）。现将[该专项证据](../11-06-callback-test-fixture-readiness/validation/targeted-tests.result.json)回填，关闭原缺口；历史失败及原始 HEAD 对照日志不删除。本轮不再测试。

## 独立复核与静态检查

Trellis check 代理审查全部候选源代码和未跟踪新文件，未发现待修复的确认产品缺陷；仅进行了上述 3 行测试证据补强。复核覆盖策略 owner、真实发送顺序、凭据、响应释放、错误链、工厂及三个入口的状态/产物行为。

git diff --check、两个新 Python 文件的空白检查、构造点及旧 import 静态搜索通过。没有执行独立 lint/typecheck，不能把静态阅读表述为这些工具通过；没有运行构建或发布脚本。主代理最后核对文件范围和任务记录。

## 状态与边界

实现及获批本地定向验收全部完成：AC01–AC10 逐项核对见 [证据对账](acceptance-reconciliation.md)。复用 10 + 1 + 4 个不同方法的已有成功结果；不是本轮新跑的统一测试。任务标记 completed，未提交、推送或归档。真实环境与换代并发运行边界仍保留。

未引入 CI、依赖、schema 或生产配置变化；未执行全量测试、真实供应商调用、部署、提交或推送；不运行会产生 bookkeeping 提交的归档/会话记录命令。

真实 CDN、生产依赖版本、代理/DNS 以及真实 Word 客户端未验证。流读取中断可能留下部分临时文件，沿用原 Artifact 生命周期且不登记成功；本任务没有扩展为 DNS 防护、原子下载或全局日志脱敏。
