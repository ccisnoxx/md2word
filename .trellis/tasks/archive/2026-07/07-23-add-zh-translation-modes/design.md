# 技术设计：扩展翻译模式与 Prompt 编辑工作区

## 最小可行设计

继续以 `TRANSLATION_MODE_SPECS` 作为语言模式唯一事实源，以 Translation Profile published version 作为 versioned mode 的翻译配置唯一事实源。每个 Profile payload 内嵌多个 Prompt 方案，现有 `prompt_version` 字段改为当前启用 Prompt ID 的唯一指针。

Prompt 不建立独立数据表或第二套发布系统。新建、编辑、切换和删除均修改 Profile draft；现有“发布并设默认”原子地固化整份配置，未来任务绑定该不可变版本。这个设计复用当前 ResourceVersionService、默认指针、回滚和 job resource snapshot，所需新状态最少。

本任务保留一个 Trellis task，不拆子任务：新语言对的内置 Prompt seed、Profile payload、编辑器和 provider 读取共享同一数据合同，拆开会形成无法独立验收的中间状态。

## 核心不变量

1. 一个 `language_pair` 对应一个内置 Translation Profile ID。
2. 一个 Profile draft/published payload 可以包含多个 Prompt 方案。
3. `prompt_version` 必须且只能指向 payload 中一个 Prompt ID，因此每个版本恰好启用一个方案。
4. Prompt Markdown 的权威副本在 versioned Profile payload；`resources/prompts/*.md` 只负责内置 seed 和旧 profile 兼容。
5. Job 绑定不可变 published Profile ID/version/hash；执行时从该版本解析 Prompt，草稿变化不能影响它。
6. Prompt 正文不进入公开 job response、普通日志或审计正文。

## Profile payload

新格式 payload 在现有字段上增加 `prompt_schemes`，并复用 `prompt_version`：

```json
{
  "schema_version": 2,
  "translation_profile_id": "electronics-en2zh",
  "language_pair": "en2zh",
  "prompt_version": "translation-minimal-v1",
  "prompt_schemes": [
    {
      "id": "translation-minimal-v1",
      "name": "内置英译中 Prompt",
      "markdown": "# Role: ...",
      "content_hash": "sha256:...",
      "built_in": true
    },
    {
      "id": "prompt_ab12...",
      "name": "精简数据手册方案",
      "markdown": "# Role: ...",
      "content_hash": "sha256:...",
      "built_in": false
    }
  ],
  "target_language": "zh-CN",
  "domain": "electronics engineering technical document",
  "model": "model-name",
  "max_pages_per_batch": 20,
  "max_chars_per_batch": 60000
}
```

约束：

- Prompt ID 由服务端生成；内置 ID 沿用现有 `prompt_version` 值，避免第二个兼容映射。
- 名称去除首尾空白后在单个 Profile 内唯一。
- Markdown 非空，使用命名常量限制最大长度；hash 始终由服务端计算。
- `built_in` 由服务端 seed 决定，客户端不能修改。
- payload hash自然覆盖 Prompt 列表、当前指针和正文。
- 一个集中校验函数在 draft 读取、基础字段 update、Prompt create/update/activate/delete、publish 和执行解析前验证：列表非空、ID/名称唯一、hash 正确、`prompt_version` 指向存在项且只有该指针表示当前方案。

## Prompt 生命周期

### 内置 seed

`bootstrap_default_profiles_if_missing()` 为四个语言对从对应固定 Markdown 文件创建一个内置方案，并把 `prompt_version` 指向它。固定文件继续随代码发布，但 UI 保存不修改文件。

### 新建

`新建 Prompt` 需要名称，服务端生成 ID，并复制当前选中 Prompt 的 Markdown 到新方案。新方案不是当前方案，管理员可继续编辑并保存。

### 保存

保存只更新当前 Profile draft 中选中方案的名称、Markdown 和 hash。请求必须携带当前 `snapshot_hash`；服务端发现 draft 已变化时返回 `409 conflict`。

### 设为当前方案

草稿操作只把 `prompt_version` 改为目标 Prompt ID。当前线上默认 Profile 不变；用户继续使用现有“发布并设默认”后，新建任务才采用该方案。

### 删除

删除前由服务端验证：

- 不是内置 Prompt；
- 不是当前 draft 或当前默认 published profile 的 `prompt_version`；
- 未出现在该 Profile 的任何 published/superseded/disabled version 的 `prompt_schemes` 中；
- draft snapshot hash 未冲突。

满足条件时只从 draft payload 移除。`ResourceVersionService` 保证 published version 不可通过草稿路径修改，当前仓库没有删除 resource version 的业务路径；Document Job resource snapshot 又保存 profile ID/version/hash。因此“未出现在任何 published profile”同时证明没有历史 job 能引用该 Prompt，无需扫描整个 job repository。若未来引入 resource version 物理清理，必须重新评估这一删除不变量。

一旦 Prompt 随任一 Profile 版本发布，就不再物理删除；停止使用的方式是选择另一方案并发布新默认版本。

## API

保留现有 Profile API，并扩展 draft response 的 `prompt_schemes`。新增以下 admin 写操作：

```text
POST   /api/v1/translation-profiles/{profile_id}/draft/prompts
PUT    /api/v1/translation-profiles/{profile_id}/draft/prompts/{prompt_id}
POST   /api/v1/translation-profiles/{profile_id}/draft/prompts/{prompt_id}/activate
DELETE /api/v1/translation-profiles/{profile_id}/draft/prompts/{prompt_id}
```

请求：

- create：`name`、`source_prompt_id`、`expected_snapshot_hash`
- update：`name`、`markdown`、`expected_snapshot_hash`
- activate：`expected_snapshot_hash`
- delete：`expected_snapshot_hash`

写操作返回最新 `TranslationProfileDraftResponse`。权限使用 `require_admin_actor`；审计只记录 action、profile ID、prompt ID、hash、长度和 trace ID，不记录 Markdown 正文。

已有 `PUT /{profile_id}/draft` 继续负责目标语言、领域、模型和批次字段；前端不再把 `prompt_version` 当自由文本。该路径和 publish 都调用同一 payload invariant，不能绕过 Prompt 非空或当前指针校验。

## 执行数据流

```text
Prompt 工作区修改 Profile draft
  → 发布并设默认（不可变 Profile payload）
  → 创建 Document Job（绑定 profile ID/version/snapshot_hash）
  → request snapshot 记录 active prompt ID/content_hash，不记录正文
  → Worker 按绑定版本读取 immutable Profile payload
  → DocumentIRTranslationService 接收 Prompt snapshot
  → Provider 使用 snapshot.markdown 作为 system prompt
  → AI audit 记录 Prompt ID/hash，不记录完整 Markdown
```

`TranslationProfileSnapshot` 增加当前 Prompt ID/hash；完整 Markdown 只在执行阶段从不可变 ResourceVersion payload 解析为内部对象，不放进对外 job schema。

## 语言模式扩展

在 `app/domains/translation/modes.py` 增加：

- `zh2en` / `zh2en_pdf_to_word`：source/default/MinerU=`zh`，target/render=`en`，profile=`electronics-zh2en`
- `zh2ru` / `zh2ru_pdf_to_word`：source/default/MinerU=`zh`，target/render=`ru`，profile=`electronics-zh2ru`

不增加历史别名。术语 seed 使用现有双语条目的反向映射。新 Prompt 文件只作为新 Profile 的内置 seed。

## 旧数据兼容

现有 published Profile payload 只有 `prompt_version`，没有 `prompt_schemes`。兼容边界如下：

- 读取/创建旧 draft 时，从该语言对固定 Markdown seed 物化一个内置方案并持久化到 draft；管理员发布后得到新格式版本。
- 解析旧 published Profile 创建/执行 job 时，可按已知语言对从固定文件物化内置 Prompt；Prompt ID 确定性复用旧 payload 的 `prompt_version`，正文 hash 由固定文件计算并写入 job 安全快照。这是有注释和测试的 legacy 分支。
- 新格式 Profile 缺少 Prompt、指针无效或 hash 不匹配时必须显式失败，禁止回退固定文件。
- `schema_version=2` 表示带 Prompt 列表的新格式；未知更高版本显式失败，不能按 legacy 处理。
- file/sqlite legacy mode 的配置页本就不可用，继续沿用固定文件运行路径，不声称支持页面 Prompt 编辑。

## 前端工作区

沿用现有 TranslationProfilesPage 和工作台视觉令牌，不引入新字体、颜色系统或编辑器依赖：

- 上方保留 Profile 列表和基础字段。
- 下方新增全宽 Prompt 工作区：左侧为方案选择/状态，右侧为带标签的等宽 Markdown textarea。
- 工具栏提供“新建 Prompt”“保存 Prompt”“设为当前方案”“删除 Prompt”。
- 同时显示“草稿当前方案”和“线上当前方案”，避免误以为保存草稿已经上线。
- 切换 Profile/Prompt 或离开页面时，如有未保存 Markdown，显示确认。
- 删除使用危险确认对话框；禁用原因以文字展示，不只使用颜色。
- 只读用户可浏览；写按钮按现有 RoleGate/admin 状态禁用。
- 1024px 以下改为纵向布局，覆盖 375/768/1024/1440px，无页面级横向溢出。
- 不增加 Markdown 预览、WYSIWYG、语法高亮或自动保存。

## 安全、并发与错误

- 外部输入在 Pydantic/service 边界校验名称、ID、正文长度、语言归属和 active 指针。
- Prompt mutation 使用 `expected_snapshot_hash` 做 CAS；冲突返回稳定 `409 conflict`。
- 受控删除失败返回明确错误，不 silent no-op。
- 不在日志、audit、config-summary 或 job response 中返回完整 Prompt Markdown。
- `TranslationCallAuditRecorder._full_request_payload()` 继续使用字段白名单；即使 `debug_full_text=true`，debug archive 也不得加入内部 Prompt snapshot/Markdown，并以测试锁定。
- Provider 错误继续使用现有 DocumentIR translation failure 合同。

## 文档与 OpenAPI

同步：

- `docs/api/document-jobs.md`
- `docs/api/translation-profiles.md`
- `docs/dev/translation-profile-and-segment-trace-guide.md`
- `docs/api/openapi.json`

P1 英译中正式样本与本地 debug preset 保持原范围。

## 验证与回滚

- 单元测试覆盖 payload invariant、Prompt CRUD、唯一当前指针、CAS、受控删除、legacy 物化和 provider 实际正文。
- API 测试覆盖权限、错误码、发布后 job 绑定与对外脱敏。
- 前端测试覆盖按钮状态、未保存确认和 payload；build 覆盖 Vue/TypeScript。
- UI 使用既有 flat workbench 风格和 Element Plus 语义控件；有可用认证环境时补真实页面 smoke，否则明确缺口。
- 无数据库 schema 变化。旧代码会忽略新 Profile Prompt 正文并退回固定文件，因此回滚前必须停止创建/执行新翻译任务，并恢复与线上启用方案一致的固定文件；无法安全恢复时应滚动前进。新代码遇未知 Profile schema version 显式失败。
