# DocumentJob 模式与 direct 资源合同

## 1. 范围与触发

修改任务模式、创建 schema、资源绑定、重试/克隆或任务配置 UI 时适用。后端模式 owner 是 `app/domains/translation/modes.py`，前端名称/能力 owner 是 `frontend/src/utils/format.ts`；避免在入口各自复制模式表。

## 2. 接口

- `POST /api/v1/document-jobs`：`mode` 或 `translation_mode` 选择模式。
- `POST /api/v1/document-jobs/{id}/retry`：保持模式与 generation 合同。
- `POST /api/v1/document-jobs/{id}/clone`：保持源任务模式，新任务 ID；不是模式切换接口。
- `GET /api/v1/document-jobs/config-summary`：只读资源摘要，包含四方向元数据，不执行翻译。

## 3. 请求、响应与展示

规范值为 `direct/en2zh/ru2zh/zh2en/zh2ru`，分别对应既有五种 `*_pdf_to_word` mode。用户名称为“原文 PDF 转可编辑 Word”、英译中、俄译中、中译英、中译俄。

- 历史 `zh2zh`、`zh_to_zh` 仅在服务端输入归一为 direct。请求 schema 在 Literal 前处理明确 alias；OpenAPI/前端枚举保持五值，响应/snapshot/event 保存规范值。
- direct 使用模板、MinerU、符号与排版规则，不调用翻译术语服务、Profile payload/Prompt 解析、Provider 或翻译批次服务。符号规则 `term_rule_set` 不属于翻译术语。
- direct 的新请求不接受非空 `term_version_id`、`translation_term_set_id/version`、`translation_profile_id/version`。校验必须在翻译加载与 mutation 前，但仍保留权限/状态检查优先级。
- 历史 direct 快照可读；默认 retry、keep-source clone 的惰性字段不重新加载或回写清理，源任务与审计保留。
- direct UI 隐藏翻译资源、Prompt/模型、Provider/AI 调试区，折叠快照也使用只读投影。不能改响应原对象或用隐藏代替后端授权。
- 克隆追溯中的 `clone.source_term_version_id` 也属于翻译字段，direct 展示副本仅移除该字段，保留来源任务、模板和策略；翻译任务仍完整展示。
- 只过滤已知翻译资源 warning；未知 warning、P0 blockers、模板/符号规则错误保留。翻译方向缺资源继续禁用。
- 页面动作消费后端 `available_actions`；模式能力不用于推断发布资格，不增加前端状态机。

## 4. 验证与错误矩阵

| 条件 | 结果 |
|---|---|
| alias 单字段/与 direct mode 相符 | canonical direct；正常权限和源文件验证。 |
| 规范化后双字段冲突 | 400 `invalid_request`。 |
| 未知、空串、非法类型 | 422 `validation_error`，不静默变 direct。 |
| 有权限的 direct 新请求显式翻译资源 | 400 `invalid_request`，零加载/绑定/投递副作用。 |
| 无资源重选权限 | 保留现有 403。 |
| Operator debug true / Admin direct debug true | 403 `role_forbidden` / 400 `invalid_request`。 |
| 必需 P0 执行链未就绪 | 503 `document_jobs_not_ready`。 |

## 5. 正常、缺省与非法场景

- 正常：direct 绑定 published 模板和符号规则，生成一份主 DOCX，零 AI/批次/翻译 Artifact。
- 缺省：未给 mode/translation_mode 使用 direct；翻译默认资源缺失不构成 direct 的翻译依赖。
- 非法：direct 传显式翻译术语，不能先加载后丢弃；未知模式不能回退 direct。

## 6. 必要测试

- `tests.test_document_job_modes`：真实请求 schema alias、双字段与非法输入、direct 零翻译加载/单 DOCX、拒绝无 mutation、历史 retry/clone。
- `tests.test_fastapi_jobs_backend`：复用四方向资源、语言匹配、debug/owner 权限和正式 Worker 回归。
- `frontend/src/utils/format.test.ts`、`documentJobConfig.test.ts`：模式能力、精确 warning 过滤、投影不修改输入。
- mock API UI smoke：两角色 direct 创建/详情、翻译切 direct payload、展开快照隐藏、长文案宽度与键盘。
- OpenAPI 由 `scripts/ops/export_openapi.py` 生成，`check_release.py` 检查；不得手改生成 JSON 或放宽断言。

## 7. 错误与正确做法

错误：schema 先以五值 Literal 拒绝历史 alias，只在 service 内做归一；或 direct 先调用翻译术语服务，再把结果设为 None。

正确：输入 alias 在 schema 类型检查前归一；应用层 direct 在进入翻译依赖前结束该分支。

```python
# 原文转换只解析普通转换资源，历史被动字段不能激活翻译加载。
if not spec_for_document_job_mode(mode).is_translation:
    return None
```

UI 同样先按共享模式能力判断是否展示，再构造展示副本；不能用删除后端 snapshot 字段来隐藏配置。
