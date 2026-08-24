# 实施清单

## Phase A：启动门禁

- [x] 用户在规划完成后的消息中明确批准本修订规划，再执行 `python3 .trellis/scripts/task.py start 08-24-redeploy-default-word-template`。
- [x] 记录 `HEAD`、`origin/main`、完整 `git status` 和已识别改动；不覆盖或提交未识别文件。
- [x] 复核线上：`jobs=0`、版本集合 V1-V4、默认 V2、序列 5、V3/V4 四个运行时文件；任一变化均停止并更新规划。

## Phase B：把当前基础资产定义为新 V1

- [x] 保持用户当前 `resources/templates/default/datasheet_template.docx` 原路径和字节，不复制或重命名为 V5。
- [x] 在用户当前 `resources/template_configs/datasheet_template.yaml` 原文件中设置：
  - `footer.enabled: true`
  - `footer.left_text: v1.0`
  - `footer.right_text: info@ichelps.com`
  - 保留 `footer.show_page_number: true`
- [x] 保留 `datasheet_template_v2.yaml`、`datasheet_template_v3.yaml` 删除，不恢复旧内容，不创建 V5 YAML。
- [x] 修改 `templates_manifest.yaml` 为 `version: 1`，layout path 指向 `resources/template_configs/datasheet_template.yaml`。
- [x] 更新当前内置配置 owner：`app/core/config.py`、`app/conversion/runtime_helpers.py`、开发质量脚本和 debug JSON、`docs/dev/local-conversion-sandbox.md`、`resources/template_configs/md2docx.yaml`。
- [x] 全仓搜索 v2/v3 路径，只保留明确描述历史或独立测试版本场景的引用；不得留下当前配置 fallback。

## Phase C：Spec 与测试重置

- [x] 更新 `.trellis/spec/backend/quality-guidelines.md`、`template-layout-configuration.md`：当前 bundled seed 为新的 `default@1`，旧 V1/V2/V3 合同因本次开发重置退役；后续版本重新遵守不可变规则。
- [x] 更新 `tests/test_template_layout_config_schema.py`：加载基础 YAML，固定新 V1 YAML hash，断言页脚、最小字号和 manifest V1。
- [x] 更新 `tests/test_document_ir_word_renderer_layout.py` 的当前 seed/v2/v3 文件引用，继续覆盖 table minimum、页脚 PAGE field 和字体槽位。
- [x] 更新 `tests/test_fastapi_jobs_backend.py` 中真正依赖 bundled V2 seed 的断言和 bootstrap 场景；保留构造任意第二版本的通用版本治理测试。
- [x] 增加或调整最小 bootstrap 回归：空资源库创建并默认新 V1，首次 draft 分配 V2，旧路径不存在时不发生 fallback。
- [x] 固定新基础 DOCX/YAML hash，验证 DOCX ZIP/OOXML 完整性。

## Phase D：本地验证与独立检查

- [x] 运行 backend 定向门禁：

```bash
.venv/bin/python -m unittest tests.test_template_layout_config_schema
.venv/bin/python -m unittest \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_table_fit_uses_bundled_minimum_to_keep_right_column_membership \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_two_column_landscape_fallback_keeps_context_bound_and_records_each_step \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_landscape_fallback_moves_single_column_context_with_table \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_native_custom_footer_and_ignores_source_footer \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_configured_body_header_and_footer_font_slots
.venv/bin/python -m unittest tests.test_resource_versioning
```

- [x] 运行 `tests.test_fastapi_jobs_backend` 中 seed bootstrap、manifest detail、layout-config 读取和版本分配定向测试；若共享合同风险扩大，再运行完整模块。
- [x] 运行前端门禁：

```bash
npm --prefix frontend run test:unit
npm --prefix frontend run build
npm --prefix frontend run test:smoke -- tests/smoke/core-flow.spec.ts --workers=1
```

- [x] 运行：

```bash
.venv/bin/python scripts/ops/check_release.py
git diff --check
```

- [x] 使用 `trellis-check` 独立检查 seed 重置、路径 owner、版本序列、前端统一状态机、页脚实际 owner、生产删除范围和回滚顺序。
- [x] 审阅 diff：不得存在 V5、旧 V2/V3 current path、双路径 fallback、第二版本体系、通用删除能力、凭据或无关修改。

## Phase E：commit 与 push 授权门禁

- [x] 向用户展示精确 commit 计划并取得确认。建议两个提交：
  1. `feat(frontend): 统一模板版本生命周期操作入口`
  2. `chore(template): 重置默认模板开发基线为 V1`
- [ ] 第二个提交包含基础 DOCX/YAML、V2/V3 删除、manifest/路径 owner、Spec/测试和本 Trellis 任务文件。
- [ ] 不包含未识别 dirty 文件；提交后记录 commit SHA。
- [ ] 不自动 push；取得单独 push 授权后执行并用 `git ls-remote` 锁定目标 SHA。

## Phase F：准备 hostdzire 新 release

- [ ] 使用 SSH alias `hostdzire`；host-key conflict 立即停止。
- [ ] 记录旧后端 release、旧前端 symlink、目标 SHA、Compose 状态和非敏感 deployment 标识。
- [ ] 通过 bare repo + `git archive` 创建新后端 release，复用旧 `.env` 和内部账号文件，仅更新 APP_VERSION/DEPLOYMENT_ID。
- [ ] 构建新后端镜像，但暂不切换正在运行的 API/Worker。
- [ ] 从同一目标 commit 构建并上传新前端静态 release，暂不切换 symlink。
- [ ] 在目标镜像中先运行不依赖生产版本状态的 release check；失败则停止，不执行重置。

## Phase G：停止服务并重置旧模板状态

- [ ] 写操作前再次确认 `jobs=0`、旧版本/默认/序列/文件集合与规划一致。
- [ ] 停止 API、Worker；确认两个容器不再运行，MySQL/Redis保持运行。
- [ ] 在 MySQL 单一事务内：
  - 锁定 `template/default` 的四条版本、默认指针、序列行。
  - 断言版本集合 `{1,2,3,4}`、默认 2、序列 5、jobs 0。
  - 删除四条 `resource_versions`，影响行数必须为 4。
  - 删除一条 `resource_default_versions`，影响行数必须为 1。
  - 删除一条 `resource_version_sequences`，影响行数必须为 1。
  - 任一断言不符则回滚并重新启动旧服务。
- [ ] 事务提交后精确删除 `/app/var/config/templates/default/v3`、`v4`；不删除整个 `default`、共享 volume 或 audit events。
- [ ] 记录脱敏重置证据到 `deployment-audit.md`。

## Phase H：启动新 release 并核验新 V1

- [ ] 使用新 release 启动 API、Worker，完成 Compose、启动日志、live/ready/metrics。
- [ ] 读回 Template Version，必须只存在新的 `default@1`，状态 published、默认 true；V2-V4 均不存在。
- [ ] 核对新 V1 payload 的 DOCX/YAML 路径和 SHA-256 与目标 commit 完全一致。
- [ ] 核对 `resource_version_sequences` 尚无 `template/default` 行；通过定向服务检查证明下一 draft 将分配 V2，但不为此在线创建多余草稿。
- [ ] 运行 runtime release check + Golden Sample preflight；失败进入 Phase K。

## Phase I：真实默认 V1 验证

- [ ] 使用 `tests/fixtures/golden_samples/pdfs/OPA228_P1.pdf` 创建 direct 任务，让默认配置解析并固化 `template_version_id=default@1`。
- [ ] 等待任务 `succeeded`，核对资源快照和输出 metadata 均为新 V1。
- [ ] 下载 DOCX并检查 OOXML：`v1.0`、`info@ichelps.com`、原生 `PAGE` field、positional tab 和字体槽位。
- [ ] 使用 WPS/Word 打开产物，确认左/中/右页脚可见、页码正确、正文与页脚不重叠。
- [ ] 任一验证失败不得切换前端；进入 Phase K或修复后创建新 release。

## Phase J：前端切换与最终门禁

- [ ] 原子切换前端 `current` symlink，执行 `nginx -t` 和 reload。
- [ ] 检查公网首页、静态资源、页面样式页、模板版本总览、live/ready。
- [ ] 用安全已登录会话确认两处页面只显示新的 V1“当前默认”，生命周期入口行为正常。
- [ ] 最终核对 release SHA、deployment id、V1 hash、默认任务、API/Worker 和无 blockers；补全 `deployment-audit.md`。

## Phase K：失败回滚

- [ ] 重置前失败：保持旧服务与旧数据库状态，不切换前端。
- [ ] 重置事务失败：回滚事务并重新启动旧 API/Worker。
- [ ] 重置成功但新 release 启动失败：停止新服务，删除可能部分 bootstrap 的新 V1状态，切回旧 release，让旧 V2 seed重新 bootstrap 恢复服务。
- [ ] 新 V1 已初始化但线上验证失败：优先修复后重新发布；若必须紧急恢复服务，同样先删除新 V1状态，再切旧 release bootstrap V2，避免 hash/路径错配。
- [ ] 前端已切换时恢复旧 symlink，`nginx -t` 后 reload。
- [ ] 不执行 `down -v`，不删除其他资源、audit events、旧 release 或整个共享 volume。

## `task.py start` 前门禁

- [x] `prd.md`、`design.md`、`implement.md` 已按“重置为新 V1”修订并通过用户评审。
- [x] `implement.jsonl`、`check.jsonl` 已使用真实 Spec/Research 条目。
- [x] 用户在后续消息中明确批准开始实施；该批准不自动等同于 commit 或 push 授权。
