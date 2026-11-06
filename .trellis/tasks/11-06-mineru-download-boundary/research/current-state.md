# B03 源码事实与测试缺口

基线 main@79f20cef9ca0bb1a59af635e2408e130c4935e2d；2026-11-06 静态核对，未运行应用测试或真实下载。

| 事实 | 证据 | 影响 |
|---|---|---|
| Settings 已有名单及 tuple 属性 | app/core/config.py:138；app/core/config.py:339 | 复用配置，无新 env。 |
| 纯函数检查 HTTPS、host、精确/子域关系 | app/domains/jobs/mineru_callback.py:9 | 移 owner，clients 不导入 domains。 |
| callback 将 ValueError 转 HTTP 400 | app/api/mineru_callback_guards.py:27 | 保留预检及异常层级。 |
| checksum 独立验证 UID、seed、content | app/api/mineru_callback_guards.py:81；app/api/mineru_callback_guards.py:102 | 不改验签。 |
| 下载 requests.get，未传 allow_redirects、未调用策略 | app/clients/mineru_client.py:104 | 需要首跳与逐跳发送边界。 |
| API Session 含 Authorization/token，下载使用模块 get | app/clients/mineru_client.py:30；app/clients/mineru_client.py:104 | 不能复用带 API 凭据的 Session。 |
| 正式轮询直接消费 full_zip_url | app/domains/document_jobs/execution.py:321；app/domains/document_jobs/execution.py:729 | API 回应也要受目的地策略约束。 |
| callback Worker 从消息取 URL，进入共同下载函数 | app/domains/document_jobs/execution.py:519；app/domains/document_jobs/execution.py:610 | 入队检查不能替代实际下载检查。 |
| 下载前后有 retry/cancel 检查，之后条件登记结果 | app/domains/document_jobs/execution.py:729 | 保持状态与 Artifact owner。 |
| legacy 保留 parsed 结果恢复下载 | app/domains/jobs/stage.py:836；app/domains/jobs/stage.py:842 | 纳入共同边界，不删除路径。 |
| 两个真实 MinerUClient 构造点 | app/domains/jobs/stage.py:795；app/domains/document_jobs/execution.py:4130 | 两处注入名单；legacy _create_mineru_client 不是第三个构造点。 |
| 正式错误分类/消息已有 owner | app/domains/document_jobs/execution.py:3966；app/domains/document_jobs/execution.py:3991 | MinerUError 仍映射 mineru_failed。 |
| legacy 下载异常直接取 str(exc) | app/domains/jobs/stage.py:575 | 边界错误必须脱敏，且抑制原始异常链。 |
| 当前失败消息和成功日志带完整 URL | app/clients/mineru_client.py:113；app/clients/mineru_client.py:118 | 签名 query 不应继续进入新增下载日志/错误；不据此断言生产已泄漏。 |
| requirements 允许 requests>=2.32,<3，本机 2.34.2 | requirements.txt:13；.venv/lib/python3.11/site-packages/requests/__version__.py:8 | 不升级依赖；本机与生产证据分开。 |

## 现有测试局限

tests/test_fastapi_jobs_backend.py:115 的 FakeMinerUClient 自己实现 download_result_zip；runtime 构建在 tests/test_fastapi_jobs_backend.py:573、tests/test_fastapi_jobs_backend.py:708 注入它。因此既有成功/失败任务测试不能证明真实 Requests 目的地址受控。

新增测试保持真实 MinerUClient、Session.request/send/resolve_redirects，只替换 HTTPAdapter.send 网络发送端，记录到达传输的 PreparedRequest。合法首跳返回真实 requests.Response 及可读/可关闭的假 raw，驱动库跳转；不 mock 新增安全检查，不访问外网。

以下已有方法由源码/AST 定位，尚未执行：

- tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_invalid_callback_checksum_leaves_no_callback_message
- tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_queues_before_worker_completes_parse
- tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_dedupes_duplicate_delivery_before_worker
- tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_ignores_queued_callback_after_cancel
- tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_convert_parsed_result_fails_when_result_zip_download_fails

## 证据边界

确认：当前下载默认自动重定向，正式轮询未调用共享策略。推论：首跳给出越界 Location 时，现有 requests.get 会跟随；这来自具体库行为，不是生产攻击复现。

未知：真实 CDN 跳转链、生产 Requests 版本、环境 netrc/代理及 DNS 行为。没有读取真实本机凭据，没有提交供应商任务或下载结果。
