# RND-502 收口与提交范围

2026-10-23：用户已接受实现、独立复审修复与验证证据，并接受已列明未验证边界；明确授权仅本任务提交、manifest done 与当前子任务归档，不 push。此前各文档的 review/不提交限制为历史阶段记录，本次授权替代该阶段限制，不修改批准 v2 三件套。

## 三笔提交

1. feat(renderer): unify formula OMML and audited fallback (RND-502)
   下列业务、测试、Spec/设计文件，以及当前子任务的全部非忽略规划/审查/验证记录；manifest 仅选取 RND-502 条目，保留其余 HEAD 条目，其他任务工作区改动不入提交。
2. chore(task): archive RND-502 formula OMML fallback
   当前子任务的迁移、completed 元数据和 context 自引用；manifest 仅 RND-502 到 done 及准确归档路径。
3. chore: record RND-502 journal
   journal/index 仅本次新增会话；既有未提交 CON-102 会话、302 项暂存删除、其他任务与用户文件保持原状态。

## 实现、测试与文档文件

- app/conversion/docx_rules/formula.py
- app/conversion/docx_rules/mineru_content.py
- app/conversion/docx_rules/table_expansion.py
- app/domains/document_jobs/execution.py
- app/domains/document_jobs/result_state.py
- app/domains/translation/document_ir_translator.py
- app/services/renderer/docx_quality.py
- app/services/renderer/evidence.py
- app/services/renderer/image_renderer.py
- app/services/renderer/table_renderer.py
- app/services/renderer/text_renderer.py
- app/services/renderer/word_renderer.py
- scripts/dev/formal_mineru_conversion.py
- tests/test_formula_rendering.py
- tests/test_formula_translation_boundary.py
- tests/test_document_ir_mineru_converter_layout.py
- tests/test_document_ir_word_renderer_layout.py
- tests/test_document_job_delivery_state.py
- tests/test_document_job_execution_stages.py
- tests/test_document_job_result_persistence.py
- tests/test_fastapi_jobs_backend.py
- tests/test_translation_batch_failure_semantics.py
- tests/test_translation_integrity_execution.py
- .trellis/spec/backend/word-generation-rules.md
- .trellis/spec/backend/translation-integrity-validator.md
- docs/design/docx-rendering-template-design.md

## 核验与证据

当前 13 个业务文件与已验收快照 15eeffed1bfcc1fdbe1dcd771dcfb1acc27fb8c0d13fe200e5c953f9e7932a7f 一致。311 定向、202 release/OpenAPI current、组件 1/1、direct 矩阵 5/5 及独立复验的日志已核实；本次只改收口记录、路径及下述单个末尾空行，无业务语义变更，复用这些证据，不重复整套门禁。

最终 diff / task validate / HEAD 和受保护文件指纹在提交前后再次检查。真 Word 视觉、线上 Golden、真实 InnoDB/S3/部署文件系统仍未验证；用户接受不等于这些外部门禁通过。部署/回退仍按已记兼容执行器/排空在途约束，不删除产物、报告或审计。

Git 使用独立 index 构造精确候选，再仅同步本任务 index 条目；archive/add_session 使用 --no-commit，避免现有脚本整批纳入无关暂存项或 archive 子树。无关改动不 stash、不删除、不回退。收口前完整保护快照保存在本地临时目录 rnd502-finalization-dsnnctyk。

## 新文件纳入后的候选检查

独立 index 首次把未跟踪源纳入 cached diff --check，检出 formula.py 多余 EOF 空行；checker 仅删除一个末尾 LF。主会话以旧候选 blob == 新文件 + 单个 LF、AST 完全相同核实。36 项公式测试重新通过（0.726s），日志 tests/tmp/rnd502/closeout-formula-tests.log；既有 311/202/样本门继续作为相同业务语义证据。最终源快照 0c2264f7aade7cb6b9eecf135724cb45507750a5d727fcdb1615d8ecbf00c045，详情 tests/tmp/rnd502/closeout-code-snapshot.json；已接受原快照仍保留，不混淆两个字节版本。

## 工作提交与归档结果

工作提交：136802cb273c85e94ff65d41aca5aa15c8c70459。task.py archive --no-commit 仅迁移当前子任务至 .trellis/tasks/archive/2026-10/10-23-rnd-502-formula-omml-fallback，status=completed、completedAt=2026-10-23；manifest 仅 RND-502=done。当前任务 runtime 指针由 archive 清理，不启动后续任务。implement/check 自引用迁移至归档路径，批准 v2 三件套原字节保持。

归档候选使用精确 source/destination/本任务 manifest 条目，独立 bookkeeping 提交；302 项原暂存删除、父任务、其他 task 目录、CON-104/backlog/.serena 及既有 journal 改动保持。会话提交只包含本次新增会话，不纳入先前 CON-102 未提交日志。
