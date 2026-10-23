# RND-502 当前实现调查

日期：2026-10-23（Asia/Shanghai）；HEAD=`c56e12832ff30212cc067d0909430cf5f091f79b`；分支=`codex/pre-rnd501-local-wip`。
范围：本地真实源码、已安装类型、现有测试、API/DB JSON 容器、脚本和 Trellis 历史；不访问生产、专有下载目录、真实 Provider、数据库或外部服务，不修改业务代码。

## 1. 依赖、任务和历史

- manifest RND-502 原为 todo，唯一 depends_on 为 BAS-001。BAS-001 为 done，resolution/notes 记录人工验收。因初始工作区有历史任务暂存删除，用只读 `git show HEAD:<path>` 查看 BAS-001 的 `task.json`、`validation.md`，没有恢复文件。
- BAS-001 归档任务为 completed，工作提交 `107624d7e87f8287c83020d9c751e9d54d23d855` 在 HEAD 可达（merge-base --is-ancestor 退出 0）。报告 `docs/implementation/baseline-verification-2026-10-12.md:109` 已明确：共享 OMML 存在但缺完整质量验收，不能整项跳过。
- 父任务 `.trellis/tasks/10-12-datasheet-docx-delivery-quality` 存在，planning。递归检查 task.json 的 id/name 以及文件名未发现 RND-502 子任务；唯一创建命令使用 `--parent` 和 `--no-start`，当前子任务为 `.trellis/tasks/10-23-rnd-502-formula-omml-fallback`。
- 相邻 RND-501 的 prd/design/implement 已读，其最新规划要求在当前 HEAD 集成其他已验收能力，但尚未实施；不是 RND-502 的依赖，当前任务不集成其业务。其文件 owner 与本任务重叠，实施前须协调基线。
- 历史只读 `git show`：`.trellis/tasks/archive/2026-08/08-18-fix-layout-formula-image-caption/prd.md` 的 R2 要求 block/inline/table 共用 OMML、孤立下标保持可见、失败留质量信号；`08-18-fix-mineru-first-page-layout/task.json` 为 completed。相关提交 `674ce93`、`13111fc`、`bb11f02` 已存在于当前 renderer 历史。历史承诺不是当前完整验收证据。

## 2. 已读产品与工程真源

已读取用户指定的 11 份文档：产品 PRD、scope-and-decisions、implementation-plan、codex-task-backlog、codex-execution-guide、完整 codex-task-manifest、architecture-decisions、document-ir-contract、docx-rendering-template-design、quality-review-release-design、testing-acceptance-strategy。

backlog RND-502 完整定义仅为“统一 inline/block/table formula 渲染；无法转换时有明确 flag”；细化依据为渲染设计第 5/6/13/15/16 节、PRD FR-005/006/010/012 和 Word Spec MATH-001/002/003、QUALITY-001/003/004。冻结决策和已接受 ADR 没有要求完整数学引擎、图片降级或 Token 规则修改。

根 AGENTS、Trellis workflow、guides/backend/frontend index 已读。进一步读取 backend directory/error/quality、Word 相关条款与冲突矩阵、database 的结果登记/状态投影章节，并核对 direct 资源合同。此次只写规划，不把目标 Spec 当成现有已实现能力。

## 3. 实现事实与差距

| 事实/差距 | 当前代码锚点 |
|---|---|
| 同一有限 `_OmmlParser` 支持分数、根式、上下标、Greek、overline、boxed、样式；parse 对 ValueError 返回 None，无结构化失败原因 | `app/services/renderer/text_renderer.py:57` |
| 初始化对 dollar/空白做全局处理；tag 分支消费参数后输出空 math run；裸上标参数会连读加减/字母 | 同 parser 的 init / `_parse_command` / `_parse_argument` |
| block 公式先 parse，失败回 `_fill_paragraph`；后者走普通归一化与符号替换 | `app/services/renderer/text_renderer.py:472`、`:633` |
| frac/dfrac/tfrac 出现在混排时整段 parse；否则只用 inline 正则切片；失败片段再次归一化 | `app/services/renderer/text_renderer.py:535` |
| caption 先 prepare 再识别编号，tail 不走统一数学分段 | `app/services/renderer/text_renderer.py:498` |
| table 先对完整 HTML 做 terminology.replace_html，再将 cell HTML 传给 shared paragraph；支持普通 sub/sup，但带 frac 的富文本可把标签送进 math | `app/services/renderer/table_renderer.py:33`、`:207`、`:338` |
| `semantic_text.py` 仅兼容导出，实际纯文本公式归一化在 docx_rules，不是第二解析实现 | `app/services/renderer/semantic_text.py`、`app/conversion/docx_rules/text_semantics.py:140` |
| join_text_fragments 保留 `$...$`；coerce_text_list 对 semantic inline 先 normalize，annotation 因而可能失去边界 | `app/conversion/docx_rules/mineru_content.py:55`、`:98` |
| formula block 仅从明确数学字段取值；当前仅 image block 注册 image asset，formula 无可直接复用的正式图片降级资产 | `app/services/document_ir/mineru_converter.py:160`、`:365` |
| renderer 对外返回 bytes，已有单次 `_RenderContext`；没有公式回执 | `app/services/renderer/word_renderer.py:44`、`:55` |
| analyzer 汇总 w:t/m:t 文本，用 regex 查残留；没有逐公式结果与 expected/actual。质量 flags 与致命 blocking_quality_flags 分离 | `app/services/renderer/docx_quality.py:53`、`:86`、`:265`；`app/services/renderer/evidence.py:42` |
| 在线质量先于候选登记；receipt 锁定 generation/最终 IR/file。历史主件恢复重算 evidence 并逐字段要求相等，新增默认字段会破坏兼容 | `app/domains/document_jobs/execution.py:3045`、`:3243`、`:3359` |
| 三 adapter 都用 patched_job 共用纯规则；只在同 job 序列化点更新，适合锁内合并选定结果的公式摘要 | `app/domains/document_jobs/result_state.py:32`、`:64` 和三 document_jobs adapter |

## 4. API、DB、配置和脚本

- `app/domains/document_jobs/models.py:157` 已有 quality_status/review_status/delivery_status/quality_summary；schemas.py:126 的 quality_summary 为 `dict[str, JsonValue]`，不需新 OpenAPI typed field。
- `delivery_state.py` 已有结果变化/换代失效、published 不可修改和复核 CAS；不得让公式 warning 绕过它。file/sqlite/MySQL 保存 payload 并投影四状态，新增公式 JSON 无 DDL 需要。
- `result_state.prepare_result` 验证 candidate 的 source_integrity/docx_quality/blocking flags；`ensure_renderer_integrity` 仍是致命内容完整性边界。普通受控文本 fallback 不进入此 fatal 列表。
- TemplateConfig/renderer options、requirements 中未发现需要为本任务新增公式引擎或配置的依据。现有 terminology 是符号/上下标替换，不等于翻译术语；数学片段仍应绕过可改内容的替换。
- 正式本地 `scripts/dev/formal_mineru_conversion.py:211` 生成 evidence 并 ensure 后写 sidecar；在线同源 renderer。component runner 调同一 adapter。
- matrix 实际支持 `--mode direct --sample-set phase2-core`，可选 `--sample-id`。Golden runner 有 `--preflight`、认证与 runtime 前置；本轮没运行线上 preflight/回归，不虚构环境状态。
- 当前已提交 component 最小 OPA228 fixture 不能证明公式/表格行为；后续必需合成 MinerU→IR→非空 Word table+公式完整链路，不能用“runner 可打开”替代。

## 5. 本轮定向基线

9 项现有测试通过，耗时 0.167s：renderer layout 类中的 fraction、malformed fraction、extended OMML、CM4112、datasheet tex matrix、table cells/notes、manual formula residue 共 7 项，以及 converter layout 类中的 semantic math sources 和 missing formula payload 共 2 项。准确命令见 `../planning-validation.md`。

这只能证明已有正例和残留扫描行为仍成立，不能证明统一降级完成。未运行业务实现后的新测试、release、component、Golden 或 Word 人工验收。

## 6. 合成反例（正式 renderer + evidence）

逐个构造只含一个 block 的 DocumentIR，调用真实 `DocumentIRWordRenderer.render_to_bytes`，读取 `word/document.xml` 的 w:t/m:t 和 m:sup，再调用真实 `build_renderer_evidence`。无网络、文件/生产状态写入。

| case | 输入 | 实际可见文本/结构 | 结论 |
|---|---|---|---|
| unknown | `$\unknown{V_{OUT}}$` | `\unknown{VOUT}`，无 OMML；docx_latex_residue:1 | 原式经过归一化，无逐公式受控降级；下标可能以 run 样式存在，不能仅凭扁平文本断言下标丢失 |
| tag | `V=IR\tag{7}` | `V=IR`，1 OMML | 编号 7 消失，无公式诊断 |
| mixed_fraction | `增益为 $\frac{1}{2}$，单位 V。` | 整段 1 OMML | 分数外自然语言一并进入数学对象 |
| sup_scope | `x^2+3` | m:sup 为 `2+3` | 上标作用域扩大 |
| text_spaces | `\text{A B}` | `AB` | 明确文字空格丢失 |
| vee | `A\vee B` | `AVB` | 逻辑或变成字母 V |
| table_rich | `<td><b>增益</b> $\frac{1}{2}$</td>` | `<b>增益</b> 12`，cell 内 1 OMML | HTML 标签字面泄漏进数学内容 |

七例均无公式专用报告、均无 fatal blocking flag。短 formula-only 样本还触发当前 `<20 字` 的 `docx_no_editable_content`，部分触发 unstyled heading clue；这些既有指标不当成公式问题已被正确诊断的证据。

复现核心（沿用已安装 Pydantic 的必填 document_language）：

```python
ir = DocumentIR(
    metadata=DocumentIRMetadata(job_id="rnd502_probe", source_file_id="synthetic", document_language="zh"),
    blocks=[DocumentIRBlock(id="probe", type="formula", order=0, latex=r"x^2+3")],
)
content = DocumentIRWordRenderer().render_to_bytes(
    ir, template_path=None, config_path=None, image_loader=lambda _asset: None,
)
# 用 zipfile.ZipFile(io.BytesIO(content)) 读取 word/document.xml，检查 m:sup，而不是只比可见全文。
```

首次临时探针漏填 document_language，被 Pydantic 正确拒绝；补齐后得到以上七例。该失败仅为调查脚本输入错误，不是业务基线测试失败，没有修改模型或放松验证。

## 7. 收敛结论

保留已有支持子集；新增统一结果/受控文本降级、保真修复和证据接线。无需微服务、新解析器、AI、图片引擎或 DB 迁移。`skipped_existing` 不成立。冻结下载/批准/发布规则不变，warning 的原式保留政策等待本次规划评审整体确认。

## 8. v2 独立审查补充

独立 architect 对 v1 确认 P1 翻译数学边界缺口及 P2 预期输出绑定缺口，主会话均已独立复现；详情见任务 planning-review.md 和 research/architect-review-revisions.md。三件套已修订 v2，增加最小 translator 触点和主动篡改负例、输出投影与实际 XML 比较，并澄清三类历史恢复、原式诊断出口及活跃执行器回退下限。不改变 Codec/Provider 或数据库结构，任务仍 planning。随后第二位全新 architect 独立复审 v2，确认两项在规划层闭合且无新增确认问题；见 planning-rereview.md。主会话核实后保持三件套原字节，不升级版本、不进入实施。
