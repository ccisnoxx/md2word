# B03 MinerU 下载边界一致性

## 状态与授权

- 独立任务，优先级 P1，status=completed，parent=null。
- 来源：审查整改路线图 B03 / A05；关联上一规划任务；2026-11-06 按用户本轮授权同步其 B03 进度。
- 基线：main@79f20cef9ca0bb1a59af635e2408e130c4935e2d，2026-11-06 本地工作区。
- 用户于 2026-11-06 明确确认最新方案：允许名单内跳转、发送前逐次校验、拒绝 userinfo；已授权实施与计划内定向验收。
- 仅修改本计划指定的业务代码、定向测试和相关文档/Spec；不引入 CI、不跑全量测试、不提交、不推送、不部署。

## 问题与目标

回调入口和 legacy 部分阶段已有 HTTPS/host 检查，正式主动轮询调用的 MinerUClient.download_result_zip 没有此检查。下载默认跟随重定向；即便初始地址合格，后续目标也可能越过允许名单。具体触发条件是供应商结果字段、已入队 payload 或合法结果地址的 Location 不符合策略；不据此声称发生过攻击或生产泄漏。

目标：正式轮询、正式回调 Worker、legacy 结果恢复及直接客户端调用，在首次和后续结果下载请求实际发出前执行同一策略。被拒绝目标收到零次请求，不登记成功产物，不推进 parsed/成功状态；保留允许名单内的合法跳转。

## 已确认实施范围

1. 将现有结果 URL 校验函数移至客户端层，共享给 callback guard、legacy 阶段和真实下载器；迁移全部已知 import，无无依据兼容 wrapper。
2. MinerUClient 增加必传结果 host 名单参数，两个生产工厂从 Settings.allowed_mineru_result_hosts 注入；不新增 env、全局 Settings 读取或备用名单。
3. 下载使用与 API 凭据会话分离的短生命周期 Session，在公开 Session.send 边界检查每次 PreparedRequest 的目的地，复用 Requests 重定向、相对 Location、cookie 和跳转上限。
4. 保留 HTTPS、host 精确或点分隔子域匹配；拒绝空名单、缺 host、非 HTTPS、名单外 host；补充拒绝会被 Requests 转成认证数据的 username/password URL。
5. 下载边界提供安全 MinerUError，不输出完整 URL、query、fragment、userinfo 或上游原始异常文本；资源释放覆盖成功和失败。
6. 增加本边界离线测试，按方法运行少量既有回调状态回归；更新直接相关文档/Spec。

## 非目标

不改状态机、CAS、retry_count、checksum、队列、数据库、DocumentIR、ZIP 有界解压、Renderer；不删除 legacy 运行时。上传 URL、API_BASE、其他 Provider 出站策略、DNS/IP 防护、下载总字节/总时限、依赖锁与升级均不并入。不关闭 TLS 验证或自动放宽名单。

## 决策

推荐名单内允许跳转，发送前逐次检查。不采用一律禁跳转、手写重定向循环或下载后才检查 response.url。私有 Session 子类只承担目的地址约束，不建立通用 HTTP 框架。

callback 仍可在入队前返回 HTTP 400；入队成功不等于下载成功。合法签名 query 保留在请求中，日志/错误中不出现。维持合法显式端口语义，不新增仅 443 限制。详细取舍见 design.md。

## 本轮规划验收

- [x] 独立任务、三件套、源码/上游依据和上下文具备可审阅内容。
- [x] 明确所有真实入口、推荐方案、兼容变化、修改文件与失败语义。
- [x] AC01–AC10 与最小检查命令明确，不引入 CI/全量测试。
- [x] 用户在最终规划摘要之后明确确认实施（2026-11-06）。

## 实施验收（要求与结果）

结果见 [证据对账](acceptance-reconciliation.md)：复用新增边界 10 例、既有 legacy 1 例及独立夹具任务修复后通过的回调 4 例，AC01–AC10 均满足获批本地定向验收范围。原始失败留作历史证据，本轮不再测试。

| 编号 | 可观察结果 |
|---|---|
| AC01 | 三类调用共用策略 owner；两个工厂注入 Settings 名单；空名单不能下载。 |
| AC02 | 非 HTTPS、无 host、名单外 host、后缀伪装、userinfo、畸形 URL 在首个请求前拒绝；传输调用为 0，既有输出未截断。 |
| AC03 | 根域、合法子域、大小写 host、合法端口、签名 query 可下载；最终 200 分块字节完整写入，返回指定 Path。 |
| AC04 | 301/302/303/307/308 的合法同域、名单内跨域、相对 Location 正常；每个真实发送目标都合格。 |
| AC05 | 单跳或多跳中的 HTTP、名单外或 userinfo 目标收到 0 请求；先前合法请求可发生，无成功产物。 |
| AC06 | 循环在 Requests 既有上限失败；缺 Location 的 3xx、非 200、超时/连接/流读取失败均不算成功，Session/已持有响应释放。 |
| AC07 | 下载不复制 API Authorization、token、cookie；保留标准 TLS/代理/CA 配置路径；签名不进入应用主动记录的下载日志、异常或异常链。 |
| AC08 | 正式轮询和回调 Worker 经真实下载器配假传输均拒绝违规目标；parsing/mineru_failed，无 mineru_raw_result/后续产物。 |
| AC09 | legacy 保持 parsed_result_download_failed；回调非法初始 URL 为 400 且不入队；checksum、去重、取消忽略保持。 |
| AC10 | 仅执行 implement.md 定向检查；相关历史失败单列；不跑整个大型 backend 模块或发布聚合脚本。 |

## 未验证边界

当前已有离线定向运行证据及原始 HEAD 失败对照；四个旧回调用例现已修复并通过。换代/CAS 仅有相关逻辑未改的静态保留依据，未新增并发运行验收。真实 CDN 跳转链、生产依赖、代理/DNS 与并发未验证。host 名单是管理员信任边界，不等同完整 SSRF/DNS rebinding 防御；离线假传输不能替代真实部署兼容证据。
