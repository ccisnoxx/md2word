# PDF / IR / Word页映射合同

本合同属于RND-505批准v2。唯一实现owner：`app/services/preview/page_mapping.py`；实际书签及独立创建证明由`app/services/renderer/block_anchors.py`拥有，主件/预览身份与生命周期由既有DocumentJob执行及preview应用层拥有。映射是导航派生证据，不参与quality、review、delivery或发布判定。

## 载体和版本

现有`word-preview/v1` manifest增加可选`page_mapping`，独立`schema_version=pdf-ir-word-page-map/v1`、`algorithm_version=source-order-nearest/v1`。不增加文件类型、HTTP路由、数据库列、Provider协议或配置开关。旧manifest缺字段合法，新读者返回映射不可用；完整manifest沿原hash/权限/当前引用认证。

内层对象包含status（available/degraded/unavailable）、受控reason_code、binding、entries、counts、mapping_sha256。mapping_sha256是排除该字段后的UTF-8 canonical JSON完整SHA256：键排序、无多余分隔空白、ensure_ascii=false、拒绝非有限数；最多8MiB、100000条entry，预算耗尽整体不可用，不截断后声称完整。

## 稳定身份和binding

稳定block_id及anchor_ref来自同一固定DocumentIR/RenderPlan，不以输出序号重建，也不承诺跨重新解析或generation复用。binding必须来自原已选receipt、已认证trace、当次run与已登记预览PDF，不采信请求提供的自由ID或最新文件猜测。

| 字段 | 约束 |
|---|---|
| source_generation / result_file_id / docx_sha256 | 固定同一选定主件；generation非负，ID非空 |
| run_id / attempt / profile_sha256 | 同一次预览运行；attempt至少1 |
| source_pdf_file_id / document_ir_file_id | 仅填已选主件元数据可证明的来源，否则null |
| input_ir_sha256 / plan_sha256 | RND-501既有canonical身份；不能用IR文件原始字节hash替换 |
| preview_pdf_file_id / preview_pdf_sha256 / page_count | 成功预览三项同时存在，page_count至少1；无成功预览时同时null |

文件、DOCX和profile hash沿既有`sha256:<64hex>`格式；IR/plan/mapping hash是裸64hex。不在对象内嵌外层manifest自己的hash/ID造成循环。可用/降级结果必须绑定已认证IR/plan及成功PDF；无trace不反向重建block。

## entry及来源

entry保留block_id、anchor_ref、disposition、representative_block_id；bookmark_name仅来自独立成功创建证明，可空，缺锚用anchor_reason_code=anchor_missing。不得凭旧record.bookmark_name、命名空间或模板同名升级为创建成功。

source包含provenance_status、source_spans、logical_group_id、fragment_ids、layout_page_index、bbox。verified_ir205保留typed fragment的原JSON pointer、source_index/source_index_in_page、source_type、页/坐标和owner关系。legacy_layout只表示已有布局定位，不冒充原始span；自由metadata不能升级verified，题注字符区间也不是PDF span。来源真实性和目标页confidence相互独立。

location恒为对象：kind为single_page/estimated_start/unavailable，preview_page_index零基且可空，page_range始终null，confidence为high/low/none；reason_code说明算法，nearest_output同时携带nearest_block_id。fallback可空，含page_index、nearest_block_id、method及固定low，仅供导航，不表示本块实际输出命中。counts记录total、located、high、low、anchor_available；无法证明块数时total=null。

## 推断规则

先按最终document.xml内容target顺序建立真实正文owner，不将IR数组顺序或跨part的child_path当实际页序。coalesced跟随已认证代表；认证必须将record.representative_block_id与plan.text_policies及真实TOC target owner对账，不能只验证target后继续信任自由代表字段。没有归并策略的记录不得凭空携带代表；合法混合列表保留collector按item顺序记录的最后一个归并代表及其独立正文。非空native_text策略的disposition还须与实际独立输出一致：存在自有target为rendered，全部归并为coalesced；空列表沿原规则认证。循环/未知/错绑代表不能成为导航证据，坏可选trace仅使映射不可用。

1. 成功PDF只有一页且block存在真实正文目标：page0/high；不提升source provenance。
2. 多页时权威源页集合取plan.sections[*].source_page_indices的非负去重升序；legacy_v1_fallback不使用人造源页。S>1时以最早可信source页（否则legacy布局页）的rank r估计最近的r*(P-1)/(S-1)，平局取较小页，统一low。
3. S≤1无法区分多页位置，按T个真实正文owner的输出rank q估计q*(P-1)/(T-1)，T=1取0，平局取较小页，reason=source_page_rank_degenerate。
4. S>1但本块无可用来源时，借输出序距离最近的直接来源估计；平局取前者，不递归放大fallback。没有直接来源估计则按输出序比例估计，reason=output_order_ratio。
5. 长表、多span只估起点，range=null；header/footer/repeated/suppressed/superseded/not_emitted保持location不可用，可按已认证正文候选给low导航fallback。

固定示例：S=3/P=5→0/2/4；S=1/P=5/T=3→0/2/4且low；无来源T=3/P=2→0/0/1；单owner多页→0/low。以上多页值是导航估计，不是引擎测得的Word实际分页，不承诺像素或跨页完整范围。

成功预览+完整有界trace但没有正文候选时保留全部entry的source/owner/disposition，报告unavailable/no_target，各location不可用、fallback=null，total为已证明数量。无trace、无成功预览或超预算使用小型entries=[]；Provider失败不为保存不可用映射创建新manifest或文件。

## 独立锚点创建证明

`block-anchor-evidence/v1`是selected generated_word.metadata内可选私有证据，不修改RND-501 strict v1首名、targets数量/role、封闭Reason或word_page=None。collector仅记录同次成功新建的start/end及原目标对象引用，最终save后冻结IR/plan/DOCX身份、最终part/child_path和配对/归属。图片marker在真实paragraph内包围drawing所属run，不将父paragraph提升为内容owner。

模板预占名字即使在目标内部也不产生成功entry；name_conflict仅为生成时受控diagnostic，持久读者缺证明统一缺锚。证明随原候选登记前固定，receipt后不补写、不按名字重建创建事实。保留所有公式/图片原marker及最终报告认证。

## 失败、隐私和生命周期

可选证明或映射缺失、未知版本、坏内层binding/hash、缺锚和超限只使导航降级或不可用，不改变内容与既有状态。合法历史主件的持久trace只供新增映射认证，不能凭新增可选校验建立旧主件下载的新阻断门。原主件字节/hash、公式/图片报告、aggregate、权限及原manifest文件损坏继续原失败关闭；真实存储/Provider失败不得被纯映射降级吞掉。可选原IR明确缺失、过期或不在主件scope内时仅映射不可用，跨scope不读字节；未知存储失败、IR原始字节与描述符不一致仍显式报错，不能冒充缺证据。

复用原claim、begin_registration、finish CAS、generation/run/attempt/lease和最短TTL；重放/成功alias返回原manifest不重新计算；旧结果迟到不成为当前。旧DOCX、IR、manifest和发布件均不回填/覆写。完整证明与映射包含内部身份/坐标，事件、API摘要和错误出口仅允许受控版本/status/reason/计数，不输出正文、自由ID、路径、对象key或私有lease。

## 兼容和回退门

G0组合基线来源与指纹见当前Trellis任务的g0-integration.md、g0-source-fingerprints.json和g0-review.md；不以历史单分支测试替代组合证据。

带新marker/证明的产物写出后只能退至B1兼容读者：它必须停止新marker/mapping生成，同时保留已有证明字节，在三恢复入口保留原内容认证并正确隔离可选导航失败，且不泄露新增私有键。原G0/B0若拒绝新marker、丢弃证明或泄露字段即不具备回退资格。新写入前必须有旧/新manifest互读、带marker DOCX恢复及无泄漏的实证与B1源码指纹。不得删除Artifact、历史审计或批准记录来实现回退。

真实Word/WPS、Golden、生产预览沙箱/字体及真实InnoDB/部署存储证据须单独记录；离线算法或fake测试不代替这些环境门，生产预览保持disabled。
