# 修复设计（用户已确认）

## 入口与 owner

源码锚点见 [current-state.md](research/current-state.md)。目标依赖：

    Settings.allowed_mineru_result_hosts
        → 两个业务工厂 → MinerUClient
    callback guard / legacy 校验 / MinerUClient
        → app/clients/mineru_result_url.py
    下载专用 Session.send
        → 同一校验函数 → Requests 原始发送逻辑

将 validate_mineru_result_url(full_zip_url, allowed_hosts) 移到 app/clients/mineru_result_url.py，保留 None / ValueError 接口。移除仅承载该函数的旧文件，更新全部仓库内引用，不保留空壳转发；clients 不反向依赖 domains。

两个真实构造点增加必传关键字 result_host_allowlist，客户端保存 tuple。空名单只禁止结果下载，不改变上传/查询本身门禁。客户端不读取全局 Settings，不自行补默认 host。

## 策略

复用 HTTPS、hostname 大小写归一、精确 host 或点分隔子域规则；拒绝相似字符串后缀。名单仍由 Settings 解析，不引入第二种配置语法，不增加 DNS 查询、私网判定、端口白名单、尾点/IDNA 宽松兼容。

明确拒绝 username/password：供应商结果 URL 中的 userinfo 会触发 Requests 认证处理，属于本边界内有具体行为依据的收紧。签名 query 可保留；合法显式端口保持，无效端口/不被 Requests 支持的 URL 在真实传输前失败。解析异常用固定中文 ValueError，避免回显原始 URL。

下载入口先对初始字符串调用共享策略，与 callback 预检一致；每个 PreparedRequest 在发送前再检查。两层分别面对供应商字段与规范化/服务器跳转后的实际目的地，不能用入口预检替代传输检查。

## 重定向取舍

| 方案 | 收益 | 代价/结论 |
|---|---|---|
| 一律 allow_redirects=False | 最少代码，边界清楚 | 官方没有无跳转承诺，会改变现有兼容行为；不推荐。 |
| 手写 get/urljoin 循环 | 显式控制每跳 | 需自己维护相对地址、cookie、上限、响应释放；不重复库逻辑。 |
| 专用 Session.send 检查 | 覆盖首跳及每个真实跳转，复用库协议逻辑 | 新增一个有安全责任的私有类型；需真实 Requests 流程的定向测试。推荐。 |
| 下载后检查 response.url/history | 容易添加 | 请求已发生，无法满足违规目标零请求；不可接受。 |

私有类型放在 mineru_client.py，只保存名单并在 super().send 前校验。使用公开 send，不改 HTTPAdapter、resolve_redirects 或连接池私有方法，不复制上游源码。调用仍从 session.get 开始，以保留代理/CA 环境合并；跳转上限保持 Requests 默认 30，不新建配置/重试机制。

## 生命周期、错误与凭据

1. 初始校验，不创建或截断输出文件。
2. 新建下载专用 Session 上下文。不得复用 self.session 或复制其 headers/auth/cookies：它含 API Bearer 与 UID token。
3. session.get 保持 stream=True、timeout=300，使用标准 TLS 验证和代理/CA 环境设置；每次 send 先校验。
4. Requests 处理合法跳转；只接受最终 HTTP 200。之后再创建父目录和打开输出，保留 1 MiB 分块。
5. Session 由上下文关闭；通过公开 response hook 将已取得响应纳入 ExitStack，在成功和跳转读取失败时统一释放。后者可能发生在 get 返回前且异常未携带 response，因此只关闭最终响应不足以满足合同。Requests 异常携带已取得 response 时同样释放，不以重试掩盖失败。
6. URL 策略错误和 RequestException（非法 URL、超时、连接、TooManyRedirects、流读取）转为固定安全 MinerUError，抑制原始异常链。非 200 可保留状态码；不 catch 所有 Exception，本地 OSError 保持分类。
7. 应用主动记录的成功日志只记录下载完成、输出路径和必要的 host；不记录完整 URL、Location、query、userinfo、上游异常 repr。

本项脱敏验收针对应用自身的下载日志、错误和异常链；不证明依赖库 DEBUG、代理或外部系统日志已全面脱敏，不新增全局日志配置。

凭据隔离保证不复制 MinerU API 会话。标准 trust_env/netrc 保持，不能宣称禁用了所有环境凭据；本机 Requests 2.34.2，旧版风险/生产未知见 upstream.md。不得擅自关闭 trust_env 影响代理/CA。

非法初始/越界跳转/非 200 不得创建或覆盖目标文件。流开始后的失败可能留下部分字节，沿用现有临时目录/Artifact 生命周期，不引入通用原子下载或删除未知既有文件；部分内容不能登记为成功 ZIP。

## 状态兼容

- callback guard 继续 ValueError → HTTP 400；checksum、归一化、入队去重不变。
- 正式 Worker MinerUError 仍是 parsing/mineru_failed；用户消息走 _worker_failure_message。
- legacy 保持 parsed_result_download_failed。它记录 str(exc)，故 downloader 安全错误与异常链抑制必须同时生效。
- 保留 _download_and_register_mineru_result 下载前后 generation/cancel 检查及条件登记，不移动事务。
- 已入队/持久化 URL 也必须重新校验。callback 200 表示接受；后续跳转越界可以最终失败。

## 预计改动文件

| 文件 | 允许修改 |
|---|---|
| app/clients/mineru_result_url.py（新增） | 单一 URL 策略。 |
| app/domains/jobs/mineru_callback.py | 迁移函数后删除旧空模块。 |
| app/clients/mineru_client.py | 必传名单、发送前检查、下载资源/错误/日志。 |
| app/api/mineru_callback_guards.py | 策略 import；保留 HTTP/checksum 合同。 |
| app/domains/jobs/stage.py | 策略 import 和工厂注入。 |
| app/domains/document_jobs/execution.py | 仅工厂注入，不拆分执行器。 |
| tests/test_mineru_download_boundary.py（新增） | 边界、真实客户端/假传输、三入口覆盖。 |
| docs/api/mineru-callbacks.md | 入队预检与下载逐跳校验合同。 |
| .trellis/spec/backend/error-handling.md | 补充直接相关 owner/错误/脱敏合同。 |

通常不改既有大型测试文件。复用 runtime fixture 时不导入其 TestCase 类，避免新模块被 unittest 收集时连带执行全套。发现其他真实调用方时先补证据/计划，不编造兼容层。

## 回退与停止条件

无 schema/数据迁移，未来仅撤销本任务代码；不得以放开名单、忽略错误或自动回旧下载器作为回退。真实 CDN 若需要新增 host，记录目标并单独确认配置。

若公开 send 无法保持现有行为，或必须改状态机、认证配置、依赖版本，先更新计划再确认。测试失败先区分本次缺陷与历史夹具，不能扩展为全量回归/历史修复。
