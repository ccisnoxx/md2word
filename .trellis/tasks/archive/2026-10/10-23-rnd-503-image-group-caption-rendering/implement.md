# RND-503 实施计划 v2

> 2026-10-23。全新 architect 审查及主会话复核后的修订稿，新增生成时输入绑定与兼容回退验收。当前只规划，不执行以下实现步骤；必须先由用户审核最新 prd/design/implement。不得以 task create 或本文件的 checklist 视为实现授权。

## 1. 实现前硬门与有序任务

### 0. 重新核对基线（后续获批会话）

- [ ] pwd、git status --short、实际 branch/HEAD；识别并保护原有 dirty/索引，禁止 stash、覆盖、删除、bulk stage。
- [ ] RND-503=planning，IR-204=done/人工接受 skipped_existing，复读用户授权和三件套；没有其它冲突的 in_progress 实现。
- [ ] **当前根 HEAD 尚不含 IR-204 最终接受提交 17cde1f**。先取得独立获授权、包含其实际能力与传递输入安全依赖的集成基线，记录来源/变更/hash及基线测试；不能从 main 整文件覆盖当前 TR-406/CON-104/RND-502，也不能在 RND-503 重做 IR-204/201。如仍未完成集成，停止实现，报告基线阻断；依赖状态真实回退才将 manifest 改 blocked。
- [ ] 集成验收包含旧IR缺字段/显式None、原始IR含非空验证/回执但旧reader忽略、旧evidence已保存非空摘要四类形态的三入口恢复；保持原证据必要键和语义。新增None键不是自动失败的确认缺陷，不以假设冒充历史生产记录；非空差异未闭合时先停依赖集成门。
- [ ] 核对 RND-501 及并行 caption 工作树对相同文件的改动。若新集成使接口/合同偏离本稿，先修订规划再重新评审，不假定旧研究是当前事实。
- [ ] 重读当前 backend Word/quality/error/结果身份 Spec、产品冻结合同和已集成 IR-204 回执字段；只有用户在后续消息明确批准最新规划且基线就绪后，才执行 task.py start 和 RND-503→in_progress。

### 1. 图片计划与几何（AC1/5/6）

- [ ] 在现有 layout_plan owner 增加 image-group/v1 常量、少量 frozen 数据结构和纯判定；按 design §2 的源连续 run、纵向分量全组复核、横向序和唯一归组规则实现。
- [ ] 旧 LayoutPlan 默认结构/aggregate/历史解释保持；新图片计划独立附加，不把 bbox 全局重排当源序。
- [ ] IR-204 uncertain/evidence-only veto 与明确原因接入；普通单图不误报；未知几何不 coercion 成可用坐标。
- [ ] 在 Word Spec 先把 COL-003 及 IMAGE/FLOW 冲突矩阵写成当前目标的 planned 规则，保留 COL-002 普通正文原生栏；不扩大到普通页面/表格算法。

### 2. 表格图片 writer 与单图保真（AC2/3/4/6）

- [ ] 在写DOM前固定image-render-inputs/v1：实际模板身份/hash、语言、投影/文本语义版本、最小有效几何和规范化格式规则；实际加载值只读取一次。现有格式规则owner增加必要的冻结/重放纯入口，不复制匹配算法、不引入通用资源快照系统。
- [ ] 无边框固定1×N表格，显式边框 nil、width/grid/cell/margin、inline；有效宽高约束与原比例；沿用禁止自动压缩。
- [ ] 提取真正共享的逐图/逐注写入职责，显式携带 root context、cell width 和字段来源；不增加纯转发 wrapper，不让 cell 触发页面宽度默认值。
- [ ] 每图完整 captions/footnotes 独立段落、正确 keep 链和行 cantSplit；复用现有 SEQ/REF/富文本/公式实现，不更改技术 Token 或翻译 owner。
- [ ] 组前准备资产/解码；缺失/损坏整组顺序单图，诊断保留全部注释，最终仍完整性失败。意外存储错误不吞掉。
- [ ] 页/region 编排一次消费图片 span，拒绝组按源序单图；普通正文、局部 wide block、页眉页脚、源页方向和语义分页不被新表格吞并。
- [ ] 删除旧图片 zip/center-tab writer 及失去使用者的 helper，仅保留一套分组/渲染决策。

### 3. 报告、对账和兼容恢复（AC7/8）

- [ ] 单次 RenderContext/DocumentIRRenderResult 增加兼容的 image_layout_report；不影响 formula_report 或旧 render_to_bytes 调用。
- [ ] 报告绑定原始IR/模板/构建策略和冻结输入hash，首次核对实际加载来源与外层文件身份；在原candidate descriptor/receipt内一次保存，不保存可变路径供恢复重读。
- [ ] 从源annotation+冻结输入/已知投影版本重算expected，实际包独立重验组/cell/图片 SHA/inline/field/annotation 内容与来源，不能仅信报告expected值或从输出自证。每span实际section属性由DOCX独立读取并与写前几何比较，不用全书最后一个section猜原宽度。
- [ ] 总表格旧字段原语义保持；新增 verified layout/content/total 对账；只有核验成功布局表可豁免内容表计数，unknown/伪造标记明确失败。
- [ ] standalone analyzer 保守排除候选布局表带来的虚假数据表可编辑性；正式证据做完整认证，布局表不虚增 wide/header 指标。
- [ ] 正式 execution 与本地 adapter 传同次报告，登记 candidate 前校验。现有共享恢复 validator 扩展到图片报告，覆盖 legacy/explicit/receipt，旧件保留旧字段集合/布局解释；新字段损坏不得 legacy fallback。
- [ ] 三恢复入口仅使用原文件IR与冻结输入；当前模板、默认指针、语言/符号设置变化不影响合法旧件。必要绑定/快照缺失、hash不符、未知投影版本显式失败；历史无图片报告不补字段。
- [ ] 普通事件只投影安全 summary、原因计数和有界 ID examples；API 不暴露报告/必要格式配置快照，禁止保存任意YAML/Settings、路径、翻译术语、Prompt或凭据。新 warning 不直接改变质量/批准/发布语义。
- [ ] 保留原 CAS、retry_count/generation、最终 IR、first-valid receipt 和文件不可变 descriptor；没有锁内渲染、对象 I/O、跨仓储新事务或仓储字段变动。
- [ ] 形成并记录可部署兼容回退构建B1：reader/版本解释/分类/三入口/公式/receipt接线保留，生成侧走既有单图，代码构建策略single-only/v1写入冻结输入。无运行时开关，不把已确认组的主动单图策略误标为几何不确定；历史grouped/v1仍按原策略重验。

### 4. 样本、文档与交付（AC5/9/10）

- [ ] 复用 IR-204 接受的可靠图5/6、24/25合成 ZIP；复用 Git 180c90a 中已接受的去标识 caption-pair 结构时同时保留授权/provenance/hash，不预修不可靠源串。
- [ ] 合成非方形 PNG 覆盖横竖图，素材不含专有图像、正文、参数和凭据；不提交输出 DOCX、原 IR 或截图。
- [ ] 更新与本任务直接有关的 Word Spec/DOCX 设计图片和 evidence 小节，记录与旧 COL-003 的替代关系；不改产品冻结 PRD/ADR，不重写整个规范。
- [ ] 完成下列验证与差异复核，逐条映射 PRD AC；Trellis check 及必要共享结果合同复核不能省略。新生成侧启用前必须有B1对已存在新报告和旧公式报告的恢复/拒绝证据，不把排空当前任务视为历史兼容证明。若候选确有未解决的持久化/公开合同风险，按 AGENTS 要求取得合适的独立只读审查，不用审查代替主会话复验。
- [ ] 实现完成只更新 RND-503 为 review，Trellis 保持 in_progress；等待人工验收/commit plan 确认，不自行 done、archive、提交或 push。

## 2. 计划修改文件与边界

| 文件 | 计划改动 |
|---|---|
| `app/services/renderer/layout_plan.py` | 图片计划、阈值、拒绝原因，旧主计划兼容 |
| `app/services/renderer/image_renderer.py` | 原生布局表格、共享单图/注释写入、比例和失败注释保真，移除旧 tabs |
| `app/services/renderer/word_renderer.py` | 消费图片计划、root/cell context、单次报告及 span 编排 |
| `app/conversion/docx_rules/terminology.py` | 既有格式规则的最小冻结/重放纯入口；保留顺序/regex/作用域语义，避免checker复制算法 |
| `app/services/renderer/evidence.py` | 图片报告校验、源/实际绑定、表格分类、warning 与摘要 |
| `app/services/renderer/docx_quality.py` | 实际表格/inline/annotation结构提取，布局候选与内容指标分离 |
| `app/domains/document_jobs/execution.py` | 同次报告/三恢复入口与安全事件接线；不修改任务执行状态模型或仓储 |
| `scripts/dev/formal_mineru_conversion.py` | 传同次报告；不另建本地规则 |
| `tests/test_image_group_rendering.py`（新增） | 纯计划、OOXML绑定、阈值及输出负例，使用可控中性图 |
| `tests/test_document_ir_word_renderer_layout.py` | 替代 tabs/multi-annotation 的旧断言，保护普通栏、分页、单图和表格 |
| `tests/test_document_ir_mineru_converter_layout.py` | 正式ZIP→IR→DOCX图对及保真，IR-204语义保持 |
| `tests/test_document_job_result_persistence.py` | 新报告恢复/篡改/历史兼容、事件隐私及竞争复用 |
| `tests/test_conversion_sandbox_dev_tools.py` | 本地正式 adapter 与报告/完整性门禁接线 |
| `.trellis/spec/backend/word-generation-rules.md` | COL-003/IMAGE/FLOW/QUALITY/冲突及样本矩阵，报告与恢复合同 |
| `docs/design/docx-rendering-template-design.md` | 图片分组阈值/布局容器/evidence及已知限制 |
| 当前子任务文档/context、manifest 的 RND-503 | 证据和状态；仅本任务 |

不计划修改 IR模型、caption_reconciler/converter 业务逻辑、table_renderer、repository/schema、API/router、前端、模板 seed、依赖清单或部署配置。测试fixture优先在测试中构造/复用已接受资源，不升级 component runner/manifest 为通用图片平台。需要更改上述边界时先给出具体证据并更新规划。

## 3. 定向测试及断言

- 计划：同页2/3图与独立多行；四项纵向阈值及间隔的内/等/外；invalid/NaN/无尺寸、跨页、body/section中断、横向重叠、逆序/column-major、竞争/传递链。输入 IR 不变，重复计划一致；单个不确定分量不吞其它确定行。
- OOXML：确切1×N、nil六边、fixed/grid/tcW总宽、有效区域、wp:inline无anchor；非方形源像素与显示比例。每图多 caption/note 的 cell 和顺序，SEQ/REF/bookmark/公式来源，最后一注不keep到下一组。
- 不确定/失败：caption_binding_uncertain、evidence-only paragraph 原样一次输出；原IR缺回执不宣称修复；缺失/损坏其中一图不产生半组/丢注，最终门禁失败；普通单图不被误标。
- 完整性负例：复制/删除/伪造布局marker，新增数据表伪装布局表、保留总数但交换图片/题注、删footnote、换关系目标、inline→anchor、破坏宽度。纯图布局表不得作为数据表放行可编辑性；IR原生表仍必须对账。
- 原始输入：同一IR用两套合法非默认模板/页边距和符号规则，输出及绑定不同；生成后改变当前配置、默认指针或移除原临时配置文件，三恢复入口仍按原冻结输入通过。span多section/栏宽分别核验；未知投影/输入版本、缺失快照/hash不符、模板/IR身份错绑均拒绝；新无外部配置本地调用必须有明确builtin身份。
- 结果：新/旧report、报告部分缺失/未知版本、三恢复入口、明确历史跨代文件绑定原IR/原render_inputs；同renderer并发隔离；迟到worker/retry/cancel/两恢复者不更换receipt、不污染当前generation；RND-502公式恢复和事件隐私不回归。
- 回退：B1恢复正常构建已生成的grouped/v1文件，覆盖legacy发现/跨代明确历史指针/receipt和旧公式报告；保留损坏拒绝、表格完整性和原身份；B1新件single-only/v1顺序单图、无无意义uncertainty，正常构建也能读取这些新件。B0旧checker拒绝含布局表文件的现有反例仅说明不安全下限，不能称可用回退。
- 样本：可靠图5/6和24/25证明正确归属；去标识真实错配fixture证明保守回退与源内容守恒；普通单图/无注图/普通数据表/原生正文双栏共同验证。

基线就绪、实现完成后的首轮集中命令（新模块和依赖测试届时应已存在）：

```bash
.venv/bin/python -m unittest tests.test_image_group_rendering tests.test_document_ir_word_renderer_layout tests.test_document_ir_mineru_converter_layout tests.test_caption_reconciler tests.test_document_ir_layout_contract tests.test_formula_rendering tests.test_document_job_result_persistence tests.test_document_job_modes tests.test_conversion_sandbox_dev_tools
```

先诊断失败再改动复跑受影响目标；稳定候选通过后不无故重复同一大组。若依赖集成带来测试模块更名，记录实际选择与原因，不删除其必要合同验证。

## 4. 回归门禁与证据边界

```bash
git diff --check
.venv/bin/python scripts/dev/run_component_pdf_regression.py --output-dir tests/tmp/rnd503/component
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core --output-dir tests/tmp/rnd503/direct
.venv/bin/python scripts/ops/check_release.py
.venv/bin/python scripts/ops/run_golden_sample_regression.py
python3 .trellis/scripts/task.py validate .trellis/tasks/10-23-rnd-503-image-group-caption-rendering
```

- component 必须用正式 adapter；当前根只有 OPA228 smoke，不能声称覆盖图对。获授权依赖集成后的 enabled 样本数以实际 manifest 为准，不照抄 IR-204 的历史8/8。
- direct matrix 记录实际 sample IDs、输入/输出 hash、新/既有 flags，direct 的 Provider/翻译资源加载断言由 modes tests 保证零调用。不借此新增TR-401或付费模型调用。
- check_release 含当前 OpenAPI snapshot 门禁；不修改 API 时预期 current、无 generated schema 差异。无需前端 build/browser 或真实DB迁移测试：这些边界未变；结果合同用已有 file/sqlite/fake MySQL 回归，不宣称真实 InnoDB 已验。
- Golden 依赖既有线上/认证环境。无凭据/网络/实际环境时记录精确阻断及该命令未执行或preflight结果，不能把本地XML/最小smoke称为Golden通过；不主动连接用户未请求的VPS、不部署服务、不向外发送专有样本。
- Microsoft Word 是正式视觉验收：检查目标图对、单图、长注释、跨页、字段更新前后、原生表格相邻页，记录版本、当前代码版本、输入/输出hash及截图定位。既有部署预览作为另一实际客户端记录，不实现 RND-504/506；缺该环境时显式列待验项。不用 LibreOffice 单方结论替代 Word。
- 此轮规划仅已有9项基线及内存探针；上述实现/Golden/视觉门禁尚未执行。局部通过不能提升为整本文档或上线通过。

## 5. 文档、Spec 与回滚点

- 实施前先把明确冲突的 Word 图片规则标 planned；实现与证据齐备后同步 owner、阈值、拒绝/错误矩阵、历史兼容、OOXML/客户端分层。新增或实质修改的注释/docstring/错误/日志用中文，机器键/枚举保持英文，不为未改代码批量翻译。
- B0是获授权依赖集成后的**开发差异基线**，在preflight写实际hash；当前1835263仅是调查点。B0只能用于尚未产生新图片产物时撤销开发diff，不能在已有候选/receipt/历史件后作为部署回退版本。
- B1是**可部署兼容回退构建**，须在实施收口记录实际构建/commit/hash及前述恢复验证。回退生成侧到single-only/v1时，image-layout/render_inputs reader、marker分类、投影版本与三入口/公式/receipt接线必须保留；不能按旧顺序回退证据/接线diff。暂无B1实现，不声称回滚已就绪。
- 暂停/排空在途消费后切换B1，保留文件、报告、审计和选中receipt；仍验证未来明确历史指针/跨代复用。不认识新图片报告的B0或旧stage-only执行器都不是产生新文件后的安全下限。
- 不覆盖发布件，不补写历史报告，不回退到整页截图、第二解析器或无条件放行表格计数；不引入本任务专用feature flag逃避版本兼容。

## 6. 完成定义与本轮停止位置

规划完成：三件套可评审，阻断性产品疑问为空，依赖状态和集成差距明确，implement/check真实spec/research context已配置，task validate通过，业务/测试/脚本/Spec没有本轮代码改动，原dirty与暂存内容受保护。

后续实现完成：PRD AC逐项有相称证据，所有新增flag已解释，必要回归及共享边界复核通过，未验Word/Golden/环境项列明，文档/Spec已同步，最终diff无范围外变动；manifest=review、Trellis=in_progress，等待人工验收与提交授权。

**当前停规划评审门**：不得执行 task.py start、实现代理、业务编辑、提交、push、archive 或 add_session。无破坏性迁移或外部选择需求；若出现PRD停止条件即停止，不借实施步骤自行扩大授权。
