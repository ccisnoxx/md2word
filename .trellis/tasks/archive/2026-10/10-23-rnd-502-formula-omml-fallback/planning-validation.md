# RND-502 规划验证

日期：2026-10-23（Asia/Shanghai）；本文件保留初版 v1 证据，文末追加独立审查后的 v2 验证；HEAD=`c56e12832ff30212cc067d0909430cf5f091f79b`；实际分支=`codex/pre-rnd501-local-wip`。

## 交付和停止位置

- 子任务准确路径：`.trellis/tasks/10-23-rnd-502-formula-omml-fallback`；parent=`10-12-datasheet-docx-delivery-quality`。
- manifest RND-502：todo→planning，实际路径已登记，resolution=null；Trellis status=planning。
- prd/design/implement 三件套、真实调查、必要 Word 合同摘录、implement/check context 齐全；PRD 已做收敛检查，没有 TBD、临时问题清单或未决阻塞项。
- 不建议 skipped_existing：已有子集继续复用，但逐公式降级、边界、保真和结果证据接线有已复现差距。
- `task.py create ... --parent ... --no-start` 只执行一次；没有执行 task.py start，`task.py current --source` 返回 `(none)` / `none`（该只读查询无活动任务时退出 1，属预期）。未切换/创建 Git 分支、未改业务、未提交/push/archive、未记录 journal。

## 依赖证据

BAS-001：manifest=done；HEAD 归档 task.json=status completed，meta.human_acceptance 记录实现、验证、风险接受及提交/归档授权。工作提交 `107624d7e87f8287c83020d9c751e9d54d23d855` 在 HEAD 可达。其工作区归档文件属于初始暂存删除，调查仅用 `git show HEAD:<path>` 读取，没有恢复/覆盖。

## 实际执行的现有基线

```bash
.venv/bin/python -m unittest \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_fraction_omml_in_formula_and_table_cells \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_malformed_fraction_remains_visible_and_is_reported_as_latex_residue \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_extended_omml_in_all_shared_text_paths \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preprocesses_cm4112_formulas_without_tex_residue \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_supports_datasheet_tex_matrix_in_all_math_entries \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_normalizes_formula_text_in_table_cells_and_notes \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_normalizes_manual_quality_record_formula_residue \
  tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_structures_v2_multiline_lists_and_preserves_math_sources \
  tests.test_document_ir_mineru_converter_layout.MinerUToDocumentIRLayoutTests.test_convert_zip_fails_closed_when_declared_formula_payload_is_missing
```

结果：退出 0；9 tests，0.167s，OK。没有重跑更广测试：本轮没有业务实现。

另执行真实 renderer/evidence 的七个内存合成探针，复现 tag、sup_scope、text_spaces、vee、mixed_fraction、table_rich 及 unknown 的现状；详 `research/current-state.md`。首次探针漏填必填 document_language 后由 Pydantic 拒绝；修正输入后得到证据，未放松业务验证。

## Context 和规划门禁

```bash
python3 .trellis/scripts/task.py validate .trellis/tasks/10-23-rnd-502-formula-omml-fallback
```

最终结果：退出 0，All validations passed；implement.jsonl=6 entries，check.jsonl=6 entries，无警告。

首次 validate 虽通过，但发现建议分支尚不存在，以及 Word Spec 81257 bytes 超过 32768 bytes 注入上限。已修正：建议分支移入 meta.suggested_branch，branch=null；将必要 11 条原文规则提取为带源哈希、基线和核对指引的 research/word-formula-contracts.md，context 不再被截断。该摘录不是第二权威真源。第二次 validate 无警告。

context 只含必要 Spec/research，不注入业务源文件或整个仓库。三件套作为任务标准上下文，计划修改路径和测试 selector 已检查：明确新建 formula.py/test_formula_rendering.py，其余计划路径均存在；实施时仍须核对基线漂移。

## 工作区保护和最终检查

- 初始：302 项 staged 删除、5 项 unstaged 修改、1 个聚合未跟踪任务目录；这些未知改动没有 stash、删除、还原、stage 或提交。
- 对初始已有任务/工作日志及已改 docs 建立 SHA-256 快照；最终对比允许差异只有 RND-502 manifest 和父 task.json。父任务移除本次新增 child 后与初始内容哈希一致，状态仍 planning。
- manifest YAML 逐对象比较：只 RND-502 变化，其他 44 项完全一致；不覆盖 manifest 原有其他任务笔记。
- index tree、HEAD、分支与启动快照一致；业务路径 `app/frontend/tests/scripts/resources/docs/api` 无 diff。任务文件位于未跟踪目录，另做 JSON/JSONL 可解析、context 存在/字节限制、空白和占位检查。
- `git diff --check` 通过；最终任务级 context 校验和文档检查通过。
- 新增/更新的规划与研究文档使用中文；没有 Python 业务、注释/docstring、日志或开发者错误文本变更。

## 未运行与风险边界

未运行新实现测试、全量 release、component/matrix、线上 Golden、真实 MySQL、外部翻译、前端构建或 Microsoft Word 人工验收；本轮只有规划和现有基线，不能声称目标已实现或视觉已通过。实现期门禁、不可用样本的记录要求、权限/并发独立复核、回滚点和停止条件均列在 implement.md。

初版规划自查重点：受控原式 warning 不进入致命 blocking flags；pending/blocked 不提升；候选报告跟随选定 receipt；新旧 evidence 分版本核验；输出诊断不泄露公式全文。初版没有业务候选 diff，未派发实现或检查代理，也未进行独立规划复审，不把自查称为独立安全验收。后续按用户新指令的独立 architect 审查记录如下。

本轮停在规划评审门；只有后续人工明确批准本版本后，才能进入实现。

## 2026-10-23 首轮独立审查与 v2 修订验证

- 用户明确授权后派一个全新 architect（`fork_turns=none`）独立只读审查 v1。返回 P1/P2 各 1 项，主会话读取真实代码并用两个独立内存探针确认；完整发现、证据、修订和限制见 planning-review.md。
- P1：真实 translator 抽取 `<eq>\text{High Low}</eq>` 后 formula token=0，fake 改 High→Changed 仍被完整性检查接受。v2 增加共享数学边界的最小 translator 接线、Provider 前保护/拒绝、主动篡改与普通正文对照测试，不改 Codec/Provider 或批次持久格式。
- P2：保持 source/anchor/mode/count，DOCX 的 x=1 改为 x=2 后现有 evidence 相等。v2 增加写入前预期输出投影/哈希与最终实际 XML 比较，补数字/脚本/截断负例，不替代 parser 语义测试。
- 同步澄清 legacy 扫描、明确历史 result_file_id、已有 receipt 三路径；保留旧明确主件跨代复用、错误映射和原子边界；诊断投影覆盖旧 latex_residue_examples；回退必须满足 receipt/报告/在途抽取计划兼容下限。
- 当前 prd/design/implement、task metadata 和最小 context 已同步 v2；被审 v1 三件套原字节保存在 research/reviewed-v1/。审查只适用于 v1，v2 未独立复审，planning_approval.accepted 仍为 false。
- 最终 `task.py validate .trellis/tasks/10-23-rnd-502-formula-omml-fallback`：退出 0，implement/check 各 8 个真实条目，无警告；所有注入文件和三件套均低于 32768 bytes。JSON/JSONL、路径、源 Spec 摘录哈希、版本一致性及 diff 空白检查通过。
- 审查完成、主会话修订前：已存在的 905 个文件哈希、三件套哈希、index tree 保持一致。完整 status 另出现 `.serena/.gitignore` 和 `.serena/project.yml`（目录还有被忽略的 project.local.yml）；代理明确未调用 Serena/创建命令，归属不能确认，主会话保留原样并单独记录哈希，不删除或纳入本任务。
- 最终主会话改动限定于当前任务规划/审查文件和 RND-502 manifest 记录。父任务及其他已有任务/工作日志/文档哈希不变，其他 44 个 manifest 任务对象不变，原暂存树、HEAD、分支不变，业务目录无 diff。未观察到 `.serena` 文件后续变化。
- 不重复初版已通过的 9 项基线；本轮无业务改动，新执行的两个内存探针仅用于确认发现。未运行实现后的测试、release/Golden、真实数据库或 Word 人工验收。
- 不执行 task.py start，不设置活动任务，不提交/push/归档。规划保持 planning，等待用户审核 v2。

## 2026-10-23 第二位全新 architect 对 v2 的独立复审

- 按用户新指令派 `/root/rnd502_v2_fresh_architect_rereview`，architect，fork_turns=none，与上一位独立。完整读取 v2 三件套、相关 Spec、真实代码和测试源码后，执行三组 python -B 内存探针。
- 结论：上轮 P1/P2 均在 v2 规划层闭合，未发现新增确认的 P1/P2/P3；主会话再次读取翻译计划/回填、三类恢复入口和树校验关键代码核实。保留三件套技术内容与 SHA-256，不升 v3；具体证据及边界见 planning-rereview.md。
- 探针核对了旧 P1 的普通/数学节点 index 和主动改值、旧 P2 的相同 anchor/mode/count 等长改值，以及新计划去掉数学目标/变零单元时旧根集合返回 translation_batch_tree_invalid。它们证明现状和既有机制，不证明尚未实现的 v2 已通过。
- 复审完成、主会话补记录前：913 个已有文件哈希、完整 status、index tree 与本轮启动快照一致；既有 .serena 文件未变，未观察到仓库写入。
- 本轮只新增 planning-rereview.md，并同步首轮记录/研究状态/task metadata/RND-502 manifest 记录；implement/check JSONL 仍各 8 项，三件套保持版本 2 原字节。planning_approval.accepted 仍为 false。
- 最终 task.py validate 退出 0，无警告；JSON/JSONL、context 路径/大小、三件套哈希、Word Spec 摘录源哈希、diff 空白及工作区保护检查通过。业务路径无变，其他 44 项 manifest、父任务、原暂存树、HEAD、分支和 .serena 哈希保持。
- 未运行实现后测试、完整 release/Golden、真实 MySQL/S3、外部 Provider/MinerU 或 Word 人工验收；旧基线输入不变，不重复运行。task.py current --source 仍为 none（退出 1 为预期），没有 start/提交/push/归档，继续停在 v2 人工规划评审门。
