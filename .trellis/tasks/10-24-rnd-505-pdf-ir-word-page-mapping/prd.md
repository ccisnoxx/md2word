# RND-505：PDF/IR/Word 页映射

- 版本：规划 v2，2026-10-24；状态：planning，等待人工评审。
- 发布阶段：R5（DOCX、模板和预览）。父任务：datasheet-docx-delivery-quality。
- 依赖：RND-501、RND-504均已人工验收done/implemented；当前根未集成，统一基线门G0未满足。
- 本轮授权：调查、任务登记和规划文档；不集成业务、不start、不提交/push。建议分支md2word/RND-505仅记录。

## 1. 目标与用户结果

审核人员及后续三栏审核消费者能够从源PDF的页/区域，经DocumentIR稳定block ID，找到同一主DOCX的实际bookmark，并取得该预览内可解释的跳转页或明确不可用结果。分页估计不能伪装为精确定位；定位失败不得损坏内容或改变既有质量、复核、下载和发布决定。

依据产品PRD FR-013、RND-505完整backlog及ADR-004/010/012/015。详细证据见research/renderer-baseline.md、preview-baseline.md、dependency-baseline.md。

## 2. 已知基线和真实差距

已验收RND-501有source projection、逻辑anchor_ref、逐block实际OOXML targets，但通用block书签尚未物化，word_page固定None。已验收RND-504有预览PDF/页图/页数、manifest及CAS/保留期/权限，但没有锚点页定位。现根又未集成两者；不得把依赖状态done当成本地已有能力。

现有能力不能完整满足本任务，不建议skipped_existing。复用既有renderer、collector、preview manifest及授权流程，只补通用书签和独立映射合同。首版采用预览页数加来源/实际输出顺序的确定性推断，不新增引擎位置提取能力，不承诺多页实际页码或像素级一一分页。

## 3. 范围与需求

- R1 稳定链：保留原block ID/anchor_ref、IR hash、source spans/provenance、主DOCX及预览身份；ID稳定范围为同一固定IR，不宣称重新解析/增删源块后跨代ID相同。
- R2 通用锚点：在真实输出对象上物化非可见书签；覆盖正文、标题、列表、公式、原生表、图片组及题注；创建成功事实使用独立可选锚点证明，原RND-501 v1字段语义不变。共享/归并指向真实代表；无输出、被抑制或替换的块保留原因，不伪造实际对象。
- R3 映射Artifact：现有word_preview_manifest承载独立版本page_mapping，记录source spans、block/anchor、定位结果、confidence和原因。保留多源span；跨页表只给起点估计，页范围未知明确为空。
- R4 可解释降级：单页且有真实正文目标可定位page0；多页按来源或实际输出顺序估计，全部标低置信；无本块来源时借最近有来源输出块，距离平局规则固定。无可用预览时page=null。实际目标位置与导航fallback分开，suppressed/重复页眉不伪装命中。
- R5 隔离失败：映射缺证据、旧件无trace、书签未生成/冲突、容量超限只使映射降级或不可用；不改原内容与四类业务状态。原内容完整性、身份校验、权限与真实存储故障继续原失败合同，不能借降级放行。
- R6 生命周期：映射随同一预览manifest被原CAS选中，旧代、迟到attempt、旧run和失效引用不得作为当前映射；不覆写已发布件或历史产物。

## 4. 非目标

不实现前端三栏交互、QA-602公开查询API、RND-506页级质量检测、QA-605发布能力；不修改源PDF，不重跑/替换MinerU，不新增PDF文本解析、OCR、正文相似度匹配或AI定位，不选择/部署预览引擎。没有在线Word/表格编辑、中文转中文Prompt、双语DOCX、批量任务、知识库。真实引擎输出锚点坐标/完整跨页范围可以后续另审，不能悄悄升级本任务首版承诺。

## 5. 固化不变量

1. 一次只实现当前任务；依赖仅复用必要已验收能力，不提前实现其它清单项。
2. 保持模块化单体，不加微服务、Kafka、向量库或第二套转换流水线。
3. 一个DocumentJob只有一份用户主DOCX；其他语言create/clone新任务。
4. direct_pdf_to_word不调用AI Provider、翻译Prompt或翻译术语集；MinerU是唯一PDF解析入口。
5. HTML可解析时输出Word原生表格，不以截图简化；不改变表格、公式、图片的内容完整性门。
6. blocked及翻译unreviewed仍可内部下载，不得批准/发布；前端仅消费后端权威状态/available actions。
7. 不削弱权限、审计、技术Token、不可变发布、路径安全；映射无权更改任何质量/复核/交付决定。
8. source page、preview page、Word显示页码是不同概念；零基page_index仅指相应产物内页索引，不推定页码字段或物理像素。
9. 稳定ID贯穿；DocumentIR保持内容/来源模型，不塞Word专有对象。映射失败不修改源PDF/IR/选定DOCX，且不改变发布条件之外的状态；本方案连既有发布条件也不扩改。

## 6. 权限与失败语义

现有owner/Admin、tenant/company/job、文件当前引用、生命周期及技术Token规则完整继承。映射只在授权manifest内展示完整ID/坐标，不新增公开自由trace。缺失和低置信不授予批准或发布；旧artifact无映射不阻止其合法下载。非法身份、未知存储错误不能冒充“无证据”继续成功。生成新的DOCX时允许增加非可见书签；选定结果之后只读，禁止补写书签或metadata。

## 7. 验收条件

| ID | 可观察验收 |
|---|---|
| AC0 | G0统一基线指纹和两依赖共存回归通过；批准后才可实施本任务，历史单分支通过不代替G0。 |
| AC1 | 同IR/模板输入重复生成稳定anchor名；真实最终OOXML有配对书签且指向本块输出，模板/公式/图片书签保持；同实例并发不串计数；通用锚来自同次创建证明，不凭旧首名或namespace推定。 |
| AC2 | 单表多span、被归并空fragment、三图cell/多注释、列表、TOC代表、共享装饰、空/抑制块均保存正确owner/disposition；无输出不虚构命中；成功预览+完整有界trace但全为非正文/无输出块时保留全部entry，报告unavailable/no_target。 |
| AC3 | manifest内独立mapping绑定同一IR/plan/DOCX/preview generation、result/run/attempt/profile/PDF哈希；记录来源真实性档位，legacy自由span不变成verified。 |
| AC4 | 正文单页定位0；多页例S=3/P=5对应源rank0/1/2→0/2/4且confidence=low；S=1/P=5/T=3有来源正文按输出序→0/2/4；无来源最近输出距离平局选前者；全无来源用实际输出顺序；无预览null，不越界。 |
| AC5 | 长表只给estimated_start、range=null；source spans多页不产生伪精确Word范围；重复页眉仅fallback。实际输出顺序与IR数组顺序不同的双栏例仍定位正确owner。 |
| AC6 | 映射不可用/未知版本/超限不改变DOCX、IR、preview成功与质量/审核/发布/下载结果；日志有安全原因。原内容损坏和存储失败负例继续失败关闭；模板同名在target内部也不冒认成功，证明缺失/坏/未知只影响锚点可用性。 |
| AC7 | 重放、并发竞争、旧generation/run/attempt、过期/删除/归档/published、局部登记中断及历史无字段兼容保留RND-504原保证；独立锚点证明在三恢复入口保留并校验，公开出口继续隔离；映射无新增队列/重试账本。 |
| AC8 | manifest原授权可消费映射；跨tenant/company/owner和陈旧Token拒绝，公开API/事件/日志无正文、路径、自由ID或私有lease泄漏；OpenAPI快照保持。 |
| AC9 | 去除本任务新增非可见书签后的规范化OOXML及既有公式/图片报告认证证明内容/结构不变；Word和部署预览视觉证据单列，未运行不宣称通过。 |
| AC10 | 定向、component/direct、release/OpenAPI与必要线上/人工门有证据或明确阻断记录，Spec/合同更新、最终diff通过评审；只有人工接受后才done。 |

## 8. 评审状态

需求已按上述范围收敛；无需新的产品决策才能完成规划。G0和真实部署/视觉证据是明确实施/启用门，不是隐含已完成项。当前三件套待人工审核，尚未授权实施。
