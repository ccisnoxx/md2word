# CON-101：产品模式和 UI 文案收口

## 任务身份与评审状态

- 阶段：R1（合同和状态）；父任务：`10-12-datasheet-docx-delivery-quality`。
- 子任务：`.trellis/tasks/archive/2026-10/10-12-con-101-product-mode-ui-copy`；分支：`md2word/CON-101`。
- 前置依赖：BAS-001，manifest 为 `done`，归档记录有 2026-10-12 人工接受实现、验证和残余风险的证据。
- 本轮仅调查和规划，Trellis/manifest 均保持 `planning`；没有实施批准。不执行 `task.py start`、业务修改、提交或 push。
- 产品真源：`docs/product/prd.md`、`docs/product/scope-and-decisions.md`；范围定义：backlog CON-101；技术约束：已接受 ADR。目标文档不代表现有能力已经实现。

## 目标与用户结果

Operator/Admin 在创建、列表、详情、重试、克隆及模板验证的任务模式展示中，只面对一种原文转换和四种翻译方向。用户能明确知道原文转换保持语言和语义，不调用 AI；不因翻译资源未配置而误以为 direct 不能创建，也不会把符号与排版规则误认为翻译术语。

| 产品名称 | 任务模式 | 翻译模式 |
|---|---|---|
| 原文 PDF 转可编辑 Word | `direct_pdf_to_word` | `direct` |
| 英译中 | `en2zh_pdf_to_word` | `en2zh` |
| 俄译中 | `ru2zh_pdf_to_word` | `ru2zh` |
| 中译英 | `zh2en_pdf_to_word` | `zh2en` |
| 中译俄 | `zh2ru_pdf_to_word` | `zh2ru` |

## 已确认背景

完整证据见 [调查记录](research/current-behavior.md)。

- 五种模式、四种 Prompt、前端共享模式定义及 Worker direct 分流已经存在，复用而不重建。
- `app/domains/translation/modes.py:130` 保留两种历史 alias；`app/domains/document_jobs/schemas.py:17` 的 Literal 请求类型却在 HTTP 服务入口之前拒绝它们。只读 schema 探针已复现。
- `frontend/src/utils/format.ts:49` 的 direct 名称尚未按产品 PRD 收口；`PdfUploadPanel.vue:208` 的全局 warnings 和 `:239` 的未就绪提示会在 direct 下展示翻译配置信息。
- `frontend/src/pages/JobDetailPage.vue:128`、`:219`、`:904` 分别无条件展示翻译资源、Provider 批次区和原始任务配置 JSON。
- `app/domains/document_jobs/service.py:2374` 在 direct 下仍进入术语服务；显式旧 `term_version_id` 会加载翻译术语。创建与执行均不得触发翻译服务的合同尚未闭合。

本任务需要实现差距，不建议整项 `skipped_existing`。已满足的模式枚举、翻译分支、部分表单隐藏和权限边界仅验证、复用。

## 范围与需求

### R1 产品模式与术语

全部任务模式入口使用上表名称，direct 明示“保持原文语言和语义，不调用 AI”。模式集合、内部 ID、顺序及四种语言方向不变。任务中的 `term_rule_set` 展示为“符号与排版规则”，继续可用于 direct；翻译术语仅用于跨语言任务。

新 UI、维护中的产品说明和新 API 示例不再把同语言原文转换描述成一种翻译能力。历史任务证据和冻结决策中的禁止条款保留；不以全仓文本清零为验收方式。

### R2 历史输入兼容

服务端继续接受历史 `zh2zh` / `zh_to_zh`，归一为 `direct`，响应、事件及新任务持久化使用规范模式。别名只用于兼容输入，不进入新 UI、前端模式联合类型、公开规范枚举或新 API 示例。保留其他已有内部 alias，不新增语言方向或同语言 Prompt。

同传 `mode` 和 alias 时，归一后相符则接受，不符则明确拒绝；未知值、不正确类型、空串不能静默变成 direct。

### R3 Direct 资源和展示隔离

- direct 创建与执行不调用 AI Provider、翻译术语加载、Translation Profile/Prompt 解析或批次翻译服务，不生成翻译批次和 AI 调试产物。
- direct 保留模板、符号与排版规则、MinerU、源语言和普通诊断能力。
- direct 页面隐藏翻译术语、翻译配置、Prompt、模型、Provider 批次、AI 调试项；配置快照折叠区也不得重新展示这些项目。
- 四方向翻译保留原有资源选择、未就绪禁用和 Admin 调试权限。切回 direct 后清空翻译选择和调试状态，请求不携带翻译资源，`debug_full_text` 缺省或为 false。
- direct 不展示仅翻译资源缺失的提示；保留所有 P0 执行 blocker、普通配置错误和未知 warning。翻译按钮仍可禁用，并给出简短“该翻译方向未就绪”说明。
- 显式向 direct 绑定翻译资源的请求在任何相关加载和任务写入之前拒绝；不能通过 UI 隐藏代替后端验证。历史记录继续可读，不回写清理快照或审计。

### R4 合同、文档与证据

更新相关请求 schema/类型说明、UI 文案、API 文档和必要 OpenAPI 描述；以 API 测试证明 alias 在真实路由可用，以 fake/spy 证明 direct 创建和执行无翻译调用，以前端单测和定向浏览器行为证明隐藏及模式切换有效。

## 不变量

1. 一次只实现 CON-101，不提前实现 backlog 其他项；保持模块化单体，不引入微服务、Kafka、向量库或第二套转换流水线。
2. 一个 DocumentJob 只有一个用户主 DOCX；其他语言通过新建或克隆任务完成，本任务不增加克隆改模式能力。
3. `direct_pdf_to_word` 不调用 AI Provider、翻译 Prompt、翻译术语集或翻译服务；历史 alias 不得删除，不新增中文转中文 Prompt。
4. MinerU 是唯一 PDF 解析入口；不增加 OCR 预检或多解析器路由。
5. HTML 可解析时必须输出 Word 原生表格，不以截图作为默认简化方案。
6. 质量 `blocked` 与翻译 `unreviewed` 可以内部下载，不能批准或发布。该目标规则不得被削弱；统一质量/发布的缺失能力归后续任务，不冒充本任务完成。
7. 前端消费后端权威状态或 `available_actions`，不得自行推断发布资格。
8. 不新增双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
9. 不为测试削弱权限、审计、不可变发布、技术 Token、内容完整性和路径安全。

## 非目标

- 改变主输出数量、新增语言方向、重做上传页面视觉体系。
- CON-102 阶段扩展、CON-103 状态/DB 模型、CON-104 下载发布合同、QA-601/QA-605 统一复核或发布。
- MinerU、DocumentIR、表格、Renderer、翻译算法、Prompt 内容、技术 Token 或翻译质量算法调整。
- 移除全局翻译治理页面、改变角色权限、清理历史审计/快照、数据库迁移、部署或真实外部调用。

## 权限与失败语义

- 保持 JWT/owner/admin、租户/公司隔离、源文件可用性及文件访问边界；Operator 创建 published 资源、Admin 草稿模板验证、重试/克隆资源重选权限按当前合同执行。
- 未知模式维持 HTTP 422 `validation_error`；规范化后模式冲突维持 400 `invalid_request`。
- direct 显式绑定翻译资源返回 400 `invalid_request`，包括旧 `term_version_id`；只对新写入意图生效。此处会收紧当前旧术语可加载、部分后端返回 503 的行为，须在 API 文档及评审中说明。
- 保持 `debug_full_text=true` 的权限优先级：Operator 403 `role_forbidden`；有权限的 direct 请求 400 `invalid_request`。不能静默关闭后继续创建。
- P0 必需执行链未就绪仍为 503 `document_jobs_not_ready`；翻译资源失败不改成 direct fallback。
- 上述输入拒绝不创建任务、不绑定 source file、不投递 Worker；错误保持统一 envelope/trace ID。

## 验收条件

| ID | 可观察结果 |
|---|---|
| AC1 | 创建、列表/筛选、详情和模板验证仅使用五个产品名称，direct 有无 AI 说明；无旧同语言翻译入口。 |
| AC2 | 两种历史 alias 经真实创建 API 成功得到规范 direct；相符的双字段成功、冲突 400、未知值 422；无新增 alias 枚举。 |
| AC3 | 无翻译默认资源时 direct 仍可在 P0 ready 前提下创建；spy 记录术语/Profile/Prompt/Provider 的任务级调用为 0。 |
| AC4 | direct 显式翻译资源与调试请求按权限/错误合同拒绝，且没有任务、绑定或队列副作用；四方向合法翻译仍能绑定各自资源。 |
| AC5 | Admin 与 Operator 的 direct 上传、详情、诊断及配置快照不展示翻译/AI 项；模板与符号规则保留，翻译→direct 切换无陈旧资源 payload。 |
| AC6 | direct 执行 fake MinerU→IR→DOCX 成功，一份用户主 DOCX，零翻译批次/AI 日志；四方向原有资源绑定、QA 和调试权限回归通过。 |
| AC7 | 历史 direct 记录和惰性兼容字段可读；重试/克隆不加载遗留翻译资源，不改变源任务或审计；generation、CAS 和下载授权未改。 |
| AC8 | API 文档、手写类型、规范 OpenAPI 五枚举一致；相关单测/构建/定向 smoke 和既定回归门禁有明确结果，未执行项如实记录。 |

## 停止条件与规划门

依赖未被接受；PRD/冻结决策/ADR 出现无法消解冲突；需要未批准的破坏性迁移、覆盖发布件或删除审计；必须改变冻结的模式、原生表格、下载或发布规则；必要样本/外部选择/安全授权缺失且 fake/adapter 无法完成范围内验证时停止。

本轮没有发现上述阻塞，技术差距可在现有模块和 fake 环境内解决。规划已经收敛，等待用户审核本 PRD、design 和 implement；审核完成前不进入实施。

## 2026-10-12 实施授权

用户已明确接受当前三份规划并授权 CON-101 实施。本子任务已 start 为 in_progress；上文 planning/待评审语句保留为规划阶段记录。实施和验证后 manifest 仅标 review，人工验收前不归档、提交或 push。

## 2026-10-12 人工验收与收尾授权

用户已人工审查并接受 CON-101 的实现、测试证据和残余风险，同时确认当前任务 commit plan 并授权提交及归档。AC1–AC8 的逐项核验见 [validation.md](validation.md)。本任务补齐了实际差距，manifest 由 review 改为 done，不属于 skipped_existing。上文规划/实施门的状态描述保留为阶段历史；收尾不新增功能、不修改其他任务状态、不 push。
