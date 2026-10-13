# BAS-001 规划调查：当前能力与证据边界

日期：2026-10-12（America/Los_Angeles）。HEAD：`fcea60ff8c131edff7fd5ba360e1bf4e37ec4227`；分支 `md2word/BAS-001`。
本文件是静态调查记录，不是已执行的测试基线报告。本会话没有运行业务测试、启动服务、访问生产、调用 MinerU/LLM 或生成 DOCX。

## 依赖、任务与工作区

- `pwd` 返回 `/Users/sc/PycharmProjects/md2word`；`git status --short` 初始只有 ` M .gitignore`。
- 初始 `.gitignore` SHA-256：`b0719d64dea7293460521fa0fb9b575bb3440abcdc4d567ec465adc95a39dc89`，不属本任务。
- DOC-001 manifest 为 done；`.trellis/tasks/archive/2026-10/10-12-doc-001-documentation-package-index/task.json` 为 completed，meta.human_acceptance 已接受实现、验证和风险。其 validation.md 提供归档复验结果。
- BAS-001 初始 todo/path=null；遍历当前与归档 task.json 未发现同 slug 子任务；已存在父任务 `10-12-datasheet-docx-delivery-quality` 为 planning。使用 create --parent --no-start 新建一次；不激活会话。
- `docs/implementation/baseline-verification-*.md` 无匹配；当前六项核验报告与当前 HEAD 运行结果并未由旧任务完整交付，不建议 BAS-001 skipped_existing。

## 调查范围与来源层级

已读根 AGENTS、workflow、backend/frontend/guides indexes，backend quality/database 及 Word 规则相关段；已读用户指定的十份产品/冻结范围/实施/执行/backlog/manifest/ADR/gap/testing/security 文档，以及父任务三份规划和 DOC-001 验收记录。
搜索覆盖 `app/**`、`frontend/src/**`、`tests/**`、`scripts/**`、`docs/api/**`、`docs/dev/**`、`.trellis/tasks/**`；检索 WordPreview/word_preview、PublicationRecord/publication、docx→pdf/soffice、CrossPageParagraph/source_spans、reference_asset、migration/Alembic/ALTER TABLE，再读命中的 owner 和不同语义的调用入口。以下路径均相对仓库根，行号是上述 HEAD 的辅助定位，符号为稳定索引。
未读取私有 `.env` 或运行数据内容；本机只确认 `.venv/bin/python`、`frontend/node_modules` 存在，不据此宣称运行依赖已验证。

## 六项事实矩阵

### 1. Word Preview：开发工具已有，产品合同缺失

- `docs/dev/local-conversion-sandbox.md:171` 说明 DOCX→soffice→PDF→pdf2image/Poppler→PNG；历史 `archive/2026-08/08-18-fix-formal-word-structural-regressions/research/cm4112-validation.md` 有 LibreOffice/WPS 有界人工结果。
- `app/domains/document_jobs/models.py:87` 的 DocumentJobRecord 没有 preview 结果字段；`schemas.py:14` 的 action 只有 download/retry/cancel/archive/unarchive/clone/delete。
- `docs/api/openapi.json` 的 document-jobs 路由只有创建/查询/事件/文件/下载/translation-qa/生命周期等，没有 Word preview 路由；`router.py:519` 是 delete-preview，`recovery.py:155` 是 replay preview。
- `frontend/src/api/documentJobs.ts` 对应现有 API；`frontend/src/pages/JobDetailPage.vue` 的 preview 命中是诊断摘要/删除确认，不是 DOCX 页面预览。
- 结论：没有查到正式 WordPreviewProvider、任务级预览 Artifact/重试/API；本地工具不能满足 RND-504。无需重复建设基础视觉工具，也不能 SKIPPED_EXISTING 整项。

### 2. Publication：资源发布已有，文档成品发布缺失

- `app/domains/document_jobs/models.py:112` 的 retry_count 与 `:126` 起 translation_qa 字段存在，独立 quality/review/delivery、PublicationRecord 不存在于该模型。
- `app/domains/document_jobs/service.py:415` 的 build_available_actions 不含 publish；`:434` get_translation_qa 对 direct 返回 unsupported_mode；`:512` update_translation_qa 对 direct 抛 409/conflict。
- `service.py:564` / `:1547` 下载校验 owner/job/result/文件状态及到期，translation_qa 不是这里的下载阻断条件；这不等于已实现 quality blocked 的下载分类。
- `schemas.py`、`router.py`、OpenAPI、前端 client/type 的公开合同交叉确认没有 publish/publications。命中的 published 主要是模板/术语/配置资源；现有方法名中 IR/Word publication 也可指产物登记，不能冒充 Admin 交付发布。
- `tests/test_fastapi_jobs_backend.py:10159` 验证翻译 QA；`:10246` 明确验证 direct QA 不可用；`:10481` 验证临时结果下载。
- 结论：QA-601/QA-605 等仍有实质目标；保留已有 QA、授权下载和资源快照基础。不可把资源 seed 不可变性当成文档发布不可变保障。

### 3. Caption/footnote：IR 已有，annotation 数组未翻译

- `app/services/document_ir/models.py:76` 定义 captions/footnotes；converter `:149` 提取并在 `:215` 附近写入块。
- `app/domains/translation/document_ir_translator.py:435` extract_translation_items 只调用 `_append_block_text`、`_append_list_items`、`_append_table_text_nodes`；`:530` apply_replacements 只更新 text/list_items/html。
- `tests/test_document_ir_translation.py:192` 的结构保真测试在 `:217` / `:218` 明确断言翻译前后 captions/footnotes 相等；这是当前合同证据，不能为符合目标在 BAS-001 改掉断言。
- 细节：converter `:339` 的 `_text_for_block` 可将首条 caption 复制为 table/image 的 text，故该副本可能进入翻译；`:181` 附近 table_context 辅助段落也能翻译。这些都不证明 annotation 数组已覆盖。
- 结论：TR-401 要补显式 annotation 单元和回填；复用现有字段、稳定 ID、批次和 Provider，不重写翻译系统。

### 4. 跨页段落：自然分页不等于语义合并

- converter `:119` 的预处理是题注重关联和 `merge_table_placeholder_continuations`，`:131` 起逐 raw block 创建 IR；没有跨页 paragraph merger。
- `app/services/document_ir/layout_signals.py:153` 只合并真实表后的空表 placeholder，并累积 continuation_heights。
- `app/services/document_ir/models.py:47` 的 layout 有 page_index/bbox/source_index/continuation_heights，无 source_spans 合同。
- `app/services/renderer/word_renderer.py:344` 每个 paragraph block 新建 Word paragraph；`.trellis/spec/backend/word-generation-rules.md` FLOW-001/003 描述自然分页和表续页，不宣称跨页断句已合并。
- 结论：IR-203 仍缺；后续最小探针应输入两页续接段落，报告块/段落数和来源保留，不用“Word 自然跨页”替代判断。

### 5. Table reference asset：普通图片资产基础可复用

- converter `:160` 起只有 `block_type == "image"` 才 resolve path、构造 MinerUImageAsset 与 DocumentIRAsset。chart/figure 归为 image 的已有路径可注册。
- converter `:324` `_metadata_from_raw` 只显式保留 source_type/bbox/page/text_level 等；table reference path 没有独立 IR 引用。
- `app/domains/document_jobs/execution.py:801` 起消费 result.image_assets，登记 file/hash，并回填 IR asset；`:828` 生成 image archive。这条链是可复用基础，但 table 不进入。
- `DocumentIRAsset` 有 file_id、object_key、mime_type、checksum_sha256；kind 当前只有 image。不需要为调查新增实体。
- `tests/test_document_ir_mineru_converter_layout.py:595` 及空表 nested 正反例证明的是 placeholder 处理，非 reference asset。没有表格 reference warning/授权展示的当前完整证据。
- 结论：IR-206 仍有缺口；参考图不得默认替代正常 HTML 表格。完整 MinerU raw ZIP 保留资源不等于注册成一等 QA asset。

### 6. DB migration：bootstrap/maintenance 已有，版本化迁移未建立

- `app/core/config.py:31` jobs_repository_backend 默认为 file；database 对应 sqlite，mysql 对应 MySQL；factory.py:240/244 分派。这是代码默认，不是生产观测。
- `app/infrastructure/persistence/mysql/backend.py:49` 初始化可执行 schema；`mysql/schema.py:503` 依次执行建表、maintenance、列补齐、post-column、删除旧索引、补索引。
- `mysql/schema.py:521` 使用 INFORMATION_SCHEMA 判断列后 ALTER；索引也查询后维护。因此不是“只有 CREATE TABLE”，也不能保证并发初始化无竞争或迁移可逆。
- `sqlite/schema.py:233` 是 CREATE TABLE/INDEX IF NOT EXISTS 语句循环。
- `tests/test_database_job_repository.py:1540` 使用 fake MySQL 模拟缺列，验证补齐与 SQL 形状；未证明真实 MySQL DDL 回滚。
- `.trellis/spec/backend/database-guidelines.md` 与 `docs/dev/backend-local-setup-and-architecture.md` 明确未建 Alembic/versioned migration。全仓受控文件搜索无对应目录；`scripts/ops/shadow_copy_metadata_to_database.py` / `shadow_copy_metadata_to_mysql.py` 是 metadata 后端搬迁；`scripts/dev/migrate_md2word_main_sandbox.py` 是开发沙盒迁移。
- 结论：CON-103/QA-605 应提前设计迁移与兼容验收，REL-703 负责上线演练，不能把新增状态假设为已有迁移基础。BAS-001 不选迁移框架，不运行真实 schema。

## 其他已核验基础

- `app/domains/translation/modes.py:47` 起有 direct 和四方向；normalize_translation_mode 保留 zh2zh/zh_to_zh→direct；direct 的 profile/prompt/term set 均为空。
- `execution.py:836` 仅 translation mode 进入 source IR/batches；direct 路径设置 applied=false 后进入 rendering。配置快照是否完整隔离翻译资源需结合既有测试执行证据，不仅凭模式表宣布全过程零 AI 已验证。
- `DocumentJobRecord.result_file_id` 单值，是一主 DOCX 模型基础；多个内部 artifacts 不构成多主输出。
- `frontend/src/components/JobActions.vue` 使用 format helper；`frontend/src/api/types.ts:1508` 有后端 available_actions；发布动作尚未定义，不能宣称已完成发布 UI 权威状态消费。
- Word Spec MATH-002/003 已有共享 OMML 和显式失败残留；RND-502 应复用。COL-003 已有严格配对图片制表位方案，backlog RND-503 的布局表格是待对齐的目标建议，不在本任务替换。
- 空 HTML 现有 source integrity 会 fail-closed；目标要求内部 blocked 草稿，属于后续 TAB-306/CON-103 的差距，不能在基线阶段弱化当前内容保护。

## 测试/脚本盘点与历史结果

| 类别 | 当前入口/覆盖 | 结果等级 |
|---|---|---|
| Release | `scripts/ops/check_release.py:24` 默认目标；`:81` 聚合 OpenAPI、frontend types/mock 和 unittest；有 runtime/preflight 可选参数 | 当前未运行。2026-08-20 归档任务 implement.md:63 记录 202 项通过，适用其修复版本，不适用当前 HEAD。 |
| Golden | `scripts/ops/run_golden_sample_regression.py:86` 支持 preflight/完整运行/manual signoff；manifest 为 gs-003/004/006/008 四个 OPA228 PDF | 当前未运行。2026-06-29 release 20d496e，4/4 成功，Admin signoff 后 release-ready；有已接受的质量 flags。 |
| Component | `scripts/dev/run_component_pdf_regression.py:60` 支持 sample-id/output-dir；唯一 committed 最小 fixture 为 ti-opamp-opa228-p1-smoke | 当前未运行；`:135` 起结果依赖 succeeded/openable，不能证明 manifest 所列全部焦点。 |
| Translation | `tests/test_document_ir_translation.py` fake Provider；`run_p1_translation_regression.py:103` 是 en2zh runner；manifest 三样本 P1/P2/P7 | 当前未运行。2026-06-29 20d496e 为 3/3 与人工签字，保留 truncation_not_observed warning，不覆盖其他语言。 |
| Local matrix | `run_local_mineru_quality_matrix.py:49` 起只支持 direct/en2zh/ru2zh；sample sets 为 phase2-core、ru2zh-acceptance | 当前未运行；目标测试文档中的 translation-core 属于未来建议，不是现有 CLI。无必要默认跑完整矩阵。 |
| Frontend | `frontend/package.json` 的 test:unit/build/test:smoke；Playwright 启 Vite 3010、Chrome、失败 trace | 当前未运行；本次只确认命令与现有测试文件，不声称旧日志足以证明当前通过。 |

历史结果源：

- `.trellis/tasks/archive/2026-06/06-29-p0-golden-sample-release-evidence-closure/acceptance-audit.md`
- `.trellis/tasks/archive/2026-06/06-29-p1-translation-beta-formal-sample-gate/formal-sample-gate-audit.md`
- `.trellis/tasks/archive/2026-08/08-20-fix-mineru-table-placeholder-regression/implement.md` 与 `research/root-cause.md`
- `.trellis/tasks/archive/2026-08/08-18-codify-word-generation-rules/implement.md` 为规则文档核验，不能冒充一次新的业务测试执行。

Golden/P1 preflight 会访问认证/runtime；完整 runner 有外部写入。P1 config 默认 debug_full_text=true，不能为核验擅自触发。在线/Word 当前证据缺口须报告，不补造。

## Backlog 初步建议（未写回其他任务）

| ID | 建议 | 理由/剩余验收 |
|---|---|---|
| BAS-001 | 不建议整项 skipped_existing；验证并交付基线报告 | 报告缺失、当前测试结果尚未运行，旧记录覆盖不同版本。 |
| CON-101 | 缩小到文案/资源显隐/现有模式核验 | 五模式、四 Prompt、legacy alias 已有；仍需核对全部 UI/文档剩余措辞。 |
| IR-201 | 复用 package/integrity，仅补目标 warnings/blockers 与资源验证 | 路径/完整性基础已有，不能重建解析链。 |
| IR-203、IR-206、TR-401 | 保留功能任务 | 分别缺跨页段落语义合并、表格 QA asset、annotation 数组翻译。 |
| RND-504、QA-605 | 保留功能任务 | 开发预览工具/资源发布不能满足任务级 preview/成品发布。 |
| RND-502、IR-204、RND-503 | 先验证已有子能力，再限定增量 | 共享 OMML、严格题注重关联、并排图片已有；剩余质量/绑定/目标差异不支持整项跳过。 |
| TR-401→IR-204 | 评估硬依赖是否必要，暂不改 DAG | annotation 字段已存在；新绑定策略可作为后续集成前提，需 TR-401/IR-204 评审决定。 |
| CON-103、QA-605、REL-703 | 前移迁移设计审查，不等待上线才建立策略 | 没有版本化迁移；首次数据变更任务需承担兼容/up/down 或不可逆说明。 |

目前没有证据充分的整任务 SKIPPED_EXISTING 候选；只建议复用已完成子能力。实施阶段若发现整项已满足，报告逐验收证据并建议人工接受 skipped_existing，不自动更新状态。
