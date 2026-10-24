# G0 统一依赖集成候选

2026-10-24。本子代理完成 G0-A/B 和 G0-C 的候选实现及定向证据。收口时主会话已通知：独立 critical 最终审查通过、主会话接受 G0 门，并将组合基线冻结到 `tests/tmp/rnd505-g0-b0` 后执行 task start。本文的 G0 通过结论来自该独立审查及主会话准入，不由实现者自行代签。本子代理未实现 RND-505 的通用 block marker、独立锚点证明或 page_mapping，未提交、暂存或推送。

## 1. 授权位置与来源

- 唯一可写仓库：`/Users/sc/.codex/worktrees/rnd505-page-mapping/md2word`；分支 `codex/rnd505-v2-implementation`。
- 起点 RND-504：`8fa11d9779ce05e9cba1cfb7afee34ecbd58a4cf`，已含 RND-502/503、TR-406、CON-103/104。
- RND-501 已验收工作提交：`69906a5e1e4b676a3e775fa50a94cef0ebc799c9`；三方共同祖先 `c56e12832ff30212cc067d0909430cf5f091f79b`。
- 使用 git show / merge-file 生成逐文件融合候选，手工处理冲突；未整包历史覆盖、未 cherry-pick、未切换原有 `md2word/RND-505`。其 `bfa81cba` 仅只读查看提交/文件列表，没有复用其业务实现。
- 入场已有的父任务 task.json、codex-task-manifest.yaml、当前任务目录和 `.venv` symlink 作为基线保留；随后主会话添加的 `mineru_result` 只读样本 symlink 保留。没有写原根目录。原根/index保护证据由主会话独立检查。
- 精确路径、base/source/candidate SHA、31 个未共同修改的 RND-504 路径及组合指纹见 `g0-source-fingerprints.json`；31 路径均与 8fa11d97 相同。Git index 无暂存变更。

## 2. 实际融合与冲突裁决

1. **同次结果**：RND-501 的 plan/block_evidence/不可变内部 ownership 与原 RND-502 formula_report、RND-503 image_layout_report 同时返回。Worker 和正式 local adapter 只渲染一次并认证同次报告。receipt 选件后不补写主件、报告或 trace。
2. **真实图片所有权**：保持当前 RND-503 1×N 布局表、每图独立 cell、全部注释及普通 native_columns。把当前源序/分栏调度移入 RenderPlan 后由 writer 消费；成组 block operation 持全部成员。旧 paired-tabs 私有范围适配为逐图 writer 捕获的 drawing/fallback 与各 annotation paragraph 真实引用，最终 freeze 为内部不可变 `_ImageOwnership`；不从待验 trace 构造 ownership。完整 caption paragraph 覆盖其 OMML，不能用别图/父段落/共享表或总数代替归属。
3. **内容与表格**：保留 RND-502 公式位置/出现次数/预期输出认证及原大表展开；计划与 writer 共用实际原 HTML 解析和 requires_table_expansion，不恢复旧的 HTML 预替换以免公式被二次加工。IR-205 来源账本附加到现有 IR-204 reconciler 之后，不恢复旧图片题注重关联器；TAB-301 模型是来源提交的必要依赖，未接入新表格业务。
4. **执行/恢复/安全**：保留 RND-504 preview 的 receipt→claim→registration→finish CAS 和所有原下载/质量/发布边界。新 trace 随主件私有 metadata 保存，事件/失败载体/files 摘要由共享白名单投影，保留受控公式/图片计数和 hash。TR-406 的翻译事件由其原 owner 管理。三恢复入口仍从原 IR/字节重验已有公式/图片报告，历史原 aggregate 全23键及 IR-201/204 可选摘要兼容不放宽。
5. **旧测试夹具**：复用 RND-501 已接受的真实双模板竞争夹具，避免冻结后改 ZIP。历史 aggregate 测试使用无 md2w_img_ 的真实旧形状；不能删新件报告后要求放行。IR-201 缺失/None 的历史夹具同时移除依赖该 checksum 的 IR-205 ledger；typed ledger 的 checksum 拒绝保持。安全事件夹具保持原可重算质量证据合法，敌对自由 flag/正文/伪计数在独立投影负例核对。
6. **非有限历史几何（主会话明确批准）**：有限 IR 哈希逐字保持原 canonical JSON；只有历史 IR 含 NaN/+Inf/-Inf 时，用 `document-ir-nonfinite/v1` 加整树节点类型的无损表示计算身份。检测从 Pydantic python 值读取，避免 Any 字段 JSON 序列化先变 null；strict serializer 的 allow_nan=false 保持。plan/provenance 坐标复用 RND-503 null 投影，原 IR 不改写，typed IR-205 和 MinerU 几何门仍严格有限。新增测试覆盖 finite hash 回归、三非有限值区分、null/字符串/list/dict 不碰撞及 IR 不变。
7. **Spec**：RND-501 与当前 RND-503 都占用旧 IR-005 文档编号；保留当前严格题注 IR-005，逻辑表来源账本使用 IR-006 并修正引用。正式合同改为当前组合边界，去除排除 RND-504/c56e128/仅19路径的现行误述；没有提前写入 RND-505 新实现合同。

## 3. 内容守恒证据

`g0-caption-parity.json` 使用 git archive 得到只读 8fa11d97 app 快照，对双重转义 HTML 左/右题注、实际内嵌 tab 左/右题注、混合 OMML 共5例比较所有 word/*.xml 的规范化 hash；五例全部相同。双重转义 &amp;#9; 的既有输出是 literal '&#9;'，实际 tab 每例保留1个；不能把旧 paired-tabs 的同段歧义夹具直接套到当前独立 cell。三图/全部注释、每图 OMML、漏目标、交换注释/全部owner、伪元素种类、冒认图片父段落及缺内部事实均有真实 OOXML/负例。空公式仍沿 RND-502 的空源拒绝，未因旧 RND-501 空对象夹具降低门禁。

## 4. 本轮验证

使用工作树 `.venv/bin/python`（链接至原根共享环境），没有安装依赖或启动服务。test subprocess/临时 file/SQLite/fake MySQL 仍是离线合同证据。

| 最终检查 | 结果 | 证据 |
|---|---|---|
| T0 计划/block evidence/preview provider/application/persistence | 81项，OK | g0-final-t0-preview.log |
| T0 公式/图片/layout/result/execution/delivery | 177项，2次既有failure，0error | g0-final-t0-renderer-execution.log |
| IR-205/TAB-301/IR converter/translation/503三入口兼容 | 87项，OK | g0-final-ir-dependencies.log |
| TR/CON modes/download/delivery API/object identity/retention/translation integrity | 58项，3次既有API failure，0error | g0-final-tr-con.log |
| release（主会话） | 203项，OK；OpenAPI current/changed=false | g0-release.log |
| component（主会话） | 1/1成功 | g0-component.log；tests/tmp/rnd505-g0-component |
| direct phase2-core（主会话） | 5/5成功，P0=0；phase3_entry_ready=false | g0-direct.log；tests/tmp/rnd505-g0-direct |
| 静态 | 26个触及Python AST可解析；git diff --check通过；无配置的lint/typecheck入口 | 本轮实际检查，未冒称类型检查 |

四个最终定向组共执行403个unittest条目，5次failure发生于既有断言，0error；不将带失败组称为全绿。逐命令/耗时见 g0-final-tests.json。首轮与修复中间日志保留用于归因，不代替最终结果。

### 既有失败精确归因

- `test_automatic_word_discovery_requires_current_generation_and_final_ir` 与 `test_explicit_result_reuses_old_generation_but_checks_file_identity (invalid=None)`：原夹具新图片 marker 缺报告，原件认证拒绝。8fa11d97 本轮 baseline 171组先复现，最终逐selector/归一化AssertionError完全一致。
- delivery API 的 operator_approval（file、database）及 qa_scope 共3次失败：旧 `_assert_defaults` 要 quality_summary={}，已有 RND-502 formula 摘要非空。提取已验收 RND-504 保留的原 HEAD 对照日志，最终逐selector/AssertionError完全一致；该 API 基线没有在本轮重新执行。
- 8fa11d97 baseline 第3项 zero_translation_units 原来用空 content_list，触发 mineru_content_empty。69906a5e 已接受夹具改为非空但无可翻译单元的公式输入，原成功语义得以被正确检验；新增独立空输入失败测试继续保护原拒绝，不计为放松输入门或业务修复。
- 机器可核对结果见 g0-failure-comparison.json，未归因新增失败为空。原baseline日志 g0-baseline-preview.log（63 OK）、g0-baseline-renderer_execution.log（171项3failure）均保留。

## 5. 交接与未验边界

已交付未提交 G0 候选，主会话完成独立审查和准入，开始后续 RND-505 分工。本子代理停止业务/测试/Spec 编辑；既有 g0-source-fingerprints.json 保留为冻结的 G0 指纹，不因后续 RND-505 写入重新计算或覆盖。35个实际改动路径如下；父任务登记和manifest是已有并发改动，不列为本子任务实现。当前组合指纹：`da8c9a76d1043fcfea6ecadb83f0a496394beddbb4cbf21bc9e48e1abf556a64`。

- `.trellis/spec/backend/directory-structure.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/render-plan-evidence-contract.md`
- `.trellis/spec/backend/word-generation-rules.md`
- `app/conversion/docx_rules/mineru_content.py`
- `app/domains/document_jobs/execution.py`
- `app/domains/document_jobs/router.py`
- `app/services/document_ir/logical_table_group.py`
- `app/services/document_ir/mineru_converter.py`
- `app/services/document_ir/models.py`
- `app/services/renderer/block_evidence.py`
- `app/services/renderer/evidence.py`
- `app/services/renderer/image_renderer.py`
- `app/services/renderer/render_plan.py`
- `app/services/renderer/table_renderer.py`
- `app/services/renderer/text_renderer.py`
- `app/services/renderer/word_renderer.py`
- `app/services/tables/__init__.py`
- `app/services/tables/models.py`
- `docs/api/document-jobs.md`
- `docs/contracts/document-ir-contract.md`
- `docs/contracts/mineru-artifact-contract.md`
- `docs/design/docx-rendering-template-design.md`
- `docs/design/table-processing-design.md`
- `scripts/dev/formal_mineru_conversion.py`
- `tests/test_canonical_table_grid.py`
- `tests/test_canonical_table_grid_compatibility.py`
- `tests/test_document_ir_logical_table_group.py`
- `tests/test_document_ir_translation.py`
- `tests/test_document_job_execution_stages.py`
- `tests/test_document_job_result_persistence.py`
- `tests/test_fastapi_jobs_backend.py`
- `tests/test_renderer_block_evidence.py`
- `tests/test_renderer_render_plan.py`
- `tests/test_rnd503_dependency_integration.py`

Python 注释、docstring 和开发者可见新文本已按触及范围使用中文；保留机器字段、协议值和测试契约字面量。无新依赖、SQL/DDL、环境开关、API路由、OpenAPI快照或前端业务变更。

真实 Word/WPS、部署预览引擎/字体/批准隔离、真实 InnoDB/部署FS/S3并发和线上 Golden 未在本子任务运行，OOXML/fake不代签这些证据；生产 preview disabled/production_ready=false 保持。direct仍有原 P1/P2 backlog，未声称视觉或第三阶段就绪。临时三方合并副本与只读原app快照已按精确任务路径清理，持久来源由Git、fingerprint、parity和日志保留；共享 `.venv` 与主会话样本 symlink 保留供后续使用。
