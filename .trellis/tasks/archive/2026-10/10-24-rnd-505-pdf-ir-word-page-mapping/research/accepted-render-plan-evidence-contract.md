> 规划只读快照：`69906a5e:.trellis/spec/backend/render-plan-evidence-contract.md`。描述该验收分支；当前根尚未集成。统一基线建立后应以核对过的正式Spec替代此上下文，不据此宣称生产已启用。

# RenderPlan 与 block evidence 合同（RND-501）

## 1. 范围与触发

修改正式 renderer 的计划、同次结果、逐 block 目标或 renderer metadata 的持久化/事件投影时必须遵守。本合同拥有 Word 专有决策和实证；DocumentIR/IR-205 继续拥有来源事实，当前CON-102/103/104继续拥有结果选择和质量/复核/交付，TR-402/403/406继续拥有翻译完整性与批次生命周期；本候选排除RND-504。

这是 RND-501 实施候选的合同；实际验证与尚未覆盖的 Word/MySQL/生产证据以当前任务 validation 记录为准，不因本文件存在而认定测试或用户验收通过。

不创建第二 renderer、Artifact Store、SQL schema、公开 evidence 路由或新任务状态。通用 block bookmark 物化/Word 实际页映射由 RND-505 拥有，视觉 metrics/flags/QualityRun 由 RND-506 拥有。完整 trace 不代表视觉或发布资格。不引入预览模块、配置或启用行为。

## 2. 签名与唯一 owner

- `DocumentIRWordRenderer.render_to_bytes(document_ir, *, template_path, config_path, image_loader, options=None) -> bytes`：原参数/bytes 合同保留，与新结果入口共用实际渲染核心。
- `DocumentIRWordRenderer.render_to_result(...同一输入...) -> WordRenderResult`：同一次的content、plan和block_evidence，以及只供登记前验证的内部不可变 `_ownership`；第一方线上/正式 local adapter 消费此结果，不能先得 bytes 再猜 block 归属。
- `build_render_plan(document_ir, *, layout_plan, effective_config, resource_identity, ...实际已解析策略...) -> RenderPlan`：由 renderer/render_plan.py 拥有，Word 对象创建前确定，复用 LayoutPlan 与 writer 的同一纯策略。
- `build_renderer_evidence(document_ir, word_content, layout_plan=None, *, render_result=None) -> dict`：组合旧 aggregate 与可用的同次 trace，并校验绑定。
- `build_renderer_aggregate_evidence(...)`：aggregate结构对账的唯一owner；保留旧字段语义并可附加可空IR-201报告字段，不产生trace/unavailable字段。历史主件比较只遍历同模块LEGACY_RENDERER_EVIDENCE_KEYS固定的原23键，保持全部旧键值及null语义；不得把新字段强加给旧件或只比较部分旧键。
- `build_renderer_event_summary(evidence) -> dict`：完整字段白名单安全投影，不展开完整 trace。事件、失败 evidence 及公开 flags 复用同一受控规则。

renderer 不依赖 DocumentJob、Provider 或仓储；caller 不重建计划或按正文模糊定位。`RenderCollector.freeze()`同时冻结序列化实证和内部`_RenderOwnership`；后者由frozen dataclass/嵌套tuple保存实际图片对范围及IR/resource/plan/DOCX身份，`WordRenderResult._ownership`不参与metadata或JSON导出。缺失或串次事实按target_mismatch失败，历史件仍走稳定aggregate，不重建该内部结果。

局部collector属于单次调用，不能挂在 renderer 实例或全局，也不能在并发调用之间共享可变计数。

## 3. 数据、持久化和兼容合同

### 计划和资源身份

`render-plan/v1` 保存 renderer policy、input_ir_sha256、resource_identity、sections、decisions、operations 和 plan_sha256。RenderDecision 持原 block ID、逻辑 anchor_ref、源页/region/section、真实文字/表格/图片/公式策略、样式与分页/keep 决策。writer 消费同一计划，不保留第二套独立分支预测。

canonical JSON 使用 UTF-8、ensure_ascii=false、sort_keys=true、紧凑 separators、allow_nan=false；内容身份使用完整 SHA-256，不用 Python hash、时间、随机数、部署路径或对象地址。同 IR/实际有效资源/policy 的计划相同；DOCX ZIP 时间戳不要求跨次相同。

模板身份与 Document 使用同一次加载的 bytes；有效 config/语言覆盖/符号替换规则来自同一已解析对象，不能 hash 后按可变路径重读。只存白名单策略/样式和内容 hash，不存 header/footer 原文、配置/Logo/source 路径、Prompt、凭据或整份配置。模板继承明确记 inherit，计划不预测无法观察的 Word 动态排版。

### 最终逐 block 实证

`block-render-evidence/v1` 绑定 IR/resource/plan/DOCX 身份、完整性/覆盖计数与 block_render_map。每个源 block 恰一主记录，targets 可有序一对多；不存在、重复或串次不得宣称 complete。source IR JSON 不变。

局部输出点提供真实对象引用，保存后对最终包建立一次结构索引，冻结 part/元素类型（含实际 m:oMath 的 math 目标）/整数 locator、实际样式/section/尺寸。locator 只在该 docx_sha256 下有效；part 是受控包内路径，不是服务器路径或任意 XPath。不能逐 block 重扫全包、只靠对象计数、按正文相似度或源顺序反推 target。

- list item、table caption/context/table/note、image 的多个 annotation 各有 owner/role/item 顺序；两图共享段落仍分别拥有 drawing 子目标；annotation 生成的原生 OMML 子对象也必须有真实目标，不能只收 w:r 而漏掉数学节点。
- TOC 只写一次，后续 coalesced 必须指向真实代表；混合 list 逐 item 说明，不能用 coalesced/suppressed 隐藏正文丢失。
- 内容为空与对象未输出分开；实际创建的空 paragraph/heading/formula/list item 仍有 target，确无对象的空 list 才 not_emitted。
- 同页多个 header/footer/page_number 可合写同一目标；以物理 part+元素为贡献覆盖 owner，section 是最终引用集合。跨方向/continuous section 可能仍链接前一 part，清空复用同一 paragraph 也须撤销旧贡献、标 superseded；保留当前实际覆盖行为。
- disabled/custom/superseded/not_emitted 有有限原因；共享组、参与者和顺序可核对，不能任意扩大为 body 共用目标。图片对的题注检查段及左右片段来自同次真实writer捕获并冻结的不可变运行时ownership事实；合法题注tab可与delimiter有相同XML，单靠最终XML不能普适反推来源。验证器逐侧核对该事实和最终真实节点，不能由待验证targets自行决定边界；整体OMML集合相等不代替归属和覆盖。运行时事实仅属内部WordRenderResult，不写metadata/事件，不从trace自身hash推导，不改DOCX。
- IR-205 已验证 group/fragment/spans 只读投影，归并空片归原 render owner，不增加输出表格。legacy 自由 source_spans 不冒充 typed 已验证来源，缺失保持 unavailable/unknown。
- anchor_ref 是逻辑身份；bookmark_name 只记最终 XML 中实际存在的既有题注 bookmark，其余为空，不伪造 Word page。

### 三种投影与 receipt

完整 renderer evidence 保存到既有 generated_word.metadata 和正式 local result；不在新事件复制。旧 aggregate 比较投影与新 trace 的 available/unavailable 状态分开：历史主件恢复仍比较原全部可从 bytes 重算的证据、字节/hash、唯一性、归属、代数/IR及保留期，不要求新字段，也不回填或重渲染。

新 content/trace 在 register_result_candidate 前校验并冻结，prepare_result 选择首次有效 receipt。winner 的 bytes/hash/trace/descriptor 一致，loser 不替换；receipt 后只物化同一描述，不追加 metadata、不补 trace。保留 materialized_file 对完整 metadata 的严格比较、原 attempt/CAS/终态及原错误映射。

owner/Admin、tenant/company、当前引用/技术 Token/签名与 blocked/unreviewed 内部下载合同保持。

### 安全事件和公开摘要

安全投影是完整字段白名单，不能仅删除 render_plan/block_render_evidence。只输出明确数值/布尔、受控诊断码、版本/hash/status 和允许的后端身份；原 block IDs、自由 flags/source_type、latex_residue_examples、内部路径/object key、正文/译文、配置原文及未知 metadata 不进入 renderer/主件事件。

覆盖正常 stage_succeeded、异常载体/failure_evidence、receipt 后恢复的 file_registered；后者从选定 word_file metadata 投影，不能展开整份 metadata 或取 loser/当前配置。IR 同源 flags 的事件投影与 files quality_evidence 两 flags 列表复用受控码规则；存储原 metadata/质量判定不变。保留既有公开字段形状和 DOCX 数值白名单，不新增 HTTP/OpenAPI schema。只收窄相关新事件 payload，不清洗历史/其他域事件。

INPUT-006 已验收结构化安全报告/输入身份保留；其 Any 字段不因 Pydantic 同名 schema 存在就自动安全。只能经既有 owner 的明确来源与安全合同或受控投影保留，不信任任意同名 dict，不为脱敏删去已接受诊断或改变输入验证 owner。

metadata 仍为既有 JSON payload，无 DDL/backfill/file_type；不复制 raw source/HTML/Grid。记录样本 JSON bytes/targets，禁止静默截断后 complete。真实容量限制若要求迁移/独立 Artifact，先回规划，不临时扩建。

## 4. 验证与错误矩阵

| 条件 | 行为 |
|---|---|
| IR/resource/plan/DOCX 身份不符 | ir_render_evidence:binding_mismatch；当前渲染/quality_checking 的 render_failed，最终登记前停止。 |
| 重复 ID、主记录缺失/多余 | ir_render_evidence:block_coverage_mismatch，不重造 ID。 |
| 不存在/错误 owner/非法共享 target | ir_render_evidence:target_mismatch；受控 TOC/图片/decoration 分别验证。 |
| 版本、结构、有限数值或 JSON 编码无效 | ir_render_evidence:invalid_contract，消息仅固定码/数字索引，不回显输入或 ValidationError。 |
| 历史 metadata/bytes caller 无同次 trace | unavailable；原 aggregate/integrity 继续检查，不回填、不自动 passed。 |
| legacy 缺 typed spans | 保留 unknown，不猜造或为缺来源致失败。 |
| 原 source/layout/drawing/table/heading 丢失 | 原 blocker/失败关闭保持，不因 trace 放宽。 |
| 对象/metadata 登记故障 | 原 oss_failed/receipt 恢复语义，不降级 trace warning 后完成。 |
| 非阻断 OOXML 风险 | 原质量合同保持，不把全部 flags 升级 fatal，也不据此宣称视觉通过。 |

错误/日志/异常 evidence 使用安全投影，实际完整性判定仍依据完整证据；不能因过滤自由字符串而移除真实阻断条件。

## 5. 正常、历史与错误场景

- 正常：一次解析资源→纯计划→按计划写 Word 并收集局部引用→保存/冻结实证→完整性→候选+receipt→当前完成 CAS。local adapter 在最终 DOCX/IR 写出前检查。
- 历史：无 trace 的旧主件按稳定旧 aggregate 恢复，返回 unavailable，不重算缺失计划；receipt 重投 读取同一 immutable metadata。
- 错误：每个 block 随意挂同一段落、用源 section 推断 header retained、跳过空段落、先保存主件再核对、事件展开 word_file.metadata，或新入口迁移后仍只 patch bytes 断言无重渲染。

## 6. 必要测试与证据边界

- RenderPlan：重复构建/canonical JSON/hash、有效资源/语言/inherit、同次加载与 IR 不变；由实际 writer 消费的分支，不是 mock 返回常量。
- block evidence：正式保存后解析真实 XML；普通/双栏/图片对/表格 annotations/OMML/TOC/空对象；header/footer 合写、禁用/custom、跨方向+continuous 链接覆盖；IR-205 owner/spans 与 legacy 未知。
- 负例：错 hash、缺 block/重复 ID、伪 locator/错误共享、图片对纯/混合数学题注的漏目标/伪math种类/左右owner交换、串次及同实例连续/交错隔离；既有完整性负例仍失败。
- caller：真实生成件和 local result 同 hash；成功/失败/receipt 恢复事件的正文/自由 ID/flag/未知 metadata canary 不泄漏，安全计数/固定码/INPUT-006 报告仍在，files/incident/日志不透完整 trace。
- receipt/兼容：真实双渲染 winner 绑定、历史无 trace 恢复、receipt 后中断不渲染/补写、恢复保持完整 metadata；新入口 spy 必须命中实际路径，旧 bytes 参数/返回独立保护。
- 原 direct 零翻译资源、取消/旧代/终态、其他 blocked、批准发布/当前引用及下载权限回归；file/SQLite JSON 往返与 fake MySQL 合同按实际缺口选定向观察。
- committed OPA228 component 和当前候选 release/OpenAPI 门；Word/WPS、真实 InnoDB、部署 FS/生产引擎等未运行要明确披露，不用 OOXML/像素相似度替代。

不为触及共享文件重跑无关全库，也不靠增加重复 mock/覆盖率证明正确。真实外部验证须有明确环境/授权；本任务不部署、启用或安装本机 Office。

## 7. 错误与正确做法

错误：

```python
# 完整metadata既可能有trace，也有旧自由字段，不能展开到事件。
payload = {**word_file.metadata}
# 新builder的unavailable字段会误拒旧metadata，不能全量比较。
all(old.metadata.get(k) == v for k, v in build_renderer_evidence(ir, content).items())
```

正确：

```python
# 摘要从选定结果读取；旧件只比较稳定旧aggregate的全部原键。
payload = build_renderer_event_summary(word_file.metadata)
legacy = build_renderer_aggregate_evidence(ir, content)
all(old.metadata.get(k) == legacy[k] for k in LEGACY_RENDERER_EVIDENCE_KEYS)
```

新完整 trace 只能由同次结果构造，不能使用上述 legacy 路径去“重建”新件的 block 归属。回滚只停止新 trace 写入并保留兼容读者、metadata/主件/hash/审计，不回退丢字段旧 writer、不覆盖发布件或 DROP。

## 当前分支适配约束

本候选基于c56e128，业务文件仅19路径。执行器在当前TR-402/403/406上局部接线，保留integrity参数、专码和合法翻译事件字段，不能把renderer白名单套到全部翻译payload；正式本地adapter保留完整有序ID、重复JSON键拒绝及共享编码校验。完整私有trace保留原ID/引用，受控源账本和私有质量判定不裁剪，对外自由ID转计数、flags保留受控码，其余安全字段沿既有白名单。

本候选没有RND-504；历史来源中的预览兼容证据不能当作当前能力。未来验证必须绑定此隔离候选，未跑的真实Word/WPS、InnoDB、部署存储及大文档容量不因历史验收被标通过。
