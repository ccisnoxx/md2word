# RND-505 设计 v2

## 1. 基线与边界

依赖验收事实、根目录缺失项、恢复的归档身份及G0清单见research/dependency-baseline.md。renderer真实代码定位见research/renderer-baseline.md；preview/CAS/存储见research/preview-baseline.md。现根HEAD01e6c1ad不是可实施基线。G0必须把RND-501与RND-504组合并保留RND-502/503、TR/CON；不做整文件历史覆盖。

最小职责划分：renderer拥有实际block书签及独立可选锚点证明；既有RND-501拥有plan、来源投影、对象归属；`services/preview/page_mapping.py`拥有纯派生映射模型/算法/有界序列化；`document_jobs/preview.py`负责从已选receipt/预览构造身份与manifest。文件生命周期、CAS、权限仍由原owner负责，不新增服务层、仓储、Provider或队列。

首版只使用已验收PreviewResult.page_count，不改WordPreviewProvider签名、PreviewResult、executor v1协议、profile或部署配置。没有真实锚点→PDF页提取器；多页值都是低置信估计。这是对需求“提取或推断”的明确选择，不把未实现的精确提取留作隐含验收。

## 2. 数据流

```text
MinerU → 固定DocumentIR → 同次RenderPlan/真实输出对象
  → 写通用书签并保留同次成功对象引用 → 保存DOCX
  → freeze/认证原block evidence、公式/图片报告及独立可选锚点证明
  → 原candidate/receipt选定唯一主件（此后不变）
  → RND-504 claim → Provider结果验证 → begin_registration CAS
  → PDF/可选PNG登记 → 纯mapping构建 → 原manifest(page_mapping可选字段)
  → 原完整证据校验 → finish CAS → 当前受权manifest下载
```

所有映射计算与文件IO在job锁外；只借原finish把含映射的manifest选为当前。mapping不写quality_summary producer，不增加第二个job状态或独立安装指针。离线正式renderer只产书签与block evidence，无preview就不伪造页映射。

## 3. 通用书签

### 身份与位置

复用RND-501完整anchor_ref，不重建block ID。书签候选名为`md2w_blk_`加完整anchor digest的前30个十六进制字符（共39个ASCII字符，字母开头）。anchor_ref全长仍保存在原trace，短名只作DOCX局部locator，不作跨产物身份。

在单次collector内，所有writer输出完成后、最终save/freeze前，对实际LocalTarget统一物化；不在已经冻结的child_path或主件上后补。插入marker后，所有受影响locator必须由同次真实对象引用重新计算后统一冻结，不沿用插入前缓存的child_path/子节点范围。扫描已有名字和数字w:id，数字ID从已占用最大值之后分配，配对start/end；不改现有题注、公式、图片书签。不允许模板预占名或本次短名碰撞被误认为本块锚点：冲突只产生当次renderer受控diagnostic name_conflict，不写入旧trace的封闭Reason；不覆写模板，不靠书签名搜索正文。持久映射缺少可信创建证明时统一anchor_missing，不猜测历史根因。该映射降级不影响原内容；重复/空block ID仍由既有RenderPlan拒绝。

首个真实输出位置作为起点：段落/列表/公式定位到该对象前；表格优先自身真实caption/context，否则首个已有cell paragraph；图片使用本图cell内真实picture paragraph；不添加空段落、分页、run文本、可见标记或布局属性。共享输出/coalesced保留代表block关系；不生成假正文。跨段/跨页表的书签是起点，不代表完整范围。页眉页脚可在实际part里放书签，但不能因此声称只出现于某页。

RND-501 strict v1完全保留：`BlockRenderRecord.bookmark_name`仍等于既有targets后代书签去重后的首名，`targets.bookmark_names`仍仅投影该target后代，`reason_code`封闭集合、targets数量/role/类型和`word_page=None`均不改。不向图片targets追加伪caption、父paragraph或bookmark target；drawing的同段书签不在drawing后代中，必须经下述独立证明关联。通用书签碰巧成为旧首名只属于原XML投影事实，不能作为创建成功的证明。

### 3.1 独立可选锚点证明

新增`renderer/block_anchors.py`拥有`block-anchor-evidence/v1`及同次物化/校验逻辑。WordRenderResult增加可选block_anchor_evidence及仅运行期的创建对象归属；通过原build_renderer_evidence/主件登记链写入selected generated_word.metadata的可选同名对象。无新文件类型、job字段或状态。旧plan、block-render-evidence/v1及公式/图片报告保持原语义。

证明包含schema_version、input_ir_sha256、plan_sha256、docx_sha256、entries与自身canonical evidence_sha256。每个entry只记录本次成功新建的block_id、anchor_ref、bookmark_name、start/end的part/最终child_path及所定位的原内容target（part/最终child_path/role/item_index）；不复制正文或source spans。collector保留真实新建start/end和原输出对象引用，最终save后由这些引用冻结并独立认证，不能从待验证证明或名字反推本次创建事实。失败/冲突不写成功entry；配对插入失败时撤销本次尚未冻结marker，不留下半对标记。

段落/列表/公式在自身段落内定位；表格优先实际caption/context，否则首个已有cell paragraph；图片marker在其真实picture paragraph内。独立校验要求start/end同part、唯一配对、名称匹配稳定anchor候选、最终定位关系确实指向所声明target；图片须在同一真实paragraph且包围该drawing所属的实际run，不能仅以“同cell”或同名作为归属。该关系不把父paragraph提升为内容owner。共享/coalesced只复用原认证代表及其成功证明，不增加虚构内容targets。

模板预占expected名字即使位于目标内部，也不生成该block的成功证明。preview只采用receipt中已认证的独立证明，不凭namespace、旧bookmark_name或全包同名搜索升级为成功；无证明的旧trace仍可按页数推断但anchor_missing。name_conflict仅生成时可知，缺证明的持久读者不追认该原因。

证明在主件候选登记前随原metadata固定，receipt以后禁止补写。新增/三恢复入口必须保留并校验已有证明的IR/plan/DOCX绑定及真实配对/target关系，禁止恢复时按XML重新生成创建证明。证明缺失、未知版本、坏绑定或超限只令可选锚点不可用；原DOCX hash、IR/plan/block evidence、公式/图片内容认证仍按原规则fail-closed，不能被该局部降级吞掉。证明使用与映射相同的8MiB/100000条有界构建上限；超限不输出半份“完整证明”，省略该可选证明并给受控计数。独立证明校验不进入质量/发布贡献。

新增私有证明须从事件、file质量摘要、错误证据等公开出口显式剔除，仅允许受控计数/版本/status；不能依赖旧报告黑名单自然覆盖新键。主件metadata保留属于原文件JSON payload增量，不是新增数据库列。

RND-502公式、RND-503图片和RND-501内部ownership的locator/报告必须全部绑定最终带书签字节。新增marker不得把图片左右/各cell贡献混为一体；冻结顺序由统一基线核实，不能通过放宽认证断言适配。

## 4. 独立映射合同与载体

现有`word_preview_manifest` JSON Artifact中的可选`page_mapping`承载`pdf-ir-word-page-map/v1`，仍由原manifest完整hash和文件权限保护；不另登记sidecar或file_type。映射对象字段：

| 字段 | 语义 |
|---|---|
| schema_version / algorithm_version | pdf-ir-word-page-map/v1 / source-order-nearest/v1 |
| status / reason_code | available、degraded、unavailable；受控原因 |
| binding | source_pdf_file_id、document_ir_file_id、input_ir_sha256、plan_sha256、source_generation、result_file_id、docx_sha256、run_id、attempt、profile_sha256、preview_pdf_file_id/sha256、page_count |
| entries | 按实际输出序的逐block记录；保留原block_id、anchor_ref、bookmark_name（只从独立创建证明取得，可空）及disposition/representative |
| source | provenance_status、source_spans、layout_page_index/bbox；来源真实性与目标置信度分开 |
| location | kind=single_page/estimated_start/unavailable；preview_page_index可空，page_range=null；confidence=high/low/none、reason_code |
| fallback | 可空；仅导航用page_index/nearest_block_id/method，confidence=low；不得被当成本块实际对象命中 |
| counts / mapping_sha256 | 覆盖/分级计数；canonical JSON（排除自身hash）的完整SHA256 |

binding从已选receipt.file及已验证trace、当次run/已登记PDF取得，不能从请求传入或“最新可用文件”猜测；input_ir_sha256用RND-501既有canonical身份，不偷换成IR文件原始字节hash。plan/evidence/DOCX绑定已通过原认证；可选block_anchor_evidence另行校验，不把原record.bookmark_name当generic成功证据。不得把manifest自己的hash/file_id嵌进自身造成循环；run/attempt及外层选中manifest足以绑定。

typed IR-205 fragment spans保留原始JSON pointer、source_index、source_index_in_page、source_type、page_index/bbox及fragment/group/owner引用。legacy_layout只从已有projection输出布局定位（独立字段，不伪造原始pointer）；没有可信来源保持unavailable。禁止读取自由metadata.source_spans后升级verified，不把caption字符区间当PDF span。无需为本任务实施全类型源跨度规范化。

完整映射不含正文、HTML、译文、Prompt、临时路径、对象key、lease、请求reason或自由异常消息。已有公开files quality摘要继续白名单，不投影新完整mapping。未来前端以原授权文件下载读取；本任务不加HTTP查询或页面。

### 4.1 可用/不可用形状与读者

所有对象都有schema_version、algorithm_version、status、reason_code、binding、entries、counts、mapping_sha256。binding分两层：source/run基本身份（generation/result ID/hash、run/attempt/profile）来自已通过RND-504的主件与当次run，始终必需；IR/plan/source_pdf身份仅在原选定主件metadata可证明时填写，否则null，不能用当前任务新IR或空字符串代替。成功预览有PDF ID/hash和P；失败/unavailable预览的三项为null，不能附加成功页或虚构文件。Provider失败时沿RND-504原失败路径，不为保存这个不可用结果新建manifest或登记文件；此形状仅用于纯映射结果/已授权内部读者返回。已成功生成预览但旧主件缺trace时，才可在该次原manifest中写入不可用对象。

available/degraded要求IR/plan/PDF完整绑定、已认证block evidence与P>0；没有trace的历史件或preview失败使用unavailable、entries=[]，counts.total=null表示数量未知，保留可证明的基本身份与受控原因。成功预览且完整trace未超预算但没有正文候选时，保留全部已认证block entries，status=unavailable/reason=no_target，每项location为unavailable对象、fallback=null，total为可证明计数。超限则小型unavailable/entries=[]，total仅填可证明计数；不为了保留entry全量而突破预算。无trace时不从DOCX正文反向重建block ID。

报告status：存在至少一条正文定位且任何定位为估计/缺锚/未覆盖正文则degraded；所有应输出正文均单页证明且通用锚可用为available（非输出/装饰条目按其合法disposition排除，不虚构成功）；没有任何正文可定位为unavailable。location.confidence只说明页定位证据，source.provenance独立。

独立reader在preview.py的已验证manifest body上消费；结果仅用于内部映射视图/安全摘要，不修改存储字节、外层manifest版本或现有preview可用性。现有下载仍提供原不可变manifest，新客户端应按内层schema解释，未知版本只能显示不可用，不能把原始字段当可信精确页。不会新增GET写入或重计算副作用。

## 5. 页推断与降级（确定性规则）

`P`只取已验证成功预览page_count，零基有效页集合为0..P-1。source PDF页、Word显示页码、section_index不可互换。

1. 建立实际正文目标顺序：使用同次plan.operations及最终document.xml内真实targets的顺序，去重block owner。整数child_path只在同part比较，header/footer不混入。mapping应用侧从已持久化plan/trace获取此顺序，不读取IR.order冒充布局后的顺序。coalesced跟随真实代表；循环或未知代表使该映射不可用，不改IR。
2. 对有真实正文目标且P=1的block，location=(single_page,0,high)。这只证明目标页，不提升source provenance，也不证明坐标/视觉。suppressed/not_emitted/superseded不适用；重复页眉页脚仍无唯一location。
3. P>1且有来源页：取该block最早可信source span页，否则legacy layout页；权威源页集合固定为plan.sections[*].source_page_indices中非负页索引的去重升序，不含legacy_v1_fallback的人造布局页（该模式集合为空）；不从自由source_spans补页，也不把section顺序当页序。在集合内取rank=r，总数S。S>1时选最接近`r*(P-1)/(S-1)`的合法页，平局选较小页。字段为estimated_start，confidence=low，reason=source_page_ratio；多span只估起点，page_range始终null。稀疏源页按rank而不是除以最大页号。source page不在权威集合中不能夹逼为“可信”，转缺来源。
4. S≤1时来源页不能区分多页预览，保留原source/provenance，但所有正文owner按本步输出序比例定位，reason=source_page_rank_degenerate。S>1时，对无可用自身来源的真实正文block，优先从步骤3的直接来源估计集合找实际输出序距离最近者，平局选前者，不把fallback再递归当新证据；location为estimated_start/low/reason=nearest_output，记录nearest_block_id。没有任何来源估计时，在T个真实正文owner中按顺序q估计最近`q*(P-1)/(T-1)`；T=1选择0，比例舍入平局也选较小页，reason=output_order_ratio/low。这是导航估计，不是实际排版测量，可能偏差较大。
5. 缺通用bookmark但仍有已认证正文target时允许上述页估计并记anchor_missing；source证据真实度不变。coalesced可借代表的marker/位置并明确representative，不能声称自身单独输出。
6. header/footer/repeated/suppressed/superseded/not_emitted保持location对象（kind=unavailable、preview_page_index=null、page_range=null、confidence=none）及原disposition；如有来源页或代表可按上述已有正文候选给fallback（最近源rank，平局取实际输出序前者；无rank则仅可靠代表，否则无fallback）。fallback永远low、不伪造正文target。
7. 无成功预览/P缺失，或没有trace可消费：按4.1返回小型unavailable报告和entries=[]，不新建失败预览manifest。成功预览且有完整有界trace但没有任何正文候选时，保留全部entries与其source/owner/disposition，报告unavailable/no_target，每项location为unavailable对象、fallback=null，counts.total为已证明数量。主件identity/trace损坏不得运行此兜底掩盖，走原完整性拒绝路径。

不以页码缓存、lastRenderedPageBreak、硬分页符数量、标题相似度或PDF文字猜“真实Word页”。不为提高估计精度改变分页策略或重新渲染。

## 6. 容量、局部错误与可观测性

采用固定有界映射JSON预算8 MiB、最多100000条entry；不新增业务配置。预算针对mapping新增内容，逐项编码累计，source spans总字节计入，不先构造无限制大字符串；原preview输出/输入上限保持。超限不静默截断为complete，保存小型unavailable/limit_exceeded及总计数，既有preview PDF不受影响。源数量、schema、identity、有限数值在可信trace消费边界一次检查，内部纯函数依赖已验证类型。

可预期映射错误码：legacy_evidence_missing、anchor_missing、source_unavailable、no_target、preview_unavailable、unsupported_version、invalid_mapping、limit_exceeded。算法未预期异常在mapping局部边界转unavailable/unexpected_error并记录安全error日志/trace ID；不吞主件读取、Provider、文件登记、原证据认证异常，不捕获BaseException。该局部隔离有明确非阻断映射要求，不扩大成泛化catch/retry框架。

读取映射：在原preview/source/文件hash与授权通过后，独立校验mapping schema/hash/binding；未知/坏mapping只返回mapping不可用，不使原有效preview失效，也不自动落库或新跑Provider。manifest本身checksum错误仍原fail-closed，不能把原文件损坏降级。整份manifest存储失败沿uploading/oss_failed；独立retry保留执行终态并显式报错，这与“映射推断失败非阻断”不同。

复用现有preview事件，可附加仅计数/版本/status/受控reason的mapping_summary；不记录完整map/自由block ID。发布资格、quality contribution、review与delivery均不读取mapping status/confidence。

## 7. 幂等、并发、generation与不可变

映射只在当前attempt建manifest时计算一次；同一已确认run重放返回原manifest，成功alias复用原映射，不重新跑renderer/Provider。重新预览得到新run/attempt/PDF/manifest，旧文件保留，不能覆盖。原begin_registration与finish的source/current/revision/attempt/lease CAS防止旧计算成为当前；并发loser可留下自身原协议候选，由已有保留期处理，不增加跨job/file/object事务承诺。

Mapping binding随run身份变化，稳定block ID本身不足以跨generation复用。cancel/归档/删除/published和换代后的迟到结果按原规则拒绝。Token签发/读取复核完整当前预览；S3 TTL仍受manifest/PDF/必需pages/主件最短有效期限制，旧URL不承诺即时撤销。不重写选定主件metadata、历史manifest或PublicationRecord。

## 8. API、DB、配置、前端影响与兼容

- 无新API路由/response model/权限角色/file_type；现有manifest内容合同增加可选对象，在文档注明。OpenAPI预期不变，运行快照检查证明，不手工改快照掩盖漂移。
- 无DocumentIR schema升级，无SQL列/表/DDL/backfill，无新增job持久化字段。直接复用已有preview manifest指针和file metadata；文件payload不存DB全文。
- 不改Provider协议、运行时开关、策略快照、引擎/字体部署；生产仍disabled。
- 历史manifest无page_mapping表示旧版缺证据；旧主DOCX无新书签/trace不回填、不重渲染，合法下载和历史aggregate全23键/公式图片原恢复合同继续。
- word-preview/v1旧dict读者忽略可选键；新读者严格校验内层独立schema及可选锚点证明。必须实际做旧读者读取新manifest/新读者读取旧manifest，不能仅凭“additive”宣称兼容。
- 不改前端三栏。依赖集成后若发现现有客户端对manifest额外键做strict校验，停下补兼容设计，不偷偷改变协议版本。

## 9. 安全与回滚

映射不发外网请求，不新增SDK/依赖，不访问源PDF解析入口；只使用已授权主件、IR事实和预览。内部完整ID/坐标仍按客户数据保护，事件不回显。书签固定ASCII digest，数字ID由renderer分配，不把用户ID拼为XML/XPath或路径。ZIP/XML与对象路径读取沿现有验证，不放松沙箱、权限、技术Token和内容认证。

回滚点R0是人工认可的统一依赖基线；不能退回当前缺依赖根目录。新产物写出后R1为能读取/保留新marker、独立block_anchor_evidence及mapping附加对象且通过RND502/503/receipt恢复认证的兼容版本。回滚停止新通用marker/mapping生成、保留读取和已写Artifact，不删除历史，不清quality blocker，不覆盖主件/发布件。B0指R0统一依赖基线，B1指可读取新增产物的兼容回退版本。B1必须保留选定主件的可选证明字节、不得删除/重算，并在三恢复入口和所有公开摘要出口执行同等隔离规则。B0若丢失证明、拒绝新marker或泄露私有新键，即不具备新产物回退资格；须先形成B1兼容读者，再启用新写入。只有B0/B1交叉恢复实证通过才可声明代码回退安全；若新书签影响旧reader需保留兼容reader，不能假定旧二进制安全。

停止条件：原用户列出的依赖未验收/冻结文档冲突/破坏性迁移或历史覆写/冻结模式下载发布规则变化/无法用fake与adapter替代的授权缺失。另含G0无法在批准范围闭合、来源只能靠猜测、真实精确分页需求超出当前推断版。任何此类变化先回规划。
