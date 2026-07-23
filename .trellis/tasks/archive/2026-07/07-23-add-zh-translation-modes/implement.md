# 实施计划：扩展翻译模式与 Prompt 编辑工作区

## 1. 建立 Profile 内 Prompt 合同

- [ ] 在 translation models/schemas 中增加强类型 Prompt scheme，并扩展 draft/version/snapshot response 的安全字段。
- [ ] 在 `profiles_service.py` 中集中实现内置 seed、payload invariant、正文 hash、唯一名称和 `prompt_version` 指针校验。
- [ ] 为新 payload 写入 `schema_version=2`；未知更高版本显式失败，不能误入 legacy 分支。
- [ ] 让四个默认 Profile seed 都包含一个内置 Prompt；中文目标继续保留既有 `zh-CN`，新目标分别为 `en`、`ru`。
- [ ] 为旧 draft 增加一次性持久化物化，为旧 published profile 增加有界 legacy 解析；新格式缺失数据显式失败。

## 2. 实现 Prompt 草稿操作

- [ ] 新增 Prompt create/update/activate/delete 请求模型与 admin 路由。
- [ ] 新建方案复制指定方案正文并由服务端生成 ID。
- [ ] 保存和 activate 使用 `expected_snapshot_hash` 检测并发冲突。
- [ ] 删除检查 built-in、当前指针和所有历史 published profile 引用；只移除满足条件的 draft 自定义方案。
- [ ] 为 Prompt 写操作记录不含正文的 audit metadata。

## 3. 让运行时使用版本化 Prompt

- [ ] 扩展 Translation Profile/job resource snapshot 的当前 Prompt ID/hash，保持对外响应不含正文。
- [ ] Worker 按 job 绑定的不可变 Profile 版本解析 Prompt Markdown。
- [ ] 将内部 Prompt snapshot 传给 DocumentIR translator/provider，移除 versioned mode 对固定文件的运行时依赖。
- [ ] 保留并标注 file/sqlite 与旧 published profile 的有界固定文件分支；新格式数据不允许 fallback。
- [ ] AI call audit 只记录 Prompt ID/hash 等安全摘要。
- [ ] 保持 `_full_request_payload()` 字段白名单，确保 `debug_full_text` archive 不写入 system Prompt Markdown。

## 4. 新增中译英、中译俄

- [ ] 扩展中央 TranslationMode、TranslationLanguagePair、DocumentJobMode 与两个 TranslationModeSpec。
- [ ] 新增 `translation_zh2en.md`、`translation_zh2ru.md` 内置 seed。
- [ ] 增加两组反向 `v1` 翻译术语和独立默认 Profile/prompt version。
- [ ] 保持现有映射校验、默认资源、readiness、MinerU、provider source/target、目标语言渲染和 QA 链路。

## 5. 实现前端 Prompt 工作区

- [ ] 更新 API 类型/wrapper，补全 `language_pair`、Prompt scheme 和 mutation request/response。
- [ ] 扩展共享文档任务模式定义和上传/模板验证入口。
- [ ] 在 TranslationProfilesPage 新增全宽 Prompt 工作区：方案选择、Markdown textarea、草稿/线上当前状态。
- [ ] 实现“新建 Prompt”“保存 Prompt”“设为当前方案”“删除 Prompt”及 loading/error/禁用原因。
- [ ] 实现未保存内容在切换 Prompt、Profile 和离开路由时的确认。
- [ ] 保持 admin 写权限、普通用户只读、危险删除确认和 375/768/1024/1440px 响应式布局。
- [ ] 不增加 Markdown 编辑器依赖、预览器、WYSIWYG 或自动保存。

## 6. 最小回归测试

- [ ] 新增 `tests/test_translation_profile_prompts.py`：seed、集中 invariant、CRUD、CAS、受控删除、发布/回滚、schema version 和 legacy 物化。
- [ ] 扩展 `tests/test_fastapi_jobs_backend.py`：Prompt API 权限/错误码、published profile/job 绑定、两个新模式默认资源和对外脱敏。
- [ ] 扩展 `tests/test_document_ir_translation.py` 与 `tests/test_llm_client_characterization.py`：绑定 Prompt 正文优先于固定文件，source/target 覆盖 zh2en/zh2ru。
- [ ] 扩展 debug archive 回归：`debug_full_text=true` 仍不包含 system Prompt Markdown。
- [ ] 新增 `frontend/src/pages/TranslationProfilesPage.test.ts`，扩展 `frontend/src/utils/format.test.ts` 与 `documentJobConfig.test.ts`：Prompt 按钮/脏状态/请求合同、五模式顺序和 readiness。
- [ ] 扩展 `tests/test_database_job_repository.py`：resource_versions 重启后新 Profile payload 和默认指针保持一致。

## 7. 文档、契约与验证

- [ ] 更新 Document Jobs、Translation Profiles 和 Translation Profile/Segment Trace 文档。
- [ ] 导出 `docs/api/openapi.json`，检查前端手写类型一致。
- [ ] 执行以下最小覆盖优先的命令：

```bash
.venv/bin/python -m unittest tests.test_resource_versioning
.venv/bin/python -m unittest tests.test_translation_profile_prompts
.venv/bin/python -m unittest tests.test_llm_client_characterization tests.test_document_ir_translation
.venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_profile_prompt_crud_and_permissions \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_uses_bound_profile_prompt \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_translation_debug_archive_excludes_system_prompt
.venv/bin/python -m unittest tests.test_database_job_repository
cd frontend && npm run test:unit
cd frontend && npm run build
.venv/bin/python scripts/ops/export_openapi.py
.venv/bin/python -m unittest tests.test_openapi_export
.venv/bin/python scripts/ops/check_release.py
```

- [ ] 有可用认证环境时检查 Translation Profiles 页面 1440/1024/768/375px；否则记录未运行真实页面 smoke 的原因。
- [ ] 最终 `rg` 审计所有 TranslationMode/DocumentJobMode 分支、固定 prompt 文件读取和 prompt_version 自由文本用法。
- [ ] 检查 diff 无第二事实源、猜测别名、正文泄露、silent fallback、无关重构或未说明旧行为变化。
- [ ] 写明部署回滚前置：停止新翻译任务；若不能恢复与启用方案一致的固定 Prompt，则不回退旧代码而采用滚动前进。
- [ ] 记录真实英语/俄语模型质量未做在线人工验收的剩余风险。
