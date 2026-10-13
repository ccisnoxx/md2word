# CON-101 技术设计

状态：规划待评审，2026-10-12。要求与验收由 [prd.md](prd.md) 定义；源码和探针证据见 [research/current-behavior.md](research/current-behavior.md)。

## 当前实现与目标边界

五模式的后端 owner 是 `app/domains/translation/modes.py`，前端显示和能力 owner 是 `frontend/src/utils/format.ts`。DocumentJobService 负责创建、重试、克隆、配置快照和业务错误；schema 负责请求输入类型。Worker 已按模式跳过翻译，不改成新流水线。

本任务补 HTTP 兼容、direct 写入隔离及 UI 投影，不实现目标文档中的新阶段、quality/review/delivery 状态、发布 API、Word 预览或表格算法。API 的 available actions 继续由后端拥有；UI 的“有无翻译配置”是模式展示能力，不能用于推断发布资格。

## 数据流

```text
UI 五种规范模式 / 历史 API 输入
→ DocumentJobCreateRequest：窄 alias 归一化，仍为五值 Literal
→ router：现有认证、readiness
→ DocumentJobService：源文件权限、mode 一致性、direct 资源约束
→ 模板与符号规则快照 / 仅翻译模式的术语与 Profile 快照
→ DocumentJobRecord：规范 mode + 单 result_file_id
→ MinerU → DocumentIR
   ├─ direct → Renderer
   └─ 四方向翻译 → 现有批次/Provider → Renderer
→ 现有下载与 available_actions

详情响应 → 共享模式能力
→ direct：普通资源/诊断 + 不含翻译字段的只读展示快照
→ translation：现有资源、Prompt 元数据、QA、批次诊断
```

## 服务端输入与模式合同

1. 保留 TranslationMode / DocumentJobMode 的五个规范值。HTTP schema 对明确的 `zh2zh` / `zh_to_zh` 历史字符串在 Literal 检查前归一化，复用 modes.py 的归一函数；其他输入仍按既有 schema 验证。
2. 仅识别已知兼容字符串，沿用它们的 trim/lower 语义；None 保留可选字段语义，不把未知、空串、数字或容器转成 direct。不将 schema 改为开放 str，不向 OpenAPI/前端枚举加入 alias。
3. `DocumentJobService._resolve_document_job_mode` 在非 None 的 translation_mode 上使用共同归一结果，再比较 mode。历史内部 alias 继续有效；不能复制另一张 alias 表到 service。
4. 响应 translation_mode 继续由规范 job.mode 派生，写入 snapshot/event 的模式为 canonical。`mode` 字段本身不扩展未被证明存在的 `zh2zh_pdf_to_word` 等别名。

## Direct 写入与运行时边界

在 DocumentJobService 内收口 direct 新写入意图，可用一个有实际多调用者的私有校验方法供 create/retry/clone 使用，不引入新 service/factory/strategy。

- 空或未给的翻译字段表示无选择；非空 `term_version_id`、`translation_term_set_id/version`、`translation_profile_id/version` 对 direct 明确拒绝。
- 在创建/重绑任何翻译资源、生成 job ID 对应记录、绑定源文件或投递队列前完成校验。保留现有访问控制和状态验证优先级。
- `_resolve_term_version_id` 对 direct 提前返回 None，不调用 `TermVersionService.resolve_for_job`，即使该方法在空值时本来会返回 None。
- direct `debug_full_text=true` 继续先检查角色；Operator 403，Admin direct 400。不把非法请求悄悄改成 false。
- versioned 资源层已有 direct 拒绝翻译 Profile/Term Set 的防线，保留；DocumentJobService 让 file/sqlite/MySQL 的新 direct 输入在进入依赖前得到一致结果。
- 正常 direct 创建的新快照保留既有形状，翻译绑定为空、debug false；无须删除响应字段、引入新 DB schema 或重写共享 ResourceSnapshot。
- Worker `execution.py` 已有模式分流和术语提前返回，预期仅作为验证对象。若测试发现入口实际执行翻译，先定位唯一 owner，再决定最小修复；涉及阶段/generation 变化则重新评审，不顺手扩大本任务。

任务配置查询 `GET /config-summary` 会列举四方向 Profile/术语的只读元数据，供模式可用性展示。该接口不调用 Provider，不属于 direct 的任务资源加载或执行；本任务不删除全局配置摘要或治理页面。

## 历史快照、重试与克隆

区分“新请求显式选择”和“已有记录携带的惰性字段”。不能因新约束在读取时拒绝旧记录，不能改写旧结果、历史 request_snapshot 或审计。

| 场景 | 处理 |
|---|---|
| 新 direct 创建/clone 显式选择翻译资源 | 权限和策略验证后 400 拒绝，不加载资源。 |
| direct 默认 retry | 沿用原快照和现有 generation；遗留翻译字段保持惰性，不调用翻译服务。 |
| direct retry 重选符号规则/使用最新规则 | 仍允许既有授权行为；不解析或重新绑定翻译资源。 |
| direct clone keep_source_snapshot | 保留来源与快照追溯，新 job ID；不物化遗留翻译资源，不改源任务。 |
| direct clone use_current_defaults | 只解析模板/符号规则；新结果不继承有效翻译绑定。 |
| 四方向 clone/retry | 维持原配置策略和权限，不改变 Prompt/hash 固化语义。 |

只需覆盖现实字段形状，不为不存在的历史模式添加猜测兼容层。若确有无法惰性处理的历史 direct 快照，保留证据并重新评审，不能迁移性清库或静默损失信息。

## 前端设计

### 共享名称与入口

`format.ts` 的 label/shortLabel 统一使用 PRD 五个产品名称。现有 JobTable、JobsPage、JobDetail、TemplateDetail 等消费者自动更新；只修仍存在的独立旧文案，不改布局、主题、路由或资源治理架构。

上传页的 direct 说明使用“保持原文语言和语义，不调用 AI”。任务配置中的 term_rule_set 改称“符号与排版规则”；保留它的选项、值和 API 字段。

### 上传资源与提示

复用 `documentJobModeRequiresTranslationResources` 和现有 watch/payload guard。翻译切 direct 时清空术语/Profile/debug；只隐藏 AI 专用控件，不能隐藏模板、符号规则或 P0 错误。

`documentJobConfig.ts` 可承载与当前模式相关的展示纯函数，供上传组件使用并做行为单测：

- direct 不显示明确的 translation_term/profile 缺失 warning 家族；按 `config_summary.py` 和现有 displayText 的机器 code 做精确分类，不按“翻译”中文字符串或任意宽泛正则吞警告。
- 所有未知 warnings、模板/符号规则错误、readiness blockers 原样保留。
- 当前 direct 时不展开其他语言的术语/Profile 配置细节；禁用的翻译方向可给简短未就绪提示，不能伪装可用。
- 翻译模式仍显示相关的完整资源未就绪信息。

### 详情与快照投影

用现有模式能力给翻译术语/Profile、旧翻译术语版本、Provider 批次和 AI 专用区添加展示条件。批次/QA 请求已经 guarded，保持现有调用次数，不新增 API 请求。

详情折叠配置 JSON 采用纯展示副本，对 direct 排除：顶层 `term_version_id`、`translation_profile`、`debug_full_text_enabled`；`term_assets` 的 translation 字段；`resources` 的 translation_term_set、translation_profile、translation_prompt_id、translation_prompt_content_hash。Profile 内模型随 Profile 一并不展示。保留模式、文档语言、模板/符号规则、MinerU 和来源信息。仅处理已知结构，不建立通用递归“脱敏引擎”。

该投影不修改响应对象、持久快照、事件、审计，也不是安全授权层。翻译任务展示不受影响。retry/clone 对话框已有条件分支，主要回归并同步术语文案。事件时间线只显示 message/trace，当前无 payload 漏出，不需改它。

## API、类型、数据库与状态影响

| 边界 | 影响 |
|---|---|
| OpenAPI | 保持路径、字段、五值 enum 和响应形状；补 direct 资源约束描述，使用 export_openapi.py 生成快照。描述无变化时也须检查 current，不制造无意义 diff。 |
| 前端类型 | TranslationMode/DocumentJobMode 集合不变；在创建/clone/retry 字段补模式适用说明。不能在 UI 类型中引入 alias。 |
| DB/迁移 | 无表/列/索引/模型序列化版本变更、无 backfill。新请求被规范化后写 canonical；历史 JSON 原样读取。 |
| 状态机 | 不新增 stage、quality/review/delivery；direct 仍用现有分流，后续任务负责目标阶段。 |
| 权限 | 不新增角色能力；配置发布、调试、owner、download token 等仍由后端校验。 |
| 结果和发布 | 单 result_file_id、不新增 DOCX；不新增发布入口，不宣称现有 publication 不可变已实现。 |

## 错误映射

| 输入/条件 | 结果 |
|---|---|
| 两种 alias + direct/无 mode | 成功后只保存/返回 canonical direct。 |
| alias 与翻译 mode 冲突 | 400 `invalid_request`，不写 job。 |
| 非法 mode/translation_mode 或字段类型 | 422 `validation_error`，保留 trace/envelope。 |
| direct 非空翻译资源选择 | 400 `invalid_request`，任务级翻译 resolver 调用为 0。 |
| Operator 显式资源重选但无权限 | 维持既有 403；不为统一错误把权限检查后移。 |
| Operator debug true / Admin direct debug true | 分别 403 `role_forbidden` / 400 `invalid_request`。 |
| P0 必需执行链未就绪 | 503 `document_jobs_not_ready`，无写入。 |
| 翻译资源不存在/语言不匹配、Provider 失败 | 维持现有 404/409/400 与执行错误，不静默转 direct。 |

direct 新选择的 400 是有意收紧：当前 legacy term_version_id 可被加载，versioned/legacy 的部分新资源错误不同。它修复冻结的 direct 边界；不承诺所有历史非法请求仍被接受。评审须特别检查此兼容面。

## 幂等、并发、generation 与不可变性

模式归一化是确定性的，不新增幂等键或创建去重协议。保持当前创建重复请求语义，不暗示“一次请求只建一次”已有额外保证。retry_count、batch generation、CAS、回调重放及取消规则不改；拒绝的新请求发生在 mutation 前，不增加额外竞态写点。

保留模板/符号/Profile 的已发布资源 hash 和任务快照，UI 投影只读；不修改发布资源字节、既有 DOCX、下载授权或审计。当前文档 PublicationRecord 缺口属于 QA-605，不能靠本次 UI 得出发布安全结论。

## 安全、隐私与可观测性

无新外部调用/凭据/Provider/依赖；MinerU 保持唯一解析器。测试使用合成输入和现有 fake，不需要专有样本授权。UI 隐藏不是访问控制；后端拒绝不能削弱现有 token、owner/tenant/company、文件完整性、路径安全和资源 hash 校验。

保留 job_created、retry、clone 和错误 trace 的审计链，不新增全文或 Prompt 日志。零调用通过 spy/fake 计数、批次/AI Artifact 缺席和正常主 DOCX 三类证据证明；不新增仅为计数的生产指标或全量日志。

## 兼容、部署与回滚

本轮无部署动作。未来交付先部署含 alias/资源边界的 API，再部署 UI；Worker 的规范 mode 不变，可读新任务。无 DB 部署顺序和回填需求，无需 feature flag。

- UI 回滚只撤回本任务文案/条件展示，不能回写快照；会重新暴露旧展示缺口，不改变 DOCX。
- 后端回滚不会遇到新模式或新列，但回到旧版本会再次拒绝 HTTP alias，并重新允许旧 direct 术语加载。因此已启用兼容输入后应保留该窄修复或前滚，不能把整包回滚描述为无行为风险。
- 无论哪种回滚都不得删除 alias、历史审计/任务/文件、清空数据库或覆盖已发布资源。
- 规划撤回仅针对当前子任务文档、CON-101 manifest 增量与父 children 关系，保留 `.gitignore` 和其他任务；不在本会话执行。

## 风险与评审重点

重点是 schema alias 对 error/status 的影响、direct 禁止翻译资源的新写入边界、历史快照兼容，以及 UI 隐藏不能误删符号规则/P0 blocker。实际 API 候选 diff 出来后需独立只读复核这些具体风险；本规划不是独立代码审查。没有要求新外部系统、破坏迁移或改变冻结产品规则的未解冲突。

## 2026-10-12 实施授权

用户已明确接受当前三份规划并授权 CON-101 实施。本子任务已 start 为 in_progress；上文 planning/待评审语句保留为规划阶段记录。实施和验证后 manifest 仅标 review，人工验收前不归档、提交或 push。

## 2026-10-12 人工验收与收尾授权

用户已人工审查并接受 CON-101 的实现、测试证据和残余风险，同时确认当前任务 commit plan 并授权提交及归档。AC1–AC8 的逐项核验见 [validation.md](validation.md)。本任务补齐了实际差距，manifest 由 review 改为 done，不属于 skipped_existing。上文规划/实施门的状态描述保留为阶段历史；收尾不新增功能、不修改其他任务状态、不 push。
