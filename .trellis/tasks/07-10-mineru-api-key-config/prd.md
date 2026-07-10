# 支持修改 MinerU 密钥

## Goal

在配置中心提供 MinerU API 密钥轮换入口，使管理员无需修改部署环境文件或重启服务，即可让后续 MinerU 请求使用新密钥。

## Background

- MinerU 密钥存在数月后过期并需要轮换的业务场景。
- `Settings.mineru_api_token` 当前只从启动配置 `MINERU_API_TOKEN` 读取（`app/core/config.py:99`）。
- 两条 MinerU 任务链路每次上传、查询或下载前都会新建 `MinerUClient`，但客户端工厂固定读取进程启动时的 `Settings`（`app/domains/jobs/stage.py:792`、`app/domains/document_jobs/execution.py:2469`）。
- 健康检查、PDF 上传入口、MinerU 结果恢复和集成控制也分别读取启动配置，当前存在多个密钥状态判断点（`app/services/health_service.py:149`、`app/domains/jobs/ingest_router.py:301`、`app/domains/jobs/ops_router.py:149`、`app/domains/ops/integration_control.py:208`）。
- 项目已有 AI Provider 运行时配置先例：应用私有 JSON 文件通过原子替换写入并尽力限制为 `0600`，调用方按请求读取有效配置，API 只返回安全摘要（`app/domains/translation/provider_config.py:52`、`app/domains/translation/provider_config_router.py:22`、`app/domains/translation/provider.py:41`）。
- 生产基线为单机 Docker Compose，API 与 Worker 共享 `md2word-var:/app/var`，可共同读取同一个运行时配置文件（`docker/prod/docker-compose.yml:29`、`docker/prod/docker-compose.yml:49`、`docs/deploy/p0-docker-deployment.md:24`）。

## Requirements

- **R1 独立入口与权限**：配置中心新增独立“MinerU 配置”页面、路由和导航入口，不改变现有“AI 配置”职责；读取和更新仅允许管理员执行。
- **R2 安全状态响应**：读取接口和页面只展示 `configured/missing`、配置来源、更新时间和更新人，不返回或渲染已保存密钥的任何字符、脱敏片段、长度或请求体。
- **R3 非空覆盖**：更新接口只接受去除首尾空白后的非空密钥，只允许覆盖当前值，不提供清空能力；未提供、空字符串或纯空白输入不得改变当前配置。
- **R4 本地安全持久化**：只保存当前密钥和必要轮换元数据，通过临时文件原子替换写入应用私有运行时文件，并在支持的平台上将权限限制为 `0600`；不保留历史密钥或回滚副本。
- **R5 配置优先级**：运行时配置文件不存在时使用 `MINERU_API_TOKEN`；管理员首次保存后运行时配置始终优先。运行时文件损坏、格式非法或不可读时必须明确报错并将 MinerU 就绪状态标为异常，不得回退环境变量。
- **R6 立即生效与单一来源**：API、长期运行的 Stage Worker、Celery Worker、健康检查、PDF 上传门禁、结果恢复和集成控制都从同一有效配置服务读取。保存成功后，随后新发起的 MinerU 上传、查询、下载和恢复请求无需重启即使用新密钥；已发出的 HTTP 请求不切换密钥。
- **R7 无外部校验**：保存流程只做本地输入校验和持久化，不调用 MinerU 或其他外部接口，外部服务或网络异常不得阻断密钥保存。
- **R8 审计**：成功更新后记录更新人、事件时间、操作类型、目标 `mineru_config/default`、更新后“已配置”状态和 `trace_id`；审计中不得包含密钥、脱敏片段、长度或请求体。
- **R9 审计失败边界**：密钥文件写入成功但审计仓储写入失败时，保留新密钥、返回明确错误且不自动回滚；管理员可刷新配置状态确认新值的更新时间和更新人。
- **R10 诊断一致性**：`mineru_api_token_missing` 和新增的运行时配置损坏诊断应指向“MinerU 配置”页面；其他 MinerU 配置缺失仍指向实际可处理入口。

## Acceptance Criteria

- [x] **AC1 / R1-R2**：管理员能从配置中心和侧边导航进入独立页面；非管理员读取或更新 API 均被拒绝；现有 AI 配置页面行为不变。
- [x] **AC2 / R2-R3**：GET/PUT 响应与已保存状态页面均不包含任何密钥字符，只包含配置状态、来源、更新时间和更新人；成功保存后输入框被清空。
- [x] **AC3 / R3**：缺少密钥、空字符串和纯空白更新均返回明确校验错误，当前有效配置和文件内容保持不变；页面与接口都没有清空操作。
- [x] **AC4 / R4-R5**：无运行时文件时读取 `MINERU_API_TOKEN`；合法运行时文件覆盖环境变量；配置文件仅含当前密钥和轮换元数据，原子写入且在支持的平台上权限为 `0600`。
- [x] **AC5 / R5-R6**：运行时文件损坏、格式非法或不可读时，配置 API、健康检查和业务门禁暴露明确错误，且不会使用环境变量兜底。
- [x] **AC6 / R6**：保存新密钥后无需重启 API、Stage Worker 或 Celery Worker，两条 MinerU 任务链路随后创建的客户端均使用新密钥；已创建客户端保持原密钥。
- [x] **AC7 / R7**：成功或失败的本地保存路径都不会发起 MinerU 网络请求。
- [x] **AC8 / R8**：每次完整成功的更新产生一条审计事件，事件可按更新人、时间、操作类型、目标和 `trace_id` 追踪，且详情仅包含安全的“已配置”状态。
- [x] **AC9 / R9**：模拟审计写入失败时，更新接口返回“新密钥已保存但审计失败”的明确错误；刷新后能看到新的轮换元数据，新密钥仍为有效配置。
- [x] **AC10 / R10**：配置中心的 MinerU 密钥缺失或配置损坏诊断链接到独立页面，相关健康状态、门禁状态和实际客户端使用同一有效配置结论。

## Out Of Scope

- MinerU callback URL、UID、模型版本、语言、公式、表格或其他配置项的页面编辑。
- 保存时调用 MinerU 验证密钥、发送测试任务或自动探测有效期。
- 加密存储、外部 Secret Manager、密钥历史、一键回滚或主动清空密钥。
- 多主机或多集群配置同步；当前范围限定为共享 `md2word-var` volume 的单机部署基线。
- 用删除密钥表达停用 MinerU；未来如需停用，应另行设计集成开关。
