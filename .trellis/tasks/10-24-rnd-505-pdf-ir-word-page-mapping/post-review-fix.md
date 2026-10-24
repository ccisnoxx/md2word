# RND-505：独立复审后的 TOC 归属认证修复

日期：2026-10-24。仅修改隔离工作树 `/Users/sc/.codex/worktrees/rnd505-page-mapping/md2word`；本轮不 start、不提交、不 push、不归档，保留既有和并行变更，停在 review 供原独立 reviewer 复验。

## 已确认的问题及前红证据

1. **P2：记录级代表可被篡改。** 实际 renderer 输出 TOC 代表 `first`、归并记录 `merged` 和独立正文 `tail`。仅把持久 trace 的 `merged.representative_block_id` 改为 `tail`，原认证仍成功，mapper 跟随被篡改代表而取得 `tail` 的实际书签和估计末页。逐 item 的 `toc_representative` target 原已与 policy 和实际 owner 对账，但记录级字段没有同样约束。
2. **相邻状态缺口。** 仅把 `merged.disposition` 从 `coalesced` 改为 `rendered` 并同步 counts，或把含独立正文的 `mixed` 从 `rendered` 改为 `coalesced` 并同步 counts，原持久认证仍成功。前者丢失本应存在的归并定位，后者把独立正文位置转向 TOC 代表。

`post-review-reproduction.log` 保留首项修复前的六个预期失败：归并记录换合法外来/缺失/未知代表、混合列表换代表/移除代表、没有归并策略的记录凭空携带代表。该日志包含合成测试对象的失败 repr，不含客户数据。

`post-review-disposition-reproduction.log` 保留第二项修复前的三个预期失败：两种相反的 disposition/counters 篡改在持久认证中仍被接受，以及应用端坏 trace 仍输出非 unavailable 映射。此前完成的代表字段校验在此轮前红测试中继续通过。

## 最小修复及 owner

仅在 `app/services/renderer/evidence.py::_validate_render_evidence` 增加七行共享认证逻辑：

- 全部 record 的 `representative_block_id` 必须等于该 decision 按 item 顺序最后一项 coalesced policy 的代表；没有归并策略时必须为空。这与真实 `word_renderer._render_block → collector.representatives → RenderCollector.freeze` 的赋值顺序一致。混合 rendered list 可以合法携带代表，首个 TOC 与后续归并 item 同处一个列表时也可以合法指向自身。
- 在 `native_text` 已完成自有 target 和 TOC target/item 对账后，非空 policies 中有真实非 coalesced 输出时 disposition 必须为 `rendered`；全部策略归并时必须为 `coalesced`。空 policies 沿原空 list/not_emitted 校验，不新增默认推断。

现有逐 TOC target 的 policy→真实 representative owner 校验继续执行。因此记录字段、策略和实际 target 关系形成同一认证链。纯 mapper 不增加重复校验，不构造或放宽 runtime ownership；图表、装饰、空内容及 v1 bookmark/targets/报告规则继续由原分支认证。

新件同次认证发现不匹配仍以原 `ir_render_evidence:target_mismatch` 失败；持久可选 trace 由既有 wrapper 返回不可用，应用只得到 unavailable/legacy_evidence_missing 映射。没有新增历史主件恢复、预览或发布失败门。

## 新增有意义的回归

- `tests/test_preview_page_mapping.py`：实际 renderer→持久认证→映射链；六种代表篡改、两个相反的状态/counters 篡改必须拒绝；同次严格认证也拒绝。正常混合列表保有独立 page 2 与自己的书签，归并记录仍指向 TOC page 0；另验证混合列表自代表合法。
- `tests/test_document_job_word_preview.py::DocumentJobPageMappingTests`：真实 renderer/receipt/五页预览中，正常、代表篡改、状态/counters 篡改三组对照。坏 trace 仅映射不可用；主 DOCX 字节/hash、原独立证明、预览成功、blocked/unreviewed/internal_draft、available actions 和内部下载保持。
- `tests/test_document_job_result_persistence.py::DocumentJobBlockAnchorRecoveryTests`：file/SQLite × legacy/explicit/receipt 六个真实恢复组合保留坏代表 trace 和原证明，不重新渲染、不更换主件；成功/pending/unreviewed/internal_draft 与下载保持，映射来源认证返回 `(None, None, None)`。新增中性 TOC IR fixture 被应用与恢复两组复用。

## 最终验证

最终候选执行：

```bash
.venv/bin/python -m unittest tests.test_renderer_render_plan tests.test_renderer_block_evidence tests.test_renderer_block_anchors tests.test_preview_page_mapping tests.test_document_job_word_preview.DocumentJobPageMappingTests tests.test_document_job_result_persistence.DocumentJobBlockAnchorRecoveryTests
```

**56 项通过，21.741s**，原始输出见 `post-review-targeted.log`。此为补齐 disposition 修复后的最终复验，覆盖正常 TOC/混合列表、v1 现有断言及新增负例。此前代表修复阶段的两项应用/恢复定向通过见 `post-review-application.log`，不与最终 56 项重复相加。

- 四个修改的 Python 文件 AST 语法检查通过；源码 SHA-256 与工具探测见 `post-review-source-check.json`。
- `git diff --check` 对三个已跟踪修改文件通过；新增 mapper 测试也已通过语法与真实执行验证。
- Lint / TypeCheck：N/A。仓库没有相应配置，现有 venv 未安装 ruff、flake8、mypy、pyright；未安装依赖，不将 AST 冒充 lint/类型检查。
- B1 重建及组合回归由主会话执行；本轮未重跑全 339 项、component/direct、release、真实 Word 或部署环境检查，不据此升级这些证据。

## 文档与复验状态

现有页映射合同及 Spec 已要求 coalesced 跟随真实代表、混合列表不得隐藏正文、坏可选导航不影响原业务状态。本轮落实这些既有合同，没有新接口或新约定，因此不另改 Spec；此记录补充精确认证规则与证据。

新增非显然的 collector 顺序说明、测试 fixture docstring 和测试失败说明均使用中文；机器字段/固定错误码保持原值。源码及测试已停止编辑，待原独立 reviewer 复验，尚不宣称整体任务人工验收或完成。
