# RND-502 独立 architect 规划审查与主会话修订

日期：2026-10-23（Asia/Shanghai）；当前规划版本：2；状态：planning，未授权实施。

## 审查身份、范围和证据边界

用户明确要求派一个全新 architect 独立只读审查。实际代理为 `/root/rnd502_fresh_architect_review`（Ptolemy），角色 architect，`fork_turns=none`，未继承主会话对话；由提示词提供准确任务路径和只读约束。只派这一位架构审查代理，没有派实施/检查代理，也没有执行 task.py start。

被审对象为版本 1 的 prd/design/implement；按真实源码核对数学/翻译边界、降级、证据、历史恢复、receipt/generation、权限和诊断出口。原稿完整保存在 `research/reviewed-v1/`，下文 v1 行号以该快照为准。

| v1 文件 | SHA-256 |
|---|---|
| prd.md | e1866e7cabed35eb0ed532920f78950180e5d15010c115c1a1e80c2ce492760d |
| design.md | b46b9e92c4d704a6613b1ed6e55ea749af1dddc5833b1be67820c53b9bf63f77 |
| implement.md | bc4df5d1ed68885f7afa96e3420b1517267afb1c896807d3bedd8d0fc4088967 |

首轮审查返回 1 项 P1、1 项 P2。主会话对两项均重新读取相关真实代码并独立执行纯内存探针，确认后修订为 v2。下列“已修订”只表示规划合同已补齐，不代表业务缺陷已修复；首轮结束时 v2 尚未独立复审。随后第二位全新 architect 对 v2 的独立复审未发现新增确认问题，记录见 `planning-rereview.md`，三件套保持 v2 原字节，仍待人工审核。

## [P1] 数学边界与翻译抽取未闭合

**原始位置**：v1 design.md:22、:32，implement.md:17、:48，PRD AC7。

**触发与影响**：renderer 接受 `<eq>` 为数学边界，而表格翻译抽取剥去标签后将内文送入 Provider；现有 Codec 未整体保护这段数学内容，改值也可能通过完整性校验。后续 renderer 只能对已被改写的最终 IR 作报告，不能证明源公式保真。

**真实证据**：

- `app/domains/translation/document_ir_translator.py:523` 的 `_append_table_text_nodes` 在 :531 解析 DOM、:533–548 将每个非空 text node 当作独立单元；:580 的回填按同一非空序号替换。
- `app/domains/translation/protected_tokens.py:118`、:119 保护既有数学分隔符和特定赋值式，不保护裸 `<eq>` 内文。
- `app/domains/translation/integrity.py:255`–263 只比较已被 Codec 识别的技术 Token inventory。

**主会话独立探针**：使用真实 `extract_translation_items → encode → validator.validate → apply_replacements`，所有内容均为内存合成数据，未调用 Provider：

```text
input: <table><tr><td><eq>\text{High Low}</eq></td></tr></table>
extracted_items: [("table.html.0000", "\\text{High Low}")]
formula_tokens: 0
fake change: High → Changed
integrity_status: passed
final_html: <table><tr><td><eq>\text{Changed Low}</eq></td></tr></table>
```

**v2 修订**：

- PRD 新增 R7，AC7 明确主动篡改、普通正文仍翻译及调用前失败语义。
- design 新增“翻译准备边界”：converter 保留已有可保护表示；translator 明确数学子树不生成翻译目标，仍保留后续非数学节点原 index；普通片段检查现有 Codec 的真实覆盖。跨节点等无法安全保护的片段在 Provider 前失败，内部码 `translation_formula_boundary_unprotected`，顶层仍为 `translation_failed`。
- 不改 Codec/Provider 规则，不把整格正文一并排除；不重写既有同代根计划，不匹配旧计划按原合同失败关闭，只在合法新代重建。
- implement 明确增加 `document_ir_translator.py` 的最小触点及同步/Worker/本地验证，补 `<eq>`、数学内样式交错、混合正文、主动篡改和调用次数负例。

**处理状态**：主会话确认，规划已修订；实现待授权。

## [P2] 缺少锚点内实际输出绑定

**原始位置**：v1 design.md:47、:66、:68，implement.md:60。

**触发与影响**：原报告只绑定源哈希、位置、mode、reason、anchor 和数量；保留这些字段仍能把实际输出的数字或上下标写错，不能兑现“错式拒绝”。

**真实证据**：`app/services/renderer/evidence.py:49`–70 主要统计通用结构；`docx_quality.py:191`–193 的正文投影没有上下标结构信息。

**主会话独立探针**：真实 renderer 从同一 IR `x=1` 生成 DOCX，在内存中为其加入固定 bookmark `md2w_formula_000001`，然后只将该范围文字等长改为 `x=2`：

```text
same_source_ir: true
same_anchor_mode_count: true
visible_value_changed: x=1 -> x=2
build_renderer_evidence(ir, original) == build_renderer_evidence(ir, modified): true
```

**v2 修订**：

- AC5 明确源绑定与预期输出绑定同时存在。
- 报告加入 `output_projection_version`、`expected_output_sha256`；从转换结果在写 document DOM 前生成预期，不能从最终 XML 自证正确。
- 固定语义投影：literal 原式/提示、semantic run 的文字/上下标、OMML 数学结构/值/显式样式及可见 tag；最终 analyzer 从锚点范围重建比较。
- 补相同 source/anchor/mode/count 下改数字、移上下标、截断原式和漏提示的负例；明确此绑定不替代 parser 数学语义测试、不引入第二 TeX 引擎。

**处理状态**：主会话确认，规划已修订；实现待授权。

## 其余核验结论与实施澄清

- **receipt/generation 方向成立**：`result_state.py:43`–45 保留先选 receipt；:23–28 检查代数/IR/receipt；execution.py:3257–3262 的完成更新带条件。三 adapter 在同 job 锁内读取最新记录后调用共用 patched_job，适合合并选中摘要。v2 没有扩展 receipt 协议，也不允许 I/O 进入锁内。
- **状态和权限 owner 保持**：delivery_state 的首次绑定/换代/复核 CAS、service 的内部下载和发布资格/执行分离继续有效；没有需要新增状态机或降低批准门槛的证据。
- **历史恢复三路径必须分别落实**：legacy 扫描在 execution.py:3383–3390 重算 evidence；明确 result_file_id 在 :3360–3366 可沿原合同跨代复用；已有 receipt 在 :3052/:3243 不经过扫描。v2 明确三路径、新报告在恢复期的严格校验、原 IR 绑定及旧代报告不导入新代质量。恢复损坏保留 uploading/oss_failed 合同，不能换件掩盖。
- **私有含义和旧出口明确**：files/router.py:743–770 返回完整 metadata，files/service.py:763–770 限制为同 tenant/company owner/admin；这不是服务器专有存储。execution 的 :3184/:3272 展开 metadata，事件投影除新报告外必须处理 `docx_quality.latex_residue_examples`。v2 已补该边界和测试，不新增文件查询 API。
- **回退下限明确**：没有 DB 迁移必要；v2 删除“旧 reader 忽略字段即可”的笼统承诺，要求兼容新报告/抽取计划和既有 receipt 的执行器，否则先暂停消费者/内联执行或排空旧代，保留产物与审计。

这些是审查确认的正确方向及落地要求，不扩列为额外缺陷。主会话已核对相关恢复、文件授权、adapter 和错误处理代码；不把设计方向成立称为实际实现安全。

## 只读、工作区与实际验证

代理报告没有手工写入、未执行任务激活、Git 操作、服务或外部调用；使用了源码/Spec/测试源码读取和 `python -B` 内存探针。主会话核验：审查前已有 905 个文件哈希、三件套哈希及 index tree 均未改变。

完整 status 对比另发现新出现的 `.serena/.gitignore`、`.serena/project.yml`；目录还包含被其忽略的 project.local.yml。代理随后明确未调用 Serena，也未执行创建命令。来源不能确认，因此这些文件保留原样、未删除、未纳入本任务修改；不把它们归因于代理，也不宣称完整工作区在审查期间绝对零新增。主会话另记其哈希，以确保后续未触碰。

本轮没有业务代码变更，不重跑初版已通过的 9 项基线；两项新增探针由主会话独立执行成功，分别确认 P1/P2 的规划缺口。v2 的任务 validate、context/路径/版本/差异和工作区保护结果追加于 planning-validation.md。没有执行实现后测试、release、Golden、真实 DB 或 Word 人工验收。
