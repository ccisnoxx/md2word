# RND-502 v2 必须落实的独立审查修订

完整审查/主会话复现/原稿哈希见当前任务 `planning-review.md`；被审 v1 在 `research/reviewed-v1/`，这些旧稿不作为实施上下文。当前三件套版本为 2，仍待人工审核，未授权实施。

## P1：翻译数学边界

真实 translator 的 `_append_table_text_nodes` 会把 `<eq>\text{High Low}</eq>` 抽成裸文本；Codec formula=0，fake 改值仍通过现有完整性校验。主会话已独立复现。

- 复用共享数学边界；明确数学 DOM 子树不进入翻译目标，保持非数学 text-node index/ID 和回填位置。
- 其余数学片段须由原 Codec 整体保护；无法闭合的跨节点数学在 Provider 前失败，固定安全内部码/事件，保留源 IR，不生成混合语言主件。
- 不改 Codec/Provider/批次持久格式；不重写旧代已安装根计划。新抽取与旧计划不匹配时按现有合同失败关闭，部署/回退排空或使用兼容执行器。
- 必须有主动篡改数学内部的 fake、数学内 HTML 样式交错、普通正文仍翻译和调用前拒绝测试；echo 往返不够。

## P2：预期输出绑定

同一源 IR 的 DOCX 中将相同 anchor/mode/count 下的 x=1 改成 x=2，当前 evidence 相等。主会话已独立复现。

- 在写 DOM 前从 FormulaRenderResult 确定 `formula-output/v1` 预期投影及 SHA-256；不从最终 XML 自证预期。
- 最终按锚点范围重建：literal 原式/提示、semantic 文字/上下标、OMML 结构/值/显式数学样式及 tag 编号，拒绝改值、移脚本、截断或漏提示。
- 输出绑定不替代 parser 的数学语义测试，不新增 TeX 引擎。

## 恢复与出口澄清

分别测试 legacy 扫描、明确历史 result_file_id、已有 receipt 三条入口。保留明确历史主件的跨代复用；历史报告不导入新代质量，新报告损坏不降级 legacy。I/O 在锁外，安全摘要只从选定 receipt 在条件更新内合并，恢复错误保持 uploading/oss_failed。

“私有报告”是 owner/admin 可读内部 metadata；现有 files API 会返回它。事件摘要除新报告外必须移除旧 `docx_quality.latex_residue_examples` 原式出口。回退不得使用不理解当前 receipt/报告/计划的活跃旧执行器。

上述两项已由第二位全新 architect 独立复审，确认在 v2 规划层闭合、无新增确认问题；完整记录见任务 planning-rereview.md。三件套保持 v2 原字节，仍待人工审核。实现后仍需按 implement.md 的完整性、并发、权限和样本门禁验收，不能将规划复审当成实现通过。
