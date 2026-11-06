# 实施顺序与定向验收（已确认）

## 启动条件

用户于 2026-11-06 在最终规划摘要之后明确确认实施；本轮启动任务并仅执行下列范围。仍不授权 CI、全量测试、提交、推送、部署或真实供应商调用。

## 实施顺序

| 步骤 | 交付与完成条件 |
|---|---|
| I1 统一策略 | 迁移函数、userinfo/安全解析错误、两个 import 和两个真实工厂；不改配置 schema。 |
| I2 真实下载边界 | 私有 Session.send 检查、API 凭据隔离、库跳转、释放与脱敏；不改变上传/查询/状态机/ZIP 校验。 |
| I3 定向证据 | 新建 tests/test_mineru_download_boundary.py；真实 client/Session 配假网络，覆盖下表。 |
| I4 文档与检查 | 更新直接相关文档/Spec，检查 diff，运行最小命令并记录实际结果；不提交/推送。 |

## 验收场景

只替换 HTTPAdapter.send 网络端，保留真实 client、Session.request/send/resolve_redirects；用真实 requests.Response 配可读可关闭假 raw 驱动跳转。不得 mock 本次新增检查，不访问外部网络。

| 组 | 输入/路径 | 必须观察到 | AC |
|---|---|---|---|
| T01 初始拒绝 | HTTP、空/相对 URL、缺 host、evil.test、mineru.net.evil.test、evilmineru.net、空名单、userinfo、无效端口/畸形 URL | adapter 0 次；无新输出，已有 sentinel 不变；安全错误 | AC01/AC02 |
| T02 合法下载 | 根域、a.mineru.net、大小写 host、合法显式端口、合成签名 query | 最终 200 字节逐字节一致、指定 Path、签名保留在请求 | AC03 |
| T03 合法跳转 | 301/302/303/307/308 参数化；相对路径、协议相对 Location、名单内跨域、多跳 | 真实发送序列全为合法 HTTPS，最终字节不变 | AC04 |
| T04 越界跳转 | 允许首跳/两跳后转 HTTP、evil.test、userinfo | 前面合法请求允许；违规目标 0 次；无成功输出，已有文件未截断 | AC05 |
| T05 有界失败/释放 | 循环、3xx 缺 Location、404、timeout/连接错误、流读取中断 | 默认跳转上限失败；安全异常；Session/已持有响应关闭；无成功登记 | AC06 |
| T06 凭据/日志 | API 会话合成 Bearer/UID/cookie；query/Location/网络异常含合成 secret | 下载不含 API 凭据；应用下载日志、对外异常和格式化 traceback 无 secret；不关闭 TLS/代理/CA 路径 | AC07 |
| T07 工厂接线 | 两个生产工厂配置不含默认域的自定义名单 | 真实客户端允许自定义域、拒绝默认域；resolver 与上传/查询配置保持 | AC01 |
| T08 正式轮询 | 仅 stub 提交/查询返回，保留真实下载；违规初始及合法首跳后越界 | parsing/mineru_failed；无 mineru_raw_result/后续 Artifact；违规目标 0 次 | AC08 |
| T09 正式回调 | 正确 checksum + 非法初始；正确 checksum + 合法入队后越界跳转 | 前者 400/不入队；后者先入队后 parsing/mineru_failed；无成功产物 | AC08/AC09 |
| T10 legacy 恢复 | 保存 URL 直接 parsed 恢复；违规初始/越界跳转 | parsed_result_download_failed，无成功登记；使用真实下载器 | AC09 |
| T11 原有合同 | 下列既有 checksum/入队/去重/取消/legacy 失败方法 | 行为保持；不能替代 T08–T10 边界证据 | AC09 |

采用 subTest 复用参数。T08–T10 复用既有本地 runtime 构建函数时，通过模块或函数引用，不能导入完整 TestCase。合法下载由 T02/T03 证明，合法 API 入队由 T11 证明；T11 可能沿既有本地 fixture 执行后续渲染，不扩展为真实 MinerU/Redis/MySQL 或真实 Word 客户端端到端验证。

## 已执行的定向验证集合（AC10）

    .venv/bin/python -m unittest tests.test_mineru_download_boundary
    .venv/bin/python -m unittest \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_invalid_callback_checksum_leaves_no_callback_message \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_queues_before_worker_completes_parse \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_mineru_callback_dedupes_duplicate_delivery_before_worker \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_ignores_queued_callback_after_cancel \
      tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_convert_parsed_result_fails_when_result_zip_download_fails

再核对实际修改路径的 git diff --check、最终 diff、git status。新增模块最终 10 例通过；既有 5 个方法最初为 1 通过、4 个基线错误，随后独立夹具任务仅修复并运行四例且全部通过。现有证据覆盖该集合，详见 acceptance-reconciliation.md；本次记录整理未重跑。失败先诊断；相关输入不变不重复检查。只修本任务 fixture，不修无关历史断言。

禁止 unittest discover、整个 tests.test_fastapi_jobs_backend、check_release.py、完整构建、全量测试及 CI。若需要变更额外合同或扩大范围，先更新方案。

## 复核重点

- 单一策略 owner，clients 不反向依赖 domains；不能仅检查最终 response。
- 不复制 API 凭据或通过异常链泄漏 URL；不关闭 TLS、代理/CA 既有路径。
- parsing attempt/CAS 原样保留，完整下载后才让原流程登记。
- 新增/实质修改 Python 注释、docstring、开发者消息用中文。

## 本轮规划校验

只做 task.py validate、JSON/JSONL、引用/行号/既有方法静态存在性、任务状态、文件范围与旧任务哈希检查。结果见 planning-validation.md，不代表业务修复或运行安全通过。
