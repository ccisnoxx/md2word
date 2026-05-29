---
doc_type: brainstorm
slug: backend-productization-risk-check
created: 2026-05-28
status: active
summary: 面向电子元器件 PDF 转 Word 后端产品化的经验风险校准，重点检查接口、数据模型、权限、异步任务、配置、部署、日志、测试和可观测性盲点。
tags: [backend, fastapi, productization, risk-check, architecture]
---

# 后端产品化风险查漏

> 创意空间 | 2026-05-28 | 下一步：可进入 roadmap / design 细化

## 出发点

用户希望把当前 FastAPI 雏形项目发展为公司内部后端服务：

- 用户上传电子元器件 PDF，系统通过 MinerU 解析。
- 中文资料直接按所选模板 Profile 保持版式生成 Word。
- 英文资料可选择 AI 英译中，并在保证排版前提下生成 Word。
- 后续可能扩展中译英、中译俄等翻译方向。
- 前后端分离，后端先行。
- 不做公司 / 租户隔离，不同公司差异通过 `template_id` 选择不同模板 Profile。
- `template_id` 代表 `docx + layout + render_policy`，不包含术语规则和翻译配置。
- 术语规则采用草稿编辑 + 手动发布版本，任务只使用已发布版本。
- 任务可靠性目标是单实例可恢复级：不用 Redis / Celery，但持久化 stage message，重启后 replay `pending/running`，重复执行不破坏结果。
- MySQL 管所有业务 metadata：jobs、events、stage messages、templates、term rule versions；PDF / DOCX / zip 等大文件先放本地文件系统。

## 总体判断

### 已确认的事实

当前方向已经超出普通 CRUD 后端。它的核心不是“上传文件然后下载文件”，而是一个可追溯的文档转换编排系统。

### 我的推断

经验不足的后端开发者最容易把复杂度看成“接口数量”和“表数量”，但这个项目真正难的是：

- 长任务状态推进是否可恢复。
- 模板、术语、翻译配置是否可追溯。
- 产物和中间结果是否能复现。
- 失败时能否定位是 MinerU、翻译、渲染、模板、术语还是文件系统问题。

### 我的建议

MVP 不要追求平台化功能齐全，但要尽早固定领域边界。尤其是 `Job`、`StageMessage`、`Artifact`、`TemplateProfile`、`TermRuleSetVersion`、`TranslationProfile` 这些对象，不要散落在 router、文件路径和临时配置里。

## 逐项查漏

## 1. 接口

### 最可能高估

- 高估了“先把接口写出来，后面再改”的成本可控性。前端一旦接入，接口字段、状态枚举、错误码和下载 alias 都会变成事实合同。
- 高估了 `POST /jobs/pdf` 这类入口的简单程度。它背后实际涉及上传限制、幂等、异步任务、MinerU 回调、产物登记和失败恢复。

### 最可能低估

- 低估了状态枚举的兼容成本，例如 `uploaded`、`parsing`、`parsed`、`converting`、`completed`、`failed`、`canceled` 的语义必须稳定。
- 低估了错误码设计。用户需要知道失败发生在上传校验、MinerU 解析、远端结果下载、翻译、模板渲染、Word 生成还是 artifact 写入。
- 低估了下载接口的长期合同。`result`、`source-pdf`、`parsed-result-package`、`translation-request` 这些 alias 一旦暴露就不能随意改。
- 低估了接口的幂等需求。用户重复提交、浏览器重试、callback 重复到达都不应该制造重复产物或破坏 job 状态。

### 盲点

- 是否需要 `Idempotency-Key` 或源文件 hash 去重。
- list 接口是否需要分页、状态筛选、时间筛选、关键词搜索。
- callback 接口如何鉴权、防伪造、防重放。
- 大文件上传大小限制、超时、文件类型校验和错误提示。
- 接口是否需要 OpenAPI schema 固化并纳入测试。

### 建议

MVP 就固定一套窄接口合同：创建任务、查任务、查事件、查文件、下载产物、重试任务。模板和术语管理 API 可以先做最小管理面，但字段要围绕版本和发布状态设计。

## 2. 数据模型

### 最可能高估

- 高估了“有 MySQL 表就等于模型清楚”。表只是持久化形式，关键是对象边界和不可变规则。
- 高估了直接 CRUD 的适用性。术语规则、模板 Profile、翻译配置都不是普通可随便覆盖的配置。

### 最可能低估

- 低估了版本不可变的重要性。已发布术语版本、模板版本、翻译配置版本一旦被 job 引用，就不应原地修改。
- 低估了任务快照需求。每个 job 至少应记录 `template_id/version`、`term_rule_set_id/version`、`translation_profile_id/version`、MinerU 标识、artifact ids 和关键配置 hash。
- 低估了状态机约束。job 状态不能只靠随意 update 字段，必须定义允许的状态迁移。
- 低估了 migration 成本。后端早期字段随便加，后面前端和历史数据都会放大迁移风险。

### 盲点

- `TemplateProfile` 和 `TemplateVersion` 是否分表。
- `TermRuleSet` 草稿和发布版本是否分开存。
- 发布版本是否存完整快照，还是只存 diff。
- `Artifact` 表如何表达本地文件路径、逻辑路径、file type、alias、media type、大小、hash。
- `StageMessage` 是否有 `message_id`、`job_id`、`stage`、`status`、`attempt_count`、`locked_at`、`last_error`。
- 翻译 segment 是否现在建模，还是只保存 request/result JSON。

### 建议

MySQL 管业务事实，本地文件系统只管大文件。所有可影响生成结果的资源都要版本化，job 只引用发布版本，并记录足够复现的快照字段。

## 3. 权限

### 最可能高估

- 高估了“公司内部系统可以先不管权限”。即使不做租户隔离，也至少有普通任务使用、模板维护、术语发布、任务重试清理这些不同权限。
- 高估了后续补权限的容易程度。权限会影响 router、service、审计日志、前端页面和数据查询。

### 最可能低估

- 低估了模板和术语的破坏力。错误模板或错误术语发布后，会影响后续大量文档。
- 低估了 artifact 下载的敏感性。上传的 PDF、生成的 Word、MinerU 中间包都可能包含客户资料。
- 低估了 admin 操作审计需求。retry、cancel、cleanup、publish、rollback 都应该记录谁在何时因为什么执行。

### 盲点

- 是否需要最小角色：`viewer`、`operator`、`admin`。
- 谁可以上传模板，谁可以发布模板版本。
- 谁可以编辑术语草稿，谁可以发布术语版本。
- 谁可以下载历史任务产物。
- API token、session、SSO 或企业内网鉴权的选择。

### 建议

MVP 可以先只做简单管理员 token 或内部账号，但 service 层要预留 `actor_id` / `actor_role` / `operation_reason`，审计日志不要等前端上线后再补。

## 4. 异步任务

### 最可能高估

- 高估了 `BackgroundTasks` 的可靠性。它适合作为触发器，不适合作为任务系统真源。
- 高估了“失败后手动重试”的可接受性。转换链路长，失败类型多，没有 stage 级事件会很难定位。

### 最可能低估

- 低估了 replay 的边界。重启后 replay `pending/running` 时，必须保证重复执行不会覆盖已完成 artifact 或把 completed job 打回中间态。
- 低估了取消任务的语义。如果正在调用 MinerU 或 LLM，取消只能做到“停止后续推进”，未必能中断外部调用。
- 低估了并发和文件写入问题。两个 stage 同时处理同一 job，可能重复下载、重复生成或互相覆盖。
- 低估了阶段拆分。`parse_pdf`、`download_mineru_result`、`convert_docx`、`translate`、`register_artifact` 应有清晰阶段边界。

### 盲点

- stage message 的状态机：`pending`、`running`、`succeeded`、`failed`。
- `failed` 是否自动 retry，还是只允许人工 retry。
- retry 是否创建新 message，还是复用旧 message。
- 每个 stage 的幂等 key 是什么。
- job completed 后收到迟到 callback 怎么处理。

### 建议

坚持单实例可恢复级即可，不要急着上 Redis / Celery。关键是 stage message 持久化、状态迁移受控、artifact 注册幂等、事件可追溯。

## 5. 配置管理

### 最可能高估

- 高估了 `.env` 和几个 YAML 文件能长期承载业务配置。它们适合运行环境，不适合在线版本化业务资产。
- 高估了“模板只是 docx 文件”的简单性。模板 Profile 实际包含 docx、layout、render_policy 和版本状态。

### 最可能低估

- 低估了配置分层：运行时配置、业务资源配置、任务快照配置应该分开。
- 低估了 prompt 和模型参数的版本影响。翻译结果受模型、prompt、temperature、术语规则影响，不能只记录目标语言。
- 低估了默认值治理。默认模板、默认术语规则、默认翻译配置都应该有明确来源和变更记录。

### 盲点

- `OPENAI_*` 属于运行时 secret，不应进入数据库明文。
- `TranslationProfile` 应记录模型名、base_url 引用、prompt version、source/target language、分批策略。
- 模板上传后是否需要校验 docx 可读、必要 style 是否存在。
- render policy 变更是否需要发布版本。

### 建议

把配置分成三层：`RuntimeSettings` 管环境和 secret；`ResourceProfile` 管模板、术语、翻译等可版本化业务资源；`JobSnapshot` 记录任务实际使用的资源版本。

## 6. 部署

### 最可能高估

- 高估了“本地跑通”到“公司内可用”的距离。生产运行会遇到路径权限、MySQL migration、回调公网地址、文件备份、磁盘清理和进程管理。
- 高估了单实例部署的简单性。单实例也需要明确启动顺序、健康检查、数据目录和异常恢复。

### 最可能低估

- 低估了 MinerU callback 对网络和地址的要求。服务如果在内网，MinerU 如何回调需要提前设计。
- 低估了本地文件存储的运维成本。PDF、zip、DOCX 会占磁盘，需要 retention、清理策略和备份策略。
- 低估了数据库 migration 的纪律。Alembic migration 要和版本发布绑定。
- 低估了部署后重启 replay 的危险。启动时自动 replay 前应能报告待处理消息数量和失败消息数量。

### 盲点

- 是否使用 Docker / docker compose。
- MySQL 初始化和 Alembic migration 谁执行。
- 本地 artifact 根目录如何挂载和备份。
- 日志目录、数据目录和临时目录如何清理。
- callback URL 如何配置，以及不同环境如何区分。

### 建议

MVP 的部署目标应是“单实例生产化”，不是“开发机脚本”。至少要有 `.env.example`、migration 命令、数据目录约定、health check、runbook、备份和清理策略。

## 7. 日志

### 最可能高估

- 高估了普通文本日志的排障能力。长任务系统没有 `job_id`、`trace_id`、`stage`、`artifact_type`，日志很快不可用。
- 高估了异常堆栈本身的价值。业务事件比堆栈更能说明用户看到的问题。

### 最可能低估

- 低估了结构化日志的重要性。每个关键动作都应带 `job_id`、`trace_id`、`stage`、`status`、`mineru_batch_id`、`mineru_data_id`。
- 低估了日志和 job events 的分工。日志给开发和运维看，job events 给用户和前端看。
- 低估了敏感信息泄露风险。PDF 路径、客户文件名、API key、prompt 内容和全文文本不应无控制写日志。

### 盲点

- access log、business log、system log 是否区分。
- job event 是否入 MySQL 并可分页查询。
- 外部服务调用耗时和失败原因是否记录。
- 日志是否有保留周期和大小滚动。

### 建议

把 job events 当成产品能力，不只是日志副产物。每个 stage 开始、成功、失败、重试、取消、artifact 注册都要写事件；日志保留更细的技术上下文。

## 8. 测试

### 最可能高估

- 高估了 happy path 测试的覆盖价值。这个系统最容易出问题的是失败恢复、版本引用、文件边界和重复执行。
- 高估了 mock 测试能代表真实转换质量。DOCX 版式需要保留 characterization 或样例验收。

### 最可能低估

- 低估了状态机测试。非法状态迁移、重复 callback、重复 retry、completed 后 replay 都应覆盖。
- 低估了 repository 测试。MySQL repository、artifact storage、本地文件写入、事务边界都需要对象级测试。
- 低估了 schema 兼容测试。OpenAPI 变更、错误码、响应字段应该有快照或合同测试。
- 低估了真实样例的重要性。电子元器件 PDF 的表格、公式、型号、单位和页眉页脚需要典型样例。

### 盲点

- MinerU callback 成功但结果 zip 下载失败。
- LLM 翻译失败、超时、部分 segment 失败。
- 模板版本被禁用后，历史任务下载是否仍可用。
- 发布术语版本后，旧任务是否仍能复现。
- 磁盘满、文件缺失、文件 hash 不一致。

### 建议

测试分层：API 合同测试、service 状态机测试、repository 测试、stage replay 测试、conversion characterization、少量真实链路 smoke。先测不变量，再测接口数量。

## 9. 可观测性

### 最可能高估

- 高估了 `/health` 等于可观测性。health 只能说明服务能不能接请求，不能说明任务队列、stage、MinerU、LLM 和文件存储是否健康。
- 高估了“出问题看日志”的效率。没有指标和事件聚合时，问题只能靠人工翻文件。

### 最可能低估

- 低估了任务维度指标：每天多少任务、成功率、平均耗时、失败原因分布、各 stage 耗时。
- 低估了队列维度指标：pending/running/failed stage messages 数量、最老 pending 消息年龄。
- 低估了外部依赖健康：MinerU 提交成功率、callback 延迟、LLM 调用失败率和耗时。
- 低估了 artifact 存储健康：磁盘剩余空间、文件缺失、hash 校验失败、清理数量。

### 盲点

- readiness 是否返回 worker mode、stage dispatcher、message store、artifact storage。
- 是否有任务级 timeline 给前端展示。
- 是否需要 metrics endpoint，哪怕先只返回 JSON。
- 是否记录每个 stage 的开始时间、结束时间、耗时和 attempt。

### 建议

MVP 至少提供 readiness 诊断字段和任务事件 timeline。Prometheus 这类指标系统可以后置，但统计所需字段要在 MySQL metadata 里先保留。

## 当前倾向

当前倾向是先做“单实例生产化后端”，不是“完整平台”：

- MySQL 是业务 metadata 真源。
- 本地文件系统是 artifact 存储。
- 自研 stage message + replay 提供单实例可恢复。
- 模板、术语、翻译配置都按版本化资源设计。
- 前端后置，但 API 合同和资源模型不能等前端再定。

## 已敲定的点

- 不做租户隔离，不同公司差异走模板 Profile。
- `TemplateProfile` 不包含术语规则和翻译配置。
- 术语规则采用草稿编辑 + 手动发布版本。
- 任务只使用已发布术语版本，并记录实际版本。
- 翻译先全自动，后续预留人工校对。
- 任务执行目标是单实例可恢复，不引入 Redis / Celery。
- MySQL 管业务 metadata，大文件先存本地文件。

## 反直觉但值得考虑的方案

不要把第一版重点放在“更多接口”和“更像平台的基础设施”上。更值得优先做的是约束更强的资源和状态模型：少一些接口，多一些不可变版本、状态机、事件和快照。

这看起来慢，但能防止后续前端接入后出现最难修的几类问题：历史任务不可复现、模板和术语污染、失败不可定位、重复执行破坏产物。

## 遗留问题 & 下一步

- 是否现在就引入最小账号 / 角色，还是先用 admin token 过渡。
- `TemplateProfile` 版本结构需要细化到表设计和上传校验。
- `TermRuleSet` 草稿和发布版本的 schema 需要单独设计。
- `TranslationProfile` 是否在 MVP 建表，还是先记录 JSON 快照。
- stage 切分和状态迁移需要形成正式 design。
- MySQL repository 迁移需要设计 Alembic 初始化和兼容策略。
- 本地 artifact retention、备份和清理策略需要形成 runbook。
