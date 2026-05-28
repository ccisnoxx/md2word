---
doc_type: dev-guide
slug: backend-architecture-baseline-and-issues
component: backend-architecture
status: draft
summary: 正式整理当前 md2word 后端的现状架构基线、job 生命周期视图和待收口结构问题。
tags: [backend, architecture, baseline, jobs]
last_reviewed: 2026-05-28
---

# 后端现状架构基线与问题清单（初稿）

## 文档目的

这份文档用于给后续“功能完善、优化、架构收口”提供统一基线。

当前目标不是直接给出终态方案，而是先明确：

- 当前后端实际上是怎样分层和运行的
- `job` 主链路当前有哪些稳定事实
- 哪些结构问题应该优先收口

## 当前进展（截至 2026-05-28）

这份文档最初只是“现状基线 + 问题清单”初稿。经过本轮连续收口，下面这些点已经有代码落地：

- 已完成：
  - `app/core/job_workflow.py` 已成为 jobs workflow 规则的统一入口，`retry/cancel/cleanup/callback` 以及 `stage enqueue / submit_to_mineru / convert_package` 的关键迁移已集中定义。
  - `JobRecord` 已引入内部双层状态：`lifecycle_status` 和 `execution_status`，同时继续保留兼容性的单 `status` 投影。
  - `source_pdf_context` 已成为 `source_pdf` workflow 的内部结构边界，读写两侧都开始优先围绕它工作。
  - `command.py`、`lifecycle.py`、`stage.py` 的主要事件落盘路径已基本进入 `WorkflowEventIntent -> workflow_events.py -> JobEvent` 的统一映射模式。
  - `callback guard` 已基本收回到“边界安全校验 + payload 归一化”，job 当前状态合法性不再留在 guard 内部。
- 部分完成：
  - `JobStageService` 已比初始版本更薄，但仍同时承担 workflow driver、外部调用和部分成功/失败编排骨架。
  - repository seam 仍是 file backend 主导，只是 source_pdf 的 nested-first 写法已经推进到持久化边界。
- 尚未完成：
  - `job core` 和不同 workflow variant context 仍共处于同一 `JobRecord` 中，尚未进一步拆出更清晰的内部边界。
  - `stage executor / message store` 仍然直接绑定在 file spool + `BackgroundTasks` 模型上，未形成更窄的 protocol seam。
  - `artifact storage` 仍停留在 local file 语义，尚未真正抽出 storage adapter 边界。

## 一句话基线

当前 `md2word` 后端应被明确建模为：

- 一个单体、单实例的 FastAPI 异步工作流后端
- 以 `job` 为中心的主流程系统
- `conversion`、`MinerU`、`templates`、`term_rules` 围绕主链路提供支撑能力
- 当前默认执行适配器是 `BackgroundTasks + file-based stage spool + startup replay`

## 1. 静态分层视图

### 1.1 系统定位

当前组合根在 `app/main.py`。它负责构造：

- `Settings`
- file-based repository
- jobs/templates/term-rules services
- conversion entrypoint
- FastAPI app、middleware 和 `/api/v1` 路由树

这意味着当前系统不是“多个松散脚本 + 一层 API 包装”，而是已经形成了一个可运行的后端壳层。

### 1.2 当前语义分层

| 语义层 | 当前主要位置 | 当前职责 |
|---|---|---|
| boundary | `app/api/`、`app/api/v1/routers/`、`app/api/dependencies.py`、`app/api/mineru_callback_guards.py` | HTTP ingress、callback ingress、access control、请求归一化、response mapping |
| application | `app/services/jobs/`、`app/services/templates/`、`app/services/term_rules/`、`app/conversion/entrypoint.py` | workflow 编排、命令受理、查询投影、后台执行驱动、配置读取与导入应用 |
| domain | `app/core/job_models.py`、`app/core/job_workflow.py` | `job` 记录模型、双层状态、workflow 迁移规则、variant-specific context |
| infrastructure | `app/repositories/`、`app/clients/`、本地 `data/` 目录、`app/services/jobs/artifacts.py` 的 local file 约束 | 文件持久化、外部 MinerU 调用、本地产物存储、stage spool |

当前分层意图已经存在，但 `domain` 这一层还没有真正独立站稳，导致 workflow 规则仍然分散。

### 1.3 主域与支撑子系统

当前建议按下面的方式理解系统，而不是按目录平铺理解：

- `jobs`
  - 主流程域
  - 负责统一建模上传、入队、推进、查询、下载、重试、取消和清理
- `conversion`
  - 内部执行子系统
  - 对后端暴露 `ConversionRequest -> ConversionResult` 合同
- `MinerU`
  - 外部集成子系统
  - 负责 PDF 在线提交和 callback 结果回流
- `templates`
  - 配置型子域
  - 负责可见模板、默认模板和模板资产元数据
- `term_rules`
  - 配置型子域
  - 负责运行态规则 truth、导入导出、兼容 YAML 和模拟

### 1.4 当前已形成的可替换边界

后续架构演进不应一开始把所有模块接口化，而应先承认这 4 类 seam：

- `job repository`
  - 协议定义已存在于 `app/repositories/protocols.py`
- `stage message store / executor`
  - 当前是本地 `stage_messages/*.json` + `BackgroundTasks`
- `external providers`
  - 当前至少包括 MinerU 和 translation/LLM provider
- `artifact storage`
  - 当前是 local file，但 artifact alias、file type、media type、download contract 已单独收口

## 2. 动态 job 生命周期视图

### 2.1 统一 job aggregate

当前系统已经采用统一 `job` 聚合根，而不是两套任务模型：

- `JobRecord` 统一记录任务快照
- `JobFile` 记录输入/输出产物
- `JobEvent` 记录审计轨迹
- `JobStageMessage` 记录待执行后台动作
- `source_pdf_context` 作为 `source_pdf` workflow 的内部上下文边界，开始替代继续平铺更多上游字段

其中：

- `job` 是领域聚合根
- `lifecycle_status + execution_status` 组合表示内部真实状态
- 单 `status` 仍是当前对外兼容投影
- `events` 是审计轨迹，不是 event sourcing
- `artifacts` 是结果合同，不只是文件路径集合
- `stage message` 是执行机制，不等于领域状态本身

### 2.2 Workflow Variant A: MinerU 输出包直转 DOCX

当前第一条完整主链路是：

1. `POST /api/v1/jobs` 接收 MinerU 输出 zip
2. `JobCommandService` 创建 `job`
3. 登记 `source_package`
4. 写入 `convert_package` stage message
5. `BackgroundTasks` 调用 `JobStageService.dispatch_message()`
6. `build_job_conversion_request()` 组装 conversion 请求
7. `conversion_entrypoint.convert()` 进入 `app/conversion/`
8. 产出 `result_docx`，任务进入 `completed`

这条链路当前已经是后端最完整、最稳定的业务闭环。

### 2.3 Workflow Variant B: 原始 PDF 在线解析

当前第二条链路是：

1. `POST /api/v1/jobs/pdf` 接收原始 PDF
2. `JobCommandService` 创建 `job`
3. 登记 `source_pdf`
4. 写入 `submit_to_mineru` stage message
5. `BackgroundTasks` 调用 `JobStageService.dispatch_message()`
6. `MinerUClient.upload_files_batch()` 提交外部解析
7. 任务进入 `parsing`
8. `POST /api/v1/mineru-callbacks/result` 接收 callback
9. callback 归一化、鉴权和安全校验通过后，写入 `process_callback` stage message
10. `JobStageService` 处理 callback；`done + full_zip_url` 时先命中 `parsed` 里程碑，再自动恢复结果 zip 并继续后处理 conversion，最终到 `completed` 或 `failed`

当前这条链路的关键边界是：

- `parsed` 是同一 `job` 内部的中间里程碑
- callback 成功后通常不会稳定停在 `parsed`
- 当前实现会在原 `job` 上继续自动推进到 `completed`，而不是另建第二个 `job`

### 2.4 当前默认执行适配器

当前系统的异步执行不是抽象概念，而是具体实现：

- command API 先受理请求并创建 `job`
- stage message 先落到本地 spool
- `BackgroundTasks` 尝试立即驱动执行
- 服务启动时 `replay_pending()` 会重放 pending/running stage message

这套机制应被正式记为“当前默认执行适配器”，而不是继续隐含在实现里。

### 2.5 当前观测性模型

当前后端最稳定的观测性主键是三件套：

- `trace_id`
  - 单次请求或单次触发链路的关联键
- `job_id`
  - 整个长期 workflow 的主标识
- `events`
  - 跨请求、跨后台步骤的过程审计轨迹

因此，当前 job 的可观察性模型应理解为：

- `job snapshot` 说明“现在是什么状态”
- `events` 说明“怎么走到这里”
- `artifacts/files` 说明“当前有哪些输入输出结果”

## 3. 当前架构约束

当前已观察到的稳定约束包括：

- 外部 API 是异步工作流接口，不是同步转换接口
- `jobs` 读写已经形成轻量 command/query 分离，但还不是完整 CQRS
- 真相来源仍是快照型文件持久化：
  - `job.json`
  - `files.json`
  - `events.jsonl`
  - `stage_messages/*.json`
- `templates` 和 `term_rules` 当前属于配置型子域，不是与 `jobs` 平级的核心流程域
- 配置来源已经隐含分成三类：
  - versioned seed
  - runtime state/store
  - job-scoped request selection
- `conversion` 当前应被当作内部子系统，通过稳定合同暴露给后端壳层

## 4. 问题清单

### 4.1 第一优先级：jobs 域模型与 workflow 规则收口

#### 问题 1：workflow policy 分散在多个模块

状态：`部分完成`

当前 workflow 规则没有单一来源，主要分散在：

- `app/services/jobs/command.py`
- `app/services/jobs/stage.py`
- `app/services/jobs/lifecycle.py`
- `app/api/mineru_callback_guards.py`

影响：

- 同一种状态迁移规则可能在不同入口重复实现
- callback、retry、cancel 的合法性约束难以统一维护
- `parsed -> completed` 已补全，后续若继续扩展 workflow variant，未集中规则仍会扩大修改面

当前进展：

- 已抽出 `app/core/job_workflow.py`
- `command`、`stage`、`lifecycle`、`callback` 的关键状态迁移已开始共享这套规则
- `job_created`、`mineru_callback_received` 等非迁移型 application 事件已进入统一 event intent / mapping 路径，但仍不属于状态机本体

建议收口方向：

- 抽出纯 `workflow policy / state machine` 模块
- 由 `command`、`stage`、`lifecycle`、`callback` 共同调用

#### 问题 2：`job.status` 混合了领域里程碑和执行中态

状态：`部分完成`

当前 `status` 同时包含：

- 生命周期里程碑：`parsed`、`completed`、`failed`
- 执行中态：`queued`、`submitting`、`converting`

影响：

- `job` 当前到底是“业务走到哪一步”还是“当前执行器正在做什么”不够清晰
- 状态机文档化和测试化都比较困难

当前进展：

- `JobRecord` 已新增 `lifecycle_status` 和 `execution_status`
- workflow transition 已统一同时写入双层状态和兼容 `status`
- API schema 仍继续暴露单 `status`

建议收口方向：

- 内部模型拆成“生命周期状态 + 执行状态”两层
- 对外 API 暂时继续暴露兼容性的汇总状态字段

#### 问题 3：`JobRecord` 混合共享核心字段和 variant-specific 上下文

状态：`部分完成`

当前 `JobRecord` 里既有所有 job 共享字段，也有 `source_pdf` 才会使用的 MinerU 上下文字段。

影响：

- `job aggregate` 的核心字段和 workflow variant context 没有分层
- 以后 variant 继续增多时，`JobRecord` 会继续膨胀成字段堆

当前进展：

- 已新增 `source_pdf_context`
- 读侧已优先从 `source_pdf_context` 读取，回退旧平铺字段
- repository 持久化边界已开始以 nested-first 写法为主，再同步兼容平铺字段

建议收口方向：

- 概念上区分 `job core` 和 `workflow context`
- 第一阶段不要求拆成多表或多存储，但要先把模型语义理顺

### 4.2 第二优先级：application driver 与边界职责收口

#### 问题 4：`JobStageService` 职责过重

状态：`部分完成`

当前 `JobStageService` 同时承担：

- stage message 消费
- workflow dispatch
- 外部 provider 调用
- conversion 调用
- job 状态推进
- event 写入
- 失败处理和日志记录

影响：

- application driver 与 domain rule 混在一起
- 后续替换执行适配器时，风险面过大

当前进展：

- 状态迁移判定已大幅迁往 `job_workflow.py`
- 事件落盘已大幅迁往 `workflow_events.py`
- `stage.py` 内部也已抽出 transition apply / failure handling 等小 helper
- 但它仍然是主要的 workflow driver 和 orchestration 容器

建议收口方向：

- 把它明确为 application 层 workflow driver
- 把状态迁移判定逐步迁回纯领域规则层

#### 问题 5：callback boundary 和 workflow 规则仍有混层

状态：`大体完成`

当前 callback guard 既做：

- token/checksum/result URL 等边界安全校验
- 当前 job 状态是否允许处理 callback 的 workflow 约束

影响：

- boundary layer 和 domain/application layer 没有完全分开
- 规则难以被其他入口复用

当前进展：

- callback guard 已只保留安全校验和 payload 归一化
- job 状态合法性已经迁入 `job_workflow.py`
- 剩余工作主要是保持这种边界不再回退，而不是继续做大改

建议收口方向：

- callback guard 只保留安全与输入可信性校验
- job 当前状态是否合法，由 workflow policy 决定

### 4.3 第三优先级：可替换 seam 的收口质量

#### 问题 6：repository seam 已存在，但执行链路仍有具体实现耦合

状态：`待做`

`query` 和 `lifecycle` 已经主要依赖 protocol，但 `stage` 仍直接依赖 file-backed repository 能力。

影响：

- repository 可替换性和 executor 可替换性还没有完全分开
- 未来若改 message store，`JobStageService` 仍需要较大改动

当前进展：

- 持久化边界已经能处理 `source_pdf_context -> 平铺兼容字段` 的同步
- 但 repository protocol 还没有围绕 nested-first 模型或 stage message seam 继续收窄

建议收口方向：

- 保留现有 file backend
- 逐步把 stage 所需能力也收敛到更窄的 protocol seam

#### 问题 7：artifact 已形成合同雏形，但 storage backend 语义还未完全显式化

状态：`待做`

当前 artifact 的 alias、file type、media type、download URL 已经有统一规则，但 storage backend 仍默认为 local file 实现细节。

影响：

- “artifact 是结果合同”这一点在代码里有雏形，在架构语义上还不够显式

建议收口方向：

- 保持当前 local file 实现
- 在架构与应用层明确 artifact policy 与 storage adapter 的分工

## 5. 当前阶段判断

截至当前，第一轮“jobs 域模型与 workflow 收口”已经不是纯规划，而是进入了代码落地阶段：

- 已完成或大体完成：
  - 纯 `workflow policy / state machine`
  - 双层内部状态
  - `source_pdf_context` 的 nested-first 边界
  - `command` / `lifecycle` / `stage` 的主要事件落盘统一模式
  - callback 边界与 workflow 规则分离
- 仍在进行中：
  - `JobStageService` 继续压薄
  - repository seam 继续收窄
  - artifact storage 语义进一步显式化

## 6. 建议的下一步顺序

如果继续按增量方式推进，当前建议顺序如下：

1. 保持这份文档与代码现状同步，不再把已完成事项当作“纯建议”
2. 评估 artifact storage adapter 的真实抽象边界
3. 评估 worker / stage message store 的替换路径
4. 决定是否对外公开双层状态，或继续只暴露兼容 `status`
5. 决定是否收紧 `retry/cancel/cleanup-local-files` 的权限模型

## 6.1 `parsed -> completed` 在线链路的当前合同

当前 `parsed -> completed` 在线链路已经落地，不再只是未来前置条件。它的当前合同如下。

### 合同 1：application stage

系统使用明确的后续 stage 承接 callback 后处理：

- `process_callback` 命中 `done + full_zip_url`
- job 先命中 `parsed` 里程碑
- 系统自动 enqueue 并 dispatch `convert_parsed_result`

### 合同 2：远端结果 zip 的落盘 artifact

当前已拍板并实现的 artifact 合同是：

- 新增本地 artifact：`parsed_result_package`
- 对应 alias：`parsed-result-package`
- 对应本地逻辑路径：`input/parsed-result.zip`
- 该 artifact 作为“远端 MinerU 结果 zip 的本地恢复副本”存在
- 它不会覆盖既有 `source_package`

### 合同 3：双层状态迁移

`parsed` 之后的状态迁移已经接入现有双层状态模型：

- `parsed + idle -> queued`
- `parsed + queued -> converting`
- `parsed + converting -> completed/failed`

也就是说，`parsed` 不再只是 callback 终点，而是同一 job 上的下一段 workflow 起点。

### 合同 4：provider / storage 责任分界

当前职责归属是：

- 远端 HTTP 下载职责放在 `MinerUClient`
- stage 只负责 orchestration：决定何时触发下载、下载到哪个 `JobPaths` 位置、以及何时把产物登记进 `files.json`
- artifact service 继续只负责 file type / alias / path / media type 合同，不负责主动发起远端下载

### 当前仍可继续细化的点

当前链路已经可自动推进到 `completed`。后续如果继续优化，应优先评估 `parsed_result_package` 的长期存储策略、失败后的 retry 入口，以及是否需要把 `parsed` 从公开 schema 中进一步淡化。

## 7. 本文档的边界

这份初稿当前刻意不展开：

- `app/conversion/runtime/*` 的算法与渲染实现细节
- 多实例 / 独立 worker / 数据库 / 消息队列的分布式终态设计
- `templates` 和 `term_rules` 的 CRUD 终态设计
- event sourcing、完整 CQRS 或工作流 DSL

这些内容都应建立在当前基线先被统一确认之后再单独展开。
