# 扩展翻译模式与 Prompt 编辑工作区

## 目标

在现有“中文直译、英译中、俄译中”文档任务基础上，新增“中译英”和“中译俄”两种完整翻译模式；同时让管理员能在翻译配置中选择 Prompt，在 Markdown 编辑工作区维护正文，并执行保存和受控删除。任务执行必须使用已绑定的 Prompt 快照，不能出现页面保存成功但运行时仍读取旧固定文件的双重事实源。

## 背景与已确认事实

- 翻译模式、文档任务模式及语言元数据由 `app/domains/translation/modes.py:11` 的类型和 `app/domains/translation/modes.py:39` 的 `TRANSLATION_MODE_SPECS` 统一拥有。
- DocumentIR 翻译器已经按 `language_pair` 推导 source/target，并使用统一批次翻译链路；新增语言方向不需要新翻译引擎。
- 上传页的可见模式、标签、创建语言、资源和 QA 能力由 `frontend/src/utils/format.ts:39` 的共享模式定义控制；模板验证入口当前在 `frontend/src/pages/TemplateDetailPage.vue:172` 单独列出模式。
- 默认 Translation Profile 和翻译术语会在启动时幂等补齐缺失语言对；前提是中央模式规格和 seed 资源包含该语言对。
- `GET /api/v1/document-jobs/config-summary` 已通过 `translation_defaults` 与 `readiness.translation_modes` 表达任意语言对；`en2zh_available`、`ru2zh_available` 是既有兼容字段。
- `docs/dev/translation-profile-and-segment-trace-guide.md:218` 当前明确排除 `zh2en/zh2ru`，本任务必须同步公共文档合同。
- 翻译配置页当前只允许编辑 `prompt_version` 字符串，并明确写着“不提供提示词正文编辑”（`frontend/src/pages/TranslationProfilesPage.vue:3`）；前端没有 Prompt 内容或删除 API。
- Translation Profile payload 和快照当前只保存 `prompt_version`，不保存 Markdown 正文（`app/domains/translation/schemas.py:12`、`app/domains/translation/profiles_service.py:384`）。
- 真实 provider 请求按语言对直接读取 `resources/prompts/translation_*.md`（`app/domains/translation/provider.py:128`、`app/domains/translation/modes.py:153`），完全不读取 profile 中的 `prompt_version`；直接从页面改仓库文件会绕过已发布版本和任务快照。
- 现有 `ResourceVersionService` 已提供 draft、publish、set-default、rollback、disable 状态机，但 `ResourceType` 尚不包含独立 Prompt，Translation Profile 路由也没有 Prompt CRUD。
- 2026-06-21 的历史会话只证明当时页面有意限定为“不提供提示词正文编辑”，未发现关于未来删除语义或独立 Prompt 资源模型的既有产品决定。

## 需求

### R1. 模式合同

- 新增规范翻译模式 `zh2en`、`zh2ru`。
- 新增文档任务模式 `zh2en_pdf_to_word`、`zh2ru_pdf_to_word`。
- `zh2en` 的模式元数据为：源语言 `zh`、目标语言 `en`、默认文档语言 `zh`、MinerU 语言 `zh`、目标文档语言 `en`、默认 profile `electronics-zh2en`。
- `zh2ru` 的模式元数据为：源语言 `zh`、目标语言 `ru`、默认文档语言 `zh`、MinerU 语言 `zh`、目标文档语言 `ru`、默认 profile `electronics-zh2ru`。
- 不新增未经既有兼容合同证明的 `llm_zh_to_*`、`zh_to_*` 等别名；新调用使用规范值。

### R2. 翻译资源

- 新增 `translation_zh2en.md` 与 `translation_zh2ru.md` 作为新语言对的内置 Prompt seed，保持现有电子元器件技术文档领域、逐项回填、占位符保护和严格 JSON 输出合同。
- 新增 `zh2en`、`zh2ru` 的 `v1` seed 术语；优先复用现有双语术语的反向映射，不引入新的术语管理机制。
- 为两个新语言对生成独立默认 profile 和 prompt version；默认 profile 的 `target_language` 必须分别为英语和俄语，不能沿用现有 `zh-CN` 默认值。
- 启动补齐只创建缺失的默认资源，不覆盖现有 profile、术语版本或默认指针。

### R3. API、任务执行与可用性

- `POST /api/v1/document-jobs` 接受两个新 `translation_mode` 和对应 `mode`，并继续执行现有 mode/translation_mode 一致性校验。
- 两个模式仅允许 `document_language=auto` 或 `zh`。
- 创建任务时按对应语言对绑定默认或显式 published Translation Term Set 与 Translation Profile；语言对不匹配继续显式失败。
- MinerU 使用中文源语言，provider request 的 source/target 分别为 `zh/en` 与 `zh/ru`，渲染目标文档语言分别为 `en` 与 `ru`。
- MySQL versioned resource mode 下，provider 必须从任务绑定的不可变 Translation Profile 版本读取当前 Prompt 正文；file/sqlite legacy mode 继续使用固定文件，但不得消费或伪装支持页面编辑结果。
- 配置摘要在 `translation_defaults` 和 `readiness.translation_modes` 中返回两个新语言对；保留既有 `en2zh_available`、`ru2zh_available`，不新增重复的专用布尔字段。
- 兼容旧后端响应时，前端不得把缺失的 `zh2en/zh2ru` readiness 错当成 `ru2zh_available`；缺失即不可用。

### R4. 前端入口与能力

- 上传面板按现有顺序追加“中译英”“中译俄”，创建请求分别发送 `translation_mode=zh2en/zh2ru` 与 `document_language=zh`。
- 两个新模式与现有翻译模式一样要求翻译术语和 Translation Profile，并支持翻译 QA。
- 模板验证对话框提供相同两种模式，复用共享的模式到请求字段映射。
- 现有三种模式的标签、顺序和行为保持不变。

### R5. 文档与契约快照

- 更新 Document Jobs、Translation Profiles 和 Translation Profile/Segment Trace 文档中的支持范围、模式枚举、默认资源与 QA 范围。
- 刷新 OpenAPI 快照和前端手写联合类型，使前后端公共枚举一致。

### R6. Prompt 选择与 Markdown 编辑工作区

- 每个翻译语言对对应的 Translation Profile 草稿可保存多个命名 Prompt 方案，并且只能有一个当前启用方案。
- Profile payload 使用现有 `prompt_version` 字段作为当前启用 Prompt ID 的唯一指针；该值必须引用同一 payload 中真实存在的 Prompt，不能再作为无约束自由文本。
- 每个语言对至少包含一个受保护的内置 Prompt，正文从对应 `resources/prompts/translation_*.md` seed 初始化。
- 翻译配置页提供 Prompt 列表；选中 Prompt 后加载其名称、Markdown 正文、内置状态、正文 hash 和是否为当前启用方案。
- 页面提供清晰的 Markdown 编辑工作区，管理员可编辑正文；只读用户仍可查看但不能保存或删除。
- 页面提供“新建 Prompt”“保存 Prompt”“设为当前方案”和“删除 Prompt”按钮；新建方案默认复制当前选中方案正文，避免创建无法保存的空 Prompt。
- 保存、切换当前方案和删除只修改 Translation Profile 草稿；沿用现有“发布并设默认”动作后，草稿所选方案才影响未来任务。历史任务和既有 published 版本不变。
- Prompt 修改 API 必须携带当前 draft `snapshot_hash`，并发修改时返回明确冲突，不能后写静默覆盖另一管理员的工作。
- 保存必须进入后端 Translation Profile 持久化与版本/快照合同，不能直接修改仓库中的 `resources/prompts/*.md`。
- 发布后的 profile 固化 Prompt 列表、当前 Prompt ID、Markdown 和正文 hash；任务快照只暴露 Prompt ID/hash 等安全元数据，正文保留在不可变 profile payload 中。
- Provider 在 versioned mode 下必须消费任务绑定 profile 中的 Prompt Markdown；固定文件只作为内置 seed 和有界 legacy profile 兼容来源，不能继续主导新格式 profile。
- Prompt 正文必须做非空、Markdown 文本长度和语言对归属校验；API、日志和审计不得记录密钥或非必要的完整正文。
- 即使管理员开启 `debug_full_text`，AI debug archive 也只能记录待译正文、术语和 provider 响应，不得把 system Prompt Markdown 写入归档。
- 删除操作必须有确认步骤；只允许物理删除未发布、未被任何 Translation Profile 或历史任务引用的自定义 Prompt。
- 内置、当前启用、已随任何 published profile 保存或已被引用的 Prompt 禁止物理删除；管理员只能切换当前方案并发布新版本，不能留下“零启用”状态。
- 自定义 Prompt ID 由服务端生成，显示名称在同一 Translation Profile 内唯一；不要求跨语言对共享 Prompt。

## 验收标准

- [ ] AC1：上传面板显示五种模式，新增模式标签为“中译英”“中译俄”，且构造的请求语言字段正确。
- [ ] AC2：API 能以 `translation_mode` 或对应 `mode` 创建两种新任务，并拒绝冲突模式、非法源文档语言及跨语言资源。
- [ ] AC3：两个新任务分别绑定 `translation-terms-zh2en` / `electronics-zh2en` 和 `translation-terms-zh2ru` / `electronics-zh2ru` 的默认 published 版本。
- [ ] AC4：两个新 profile 的默认目标语言分别为英语和俄语；现有 en2zh/ru2zh 默认行为不变。
- [ ] AC5：LLM 根据语言对选择正确 prompt，provider request source/target 分别为 `zh/en`、`zh/ru`，逐项 JSON 回填合同不变。
- [ ] AC6：配置摘要包含两个新 `translation_defaults` 和 `readiness.translation_modes` 条目；旧专用 readiness 字段继续可用。
- [ ] AC7：上传入口、模板验证入口和任务详情 QA 能力均识别两个新模式。
- [ ] AC8：OpenAPI、前端类型和相关开发/API 文档列出五种任务模式与四种翻译语言对。
- [ ] AC9：每个语言对可保存多个命名 Prompt，且草稿和 published profile 均始终只有一个 `prompt_version` 指向的当前方案。
- [ ] AC10：选择 Prompt 后可加载并编辑 Markdown；管理员新建/保存后重新加载内容一致，普通用户只能查看。
- [ ] AC11：删除 Prompt 有确认和引用保护；只有未发布且未引用的自定义 Prompt 可物理删除，受保护 Prompt 返回明确错误且不会丢失数据。
- [ ] AC12：草稿中“设为当前方案”不会影响当前 published 默认配置；发布并设默认后，只有新任务使用新方案。
- [ ] AC13：Translation Profile 发布和新建任务固化 Prompt ID、hash 与不可变正文；之后编辑草稿不改变既有 published 版本或历史任务输入。
- [ ] AC14：versioned mode provider 实际使用任务绑定 profile 中的 Prompt 正文；测试能区分绑定正文与仓库固定文件，防止假保存。
- [ ] AC15：并发 Prompt 修改使用 draft snapshot hash 检测冲突，不静默覆盖。
- [ ] AC16：普通 AI call log、完整正文 debug archive、审计和对外 job response 均不包含 system Prompt Markdown。
- [ ] AC17：后端定向测试、前端单元测试、前端构建、OpenAPI 快照检查和 release contract check 通过；无法本地验证的真实模型翻译质量作为剩余风险明确报告。

## 范围外

- 不新增翻译引擎、provider、批次算法、QA 数据结构、数据库 schema 或迁移脚本。
- 不新增历史兼容别名、独立 readiness 布尔字段或第二套模式映射。
- 不新增本地 MinerU debug preset、Golden Sample/P1 正式样本或真实在线模型验收；需要发布级语言质量证据时另设任务。
- 不回填或迁移既有任务、profile 与术语版本。
- 不引入新的 Markdown 编辑器依赖；优先复用 Element Plus textarea 和现有工作区样式，除非实现阶段证明原生能力无法满足明确验收标准。
- 不跨语言对共享 Prompt，不新增独立 Prompt 数据表、通用插件系统、Markdown 预览器或所见即所得编辑器。

## 风险与延后项

- 提示词和 seed 术语只能提供可运行基线；英语、俄语技术表达质量仍需真实样本文档和人工验收。
- 长期运行环境必须执行现有启动 bootstrap，才能补齐新语言对默认资源；该过程需由自动化测试证明幂等且不覆盖既有默认值。
- OpenCode 历史会话读取器当前不可用；本次 `trellis mem` 在可读平台中未发现早于当前会话的相关产品决策。
- 现有已发布 Translation Profile 没有 Prompt 正文；它们需要有界 legacy 解析，直到管理员从带 Prompt 列表的草稿发布新版本。兼容分支必须显式标记，且新格式 profile 不得回退到固定文件。
- 回滚到旧代码会忽略新 Profile 中的 Prompt Markdown 并重新读取固定文件；因此上线后回滚必须先停止新翻译任务，并恢复与当前启用方案一致的固定 Prompt 或选择滚动前进，不能把直接代码回退视为行为等价。

## 已确认的关键决定

- 同一翻译语言方向支持多个命名 Prompt 方案，但每个 Translation Profile 版本只能启用一个。
- Prompt 方案归属于对应语言对的 Translation Profile，不跨语言对共享。
- 新建方案默认复制当前选中方案；保存和切换只改草稿，沿用现有发布动作后才影响未来任务。
- 仅未发布、未引用的自定义 Prompt 可物理删除；内置、启用、已发布或已引用方案不可删除。
- 采用现有 Element Plus 和工作台视觉合同，不新增 Markdown 编辑器依赖。
