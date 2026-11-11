# 产品 Manifest 45 项只读对账

日期：2026-11-10。范围：当前工作区静态源码、原 backlog AC、现存归档和相关 Git 对象。原 Manifest 为 8 done / 37 todo，本记录不改变任何执行字段、依赖、路径或人工接受门。

## 证据解释

- 每行“原 AC”链接到任务定义，不把源码符号或任务目录存在当作 AC 通过。结论为研究判断，不是可执行状态或新的依赖门。
- 当前源码事实与历史报告声明分列；未运行应用测试、构建、发布聚合器、真实 Provider、Word、数据库、队列或生产访问。报告中的测试次数均为原记录，不能当本轮结果。
- Git 中可读到的 completed/人工接受仅适用于其原实现、分支和接受范围。所核对的一组原工作提交不在当前 HEAD 祖先链上；这不证明源码未集成。当前字节身份与具体调用仍需独立比对，不能把“不可达”直接当缺功能。
- 对当前缺失路径的观察只限下文精确文件；没有精确任务目录或类名不能证明能力未实现。REL/QA-607 的无命中是有界检索结果，保留不确定性。
- `H-任务ID` 对应下方可用 `git show <完整提交>:<路径>` 读取的历史对象；不制造指向当前不存在文件的本地链接。当前8项done的精确归档在Manifest给定路径。

## 逐项对账

| 任务 | 原状态 | 原 AC | 当前源码入口与局部结论 | 记录/验收证据 | 具体未决项与建议 |
|---|---|---|---|---|---|
| DOC-001 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#doc-001-合入文档包和索引) | README.md、docs/README.md、DOCUMENTATION-MANIFEST.md 已有导航/权威关系；B1 新增治理入口。 | 原归档 task.json 的 human_acceptance 与 validation.md 已读取。 | 原交付是文档包，保持 done；本轮导航迁移不表示目标功能已上线。 |
| BAS-001 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#bas-001-当前能力与测试基线核验) | baseline-verification-2026-10-12.md 交付六项当时能力事实与命令账本。 | 原归档 completed/human_acceptance；报告基线 fcea60ff，接受日期 2026-10-12。 | 保持 done；报告中的“无预览/无发布”等历史判断需与当前源码区分，不能用旧测试认证当前版本。 |
| CON-101 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#con-101-产品模式和-ui-文案收口) | translation/modes.py、前端模式/资源显隐入口仍在；B1 未改业务。 | 原归档 completed，meta 明确人工接受 AC1–AC8 与残余风险。 | 保持 done；原全 smoke mock 缺口、真实 DB/Word 未验继续保留，不重跑。 |
| CON-102 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#con-102-执行阶段扩展) | document_jobs/models.py 定义三个扩展阶段；execution.py 与翻译协作者承担阶段推进。 | H-CON-102 记录 completed、人工接受及 52810b61/4d306826 两笔工作提交。 | 有实现且有历史接受声明，登记可能滞后；仍需对齐当前 receipt/失败阶段、旧记录和前端版本，不能仅凭枚举改 done。 |
| CON-103 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#con-103-质量复核交付状态模型) | DocumentJobRecord 的 quality/review/delivery/summary 字段；migrate_document_job_state.py 具局部迁移入口。 | H-CON-103 completed/人工接受；bd828da4、80b82dbc。 | 有实现和历史接受；真实 MySQL/部署文件系统、迁移回滚及当前全链 AC 未重新验证，保留 todo 待人工对账。 |
| CON-104 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#con-104-下载和发布可用性合同) | router.py 的下载授权响应包含 classification/warning；service.py 与 review/publication owner 管理后端资格。 | H-CON-104 completed，记录 2026-10-20 人工接受。 | 有后端合同；blocked/unreviewed/Admin 三场景需按当前源与记录逐项确认，不用“publish 字段存在”代替 AC。 |
| IR-201 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#ir-201-mineruartifactvalidator) | MinerUToDocumentIRService.convert_zip 先运行 MinerUArtifactValidator，再转换；包安全由 mineru_package.py 维护。 | H-IR-201 completed；human-acceptance.md/validation.md 保留原补强和原子更新范围。 | 有实现/历史接受；真实多 Worker、MySQL、部署文件系统及 Word 边界未补证；与旧版本重复任务记录要先辨版本。 |
| IR-202 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#ir-202-marginartifactnormalizer) | 当前 converter 仍按 source_type 投影角色；历史 margin_artifact_normalizer.py 路径不存在，当前调用未见同名规范化入口。 | H-IR-202 validation.md 记录人工接受；e5e64c01 曾加入专门 normalizer。 | 确认历史实现与当前路径有集成差异；跨页重复/位置/原 source metadata 的原 AC 不能视为当前已满足，先比较历史增量，勿重复设计。 |
| IR-203 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#ir-203-crosspageparagraphmerger) | layout_signals.find_merged_paragraphs 对账 MinerU 已合并正文，供 validator 豁免残留空段；不是独立跨页 merger 完成证明。 | H-IR-203 是 in_progress；implement.md 仅记实现接受/本地提交，真实正向样本与 Word 未验。 | 部分相关能力；需确认原 source_spans、29–30/40–41 正向样本与实际合并规则，不能把上游合并证据当全部 AC。 |
| IR-204 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#ir-204-captionreconciler-增强) | converter 调用 reconcile_captions，uncertain 追加 caption_binding_uncertain；合同记录原值/来源。 | H-IR-204 completed/closeout；当前 RND-503 归档亦记录 IR-204 依赖整合。 | 有实现/历史接受；图5/6、24/25 的具体候选/来源与当前版本仍须关联，不把局部重绑定外推全部 caption。 |
| IR-205 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#ir-205-logicaltablegroup-与-source-spans) | capture_table_sources、attach_logical_table_groups 与 SourceSpan/LogicalTableGroup 模型已接 converter。 | H-IR-205 completed/acceptance，原真实表3/9/10/24和客户端未复验边界保留。 | 有实现/历史接受；logical_group、fragment、continuation/header hint 的当前版本与样本证据需对齐。 |
| IR-206 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#ir-206-table-reference-asset) | attach_table_references 与 table-references 授权 API 存在，源 hash/fragment 绑定由 table_reference_assets.py 解码。 | H-IR-206 acceptance.md 记录接受与40文件提交授权，但该 task.json 仍 in_progress。 | 同时存在记录阶段差异与实现；核对登记/缺图警告/授权显示的当前集成后再提状态建议，禁止由归档缺失判未实现。 |
| IR-207 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#ir-207-zk7044-最小回归样本) | component_pdf_samples/manifest.yaml、source-redacted 的 zk7044-caption-pair fixture 可定位；未声称覆盖全部风险页组。 | Git 349bd759 的 TAB-305 依赖复用记录引用已接受 180c90a；本次有界检索未定位精确 IR-207 task.json。 | 证据不足：原允许使用/非专有来源、最小页组风险与离线 runner 全覆盖待核对；不由无目录判断任务未做。 |
| TAB-301 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-301-canonicaltablegrid-模型) | services/tables/models.py 的 TableGrid/TableCell/CellRun、make_cell_id/make_run_id、raw HTML hash/模型校验存在。 | H-TAB-301 completed，validation/人工接受记录；c71c7caa。 | 有模型/历史接受；当前序列化与下游接线仍按具体版本核验，不能由类名判 roundtrip 等全部通过。 |
| TAB-302 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-302-html-normalizergrid-builder) | build_table_grid/build_render_table_grid 共用 _build_table_grid；调用 normalizer 并绑定 raw/source hash。 | H-TAB-302 completed/人工接受；原471126c8与集成1dbb2059应区别。 | 有实现/历史接受；sup/sub/br/formula 与冲突诊断的当前版本、raw 保留及稳定ID不能由历史单测自动认证。 |
| TAB-303 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-303-table-validatorquality-flags) | validate_table 会重新构建核对 grid/diagnostics；validate_document_tables 形成可聚合贡献。 | H-TAB-303 completed/closeout/validation；5bb6baab。 | 有实现/历史接受；只标记不修改、策略分级与当前任务聚合需对齐，真实误报率未在本批验证。 |
| TAB-304 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-304-大表保留合并关系) | word_renderer 构建 content table plan，logical_table 操作走 _render_native_unit；table_renderer 有 iter_grid_rows/vMerge。 | H-TAB-304 completed，记录大表保 merge；AC6 性能只部分证实。 | 有原生路径；旧 expanded 分支仍存在，需分版本/输入域确认默认策略；不能宣称内存降低，Word 和超大表性能边界保留。 |
| TAB-305 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-305-跨页逻辑表-word-渲染) | logical_table_plan 由 group/fragment 生成单元，word_renderer 消费 logical_table 操作；实物 evidence 核对 fragment/header。 | H-TAB-305 completed/closeout；历史 aa150c89 与 IR-207 overlay 需分开。 | 有实现/历史接受；表10/24、caption一次、重复表头与自然分页的当前制品/Word证据仍需绑定。 |
| TAB-306 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-306-空-html-内部占位和-blocked) | converter.prepare_placeholders 与 table_placeholder.py；renderer/evidence、后端下载/发布规则已有相邻入口。 | H-TAB-306 completed，3ebfb7a7 与 closeout/implementation-validation。 | 有实现/历史接受；reference/PDF+bbox两分支及 blocked/download/publish 跨层 AC 未在本轮运行。 |
| TAB-307 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-307-表格-evidence-聚合) | table_content_evidence 从实际 DOCX 表/marker/row/span 重建，并复用 tables.evidence/validator/reference owner。 | H-TAB-307 completed/人工接受；228f4033/142fe5f0，历史验证记录分列基线失败。 | 有报告聚合入口；当前 source/report/result 绑定与全部 table级字段仍需对齐，不把 expected 报告当独立实物证明。 |
| TAB-308 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tab-308-表格专项回归门禁) | 当前 component runner 存在，但 scripts/dev/table_regression_gate.py 与 table-gate-expectations.json 路径未保留。 | H-TAB-308 completed/closeout；71a542de 曾接离线 gate、OPA P6/P7 与 release。 | 确认原 gate 的集成差异；当前 runner 不证明专项合并/空HTML/blocked发布负例均进 release；先按历史差异确认恢复范围。 |
| TR-401 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tr-401-captionfootnote-翻译覆盖) | extract_translation_items 只追加 text/list/html；apply_replacements 只回填这三类，未见显式 captions/footnotes 字段分支。 | H-TR-401 completed，acceptance-audit-supplement 与 ae3e49ca。 | 确认历史接受与当前显式 annotation 入口有差异；text 副本不能当 annotation 全覆盖，先比对原实现和稳定ID，勿直接改状态。 |
| TR-402 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tr-402-protectedtokencodec) | protected_tokens.py 的纯内存 encode/decode 由共享 Validator 使用，B1 已记录不变调用身份。 | 当前精确归档 completed/human_acceptance；24ed6a71；历史本地24+32项和限制。 | 保持 done；有限语法、真实 Provider 与语义质量边界不因文档迁移扩大。 |
| TR-403 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tr-403-translationintegrityvalidator) | integrity.prepare/validate/validate_persisted 及共享请求、fan-in 入口，B1 工作区身份可复用。 | 当前精确归档 completed/human_acceptance 与 closeout；f46a3bcf。 | 保持 done；新翻译协作者仍是未提交工作区，真实存储/Provider及有限语法外能力未认证。 |
| TR-404 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tr-404-tablecontextbuilder) | TableContextBuilder + table_contexts 输入；Settings 默认关闭，app/main.py 注入，原 item 输出仍 id/text。 | H-TR-404 completed/人工接受；当前 B06 active 记录61项结构验证，明确未人工语义验收。 | 有当前接入与两类历史；当前缺所属章节/表题等原目标的充分证据，短文本语义改善、开启及全AC待验，保持 todo。 |
| TR-405 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tr-405-术语和目标语言后验检查) | 当前有术语匹配/forbidden_translations配置字段，但 post_validation.py/post_validation_rules.py 路径不存在，Validator 仍是技术完整性。 | H-TR-405 completed/implementation-validation，46248866 曾加入术语/目标语言后验。 | 确认历史实现与当前模块/调用集成差异；配置存在不能证明 mandatory/forbidden/语言残留已执行，先比较历史增量。 |
| TR-406 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tr-406-部分批次失败语义收口) | 当前 translation_execution.py 承担批次准备/校验/终态和 fan-in；execution.py 组合协作者，B1 记录脏源码身份。 | 当前精确归档 completed/人工接受；0946326b依赖、6d89c7e0功能提交。 | 保持 done；真实 MySQL/InnoDB/部署文件锁门与当前提取的等效性不能由旧测试自动通过。 |
| TR-407 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#tr-407-四语言方向样本和门禁) | 当前 matrix 的 ALL_MODES 为 direct/en2zh/ru2zh；无四方向 translation_samples manifest/gate路径。 | H-TR-407 是 in_progress，implementation-checkpoint 已接受并授权56路径提交；de4efc2d是实施提交，非四方向实译签字。 | 确认四方向离线套件集成差异；四方向真实模型/人工记录仍无本批证据，不能以P1 en2zh代替。 |
| RND-501 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rnd-501-renderplan-与-block-evidence) | render_plan.py 与 word_renderer 的计划/operation/evidence路径已存在；block_evidence/内容合同相邻接入。 | H-RND-501 completed/closeout，69906a5e 是当前整合记录，另有旧 da3ca610。 | 有实现/历史接受；应按当前 renderer内容v2核对 block→Word证据，不能只据旧提交不可达判缺功能。 |
| RND-502 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rnd-502-公式-omml-和降级规则) | 共享 docx_rules/formula.py 与 renderer 同次公式报告/内容证据 owner；B2 保留专项设计细节。 | 当前精确归档 completed/final_acceptance，136802cb；311定向等是历史声明。 | 保持 done；Word、Golden、真实MySQL/S3等原未验范围保留，历史报告不变成当前实跑。 |
| RND-503 | done | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rnd-503-图片并排和-caption) | word_renderer 消费 image span，layout_plan/image_evidence 管理图片组、来源和恢复证据。 | 当前精确归档 completed/closeout，67bc26db 与 e1f5079b依赖；原Word/部署预览未验被接受。 | 保持 done；不把 LibreOffice/OOXML 记录扩大成 Microsoft Word 或部署预览通过。 |
| RND-504 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rnd-504-wordpreviewprovider) | WordPreviewProvider 协议、SandboxWordPreviewProvider 与 DocumentJobPreviewService 注册/重试；默认disabled且需批准profile。 | H-RND-504 completed/closeout，历史8fa11d97与整合27e9b1a4有别，生产启用未授权。 | 有实现/历史接受；launcher/profile/隔离保证与实际预览制品未核验，不能把协议存在判生产可用。 |
| RND-505 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rnd-505-pdfirword-页映射) | page_mapping.py 定义 binding/anchor/location 与 unavailable/nearest 映射，preview.py 消费映射。 | H-RND-505 completed/closeout；850c0090 的G0整合与旧 f8257078 不同。 | 有实现/历史接受；实际预览 bookmark 跨页定位/外部引擎恢复未在本轮验证，不能把近似页当精准定位。 |
| RND-506 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rnd-506-页级-docx-质量检查) | page_quality.py/observer/policy 与 preview.py 的 _observe_page_quality 存在。 | H-RND-506 completed/closeout；接受记录保留基线失败、外部未验边界。 | 有框架与检查入口；各裁切/溢出/空白/重叠/密度规则的校准与真实客户端证据需按策略逐项对齐。 |
| QA-601 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#qa-601-统一-review-模型) | review.submit_review 追加记录，result/generation/receipt绑定、blocked批准拒绝及旧translation投影；专用迁移脚本存在。 | H-QA-601 completed/人工接受；591ba6c1当前整合与26174ae0历史版本有别。 | 有实现/历史接受；真实持久化迁移、当前hash失效和direct/translation全入口仍需按版本核验。 |
| QA-602 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#qa-602-qualityreview-api) | router 的局部 quality_review_router 提供quality/tables/pages/preview/review/history/PATCH并 include_router。 | H-QA-602 completed/acceptance/closeout；原G0和历史 harness失败单列。 | 有API入口；当前router为既有脏文件，授权/错误/分页/来源绑定与OpenAPI全合同没有新运行证据，保留 todo。 |
| QA-603 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#qa-603-三栏审核页面) | 当前有 review/blocks API与旧 TranslationResultQaPage；DocumentReviewPage.vue、documentReview.ts及专用三栏组件路径不存在。 | H-QA-603 completed/closeout；1806580a曾接三栏，最后F6静态修正后未重跑的接受边界保留。 | 确认历史UI与当前集成差异；不能用后端block API或旧QA面板代表三栏同步，只读与定位需独立核验。 |
| QA-604 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#qa-604-下载状态提示) | useJobDetailActions.handleDownload 直接生成/打开链接后显示后端 notice；本函数未见下载前确认步骤。 | H-QA-604 completed/acceptance，fb17538b；原授权明确不合回根业务。 | 当前有warning展示但详情入口确认行为与历史AC有差异；其他下载入口待核对，不能宣称全UI通过。 |
| QA-605 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#qa-605-publicationrecord-和发布门禁) | publication.commit_publication 检查result/quality/review/preview并拒绝同代重复，service/router含Admin发布和最终下载。 | H-QA-605 completed/acceptance；60b84bea/dac0607b，接受不等于生产启用。 | 有后端实现/历史接受；跨adapter事务、发布不可变和新generation/保留规则仍需当前版本证据，不能因API存在改 done。 |
| QA-606 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#qa-606-发布-ui-与审计) | 当前 JobPublicationPanel 只显示资格/禁用原因，发布按钮无点击处理；documentJobs客户端未见发布/记录/最终下载方法。 | H-QA-606 completed/acceptance；2ef67e4c，原授权不合回根业务、不开生产。 | 确认历史发布UI与当前前端集成差异；后端最终下载存在不证明完整发布原因/列表/下载流程完成。 |
| QA-607 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#qa-607-审核发布-e2e) | 当前后端review/publication具相邻场景入口，未在本次有界任务/历史检索定位精确 QA-607 任务和五场景统一E2E记录。 | QA-603/604/605/606各有独立历史证据，不自动合成QA-607接受。 | 证据不足：五场景必须绑定同一集成基线及运行环境，尤其新结果失效/发布文件不可覆盖；不因未找到专名断言无测试。 |
| REL-701 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rel-701-release-check-和-acceptance-gate) | check_release.py、P0/P1/P2脚本存在；当前表格/四方向专用gate路径缺失，不能视为已组合目标门。 | 本次精确任务/提交关键词检索未定位 REL-701 接受；已有Golden20d496e仅历史P0。 | 部分基础工具；schema/preview/quality-review-publish/table-translation/blocked负例各门的当前组合与结果不足。 |
| REL-702 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rel-702-指标告警和容量) | HealthService 与 health_schemas 有readiness、metrics和ops alerts基础；不据此认定新增五域指标齐备。 | 未定位精确 REL-702 接受记录；现有运维任务与本目标不自动等同。 | 部分基础能力；table/translation/preview/review/publish指标、阈值和容量各项采集/告警效果待对账。 |
| REL-703 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rel-703-迁移和灰度启用) | migrate_document_job_state/reviews 与部署说明提供局部迁移/发布入口；flags在目标文档仍多为建议。 | 未定位精确 REL-703 接受；CON-103/QA-601历史迁移和B08资料不能代替全启用演练。 | 部分相关实现；真实backfill、API/Worker兼容窗口、灰度开关和回滚演练缺本次证据，禁止自动执行。 |
| REL-704 | todo | [原 AC](../../../../../../docs/implementation/codex-task-backlog.md#rel-704-runbookopenapi最终签字) | 现有API/OpenAPI、runbook、Acceptance/部署及历史签字资料可定位；B1已限定Golden原release。 | 未定位精确 REL-704 接受；既有P0/P1或单功能接受不等于本次总交付签字。 | 证据不足：需同一目标release的API/门户/Acceptance/线上任务/管理员最终签字，文档完善不能代签。 |

## 历史对象定位

以下37个任务对象实际从Git读取，并阅读每个对象目录内至多两份直接接受/验证记录。这里只保留对象身份和记录性质；不抄录历史机器路径、凭据或客户正文。task.json的阶段可能早于同目录后续接受文字，须并列解释。

| 标识 | 完整提交 | task.json 路径 | 该对象记录状态 | 已读取的同目录记录 |
|---|---|---|---|---|
| H-CON-101 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-12-con-101-product-mode-ui-copy/task.json` | completed | `validation.md`、`implement.md` |
| H-CON-102 | `ad3b624d4c5f5010649c786a0faf382d1d480793` | `.trellis/tasks/archive/2026-10/10-15-con-102-document-job-stages/task.json` | completed | `validation.md`、`implement.md` |
| H-CON-103 | `ad3b624d4c5f5010649c786a0faf382d1d480793` | `.trellis/tasks/archive/2026-10/10-16-con-103-quality-review-delivery-state/task.json` | completed | `acceptance.md`、`implementation-validation.md` |
| H-CON-104 | `71a542de5d5f0d0c665bdd57f58347d17b1a90be` | `.trellis/tasks/archive/2026-10/10-20-con-104-download-publish-availability/task.json` | completed | `implementation-validation.md`、`implement.md` |
| H-IR-201 | `b879641fde13710959df3d509c994956ccac661d` | `.trellis/tasks/archive/2026-10/10-14-ir-201-mineru-artifact-validator/task.json` | completed | `human-acceptance.md`、`validation.md` |
| H-IR-202 | `e5e64c01f0af1df6254a42cacdaa8e0ed8845ee5` | `.trellis/tasks/10-14-ir-202-margin-artifact-normalizer/task.json` | in_progress | `validation.md`、`implement.md` |
| H-IR-203 | `02b8bd93b320b9fb9c7b62d0d8e29cf0cf6cc040` | `.trellis/tasks/10-15-ir-203-cross-page-paragraph-merger/task.json` | in_progress | `validation.md`、`implement.md` |
| H-IR-204 | `de4efc2d977065f482f8fce04f769b6381c0df77` | `.trellis/tasks/archive/2026-10/10-15-ir-204-caption-reconciler/task.json` | completed | `closeout.md`、`validation.md` |
| H-IR-205 | `22d64df337bb26c3a13fc537bab806c16f46a12f` | `.trellis/tasks/archive/2026-10/10-15-ir-205-logical-table-group/task.json` | completed | `acceptance.md`、`validation.md` |
| H-IR-206 | `22d64df337bb26c3a13fc537bab806c16f46a12f` | `.trellis/tasks/10-15-ir-206-table-reference-asset/task.json` | in_progress | `acceptance.md`、`validation.md` |
| H-QA-601 | `5a1e05b44bc0a96e305ebb2590231f447eba0538` | `.trellis/tasks/archive/2026-10/10-17-qa-601-unified-document-review/task.json` | completed | `implementation-validation.md`、`implement.md` |
| H-QA-602 | `7e3a7454affc5b33e991a175d74b9f56cfce2330` | `.trellis/tasks/archive/2026-10/10-24-qa-602-quality-review-api/task.json` | completed | `acceptance.md`、`closeout.md` |
| H-QA-603 | `1ee2cbf8d590306ac7f2b085310cc9bf4398890e` | `.trellis/tasks/archive/2026-10/10-24-qa-603-three-panel-review-ui/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-QA-604 | `206d67b3d7d2c8e6b90da08fecc0cfb0feffed7c` | `.trellis/tasks/archive/2026-10/10-25-qa-604-download-status-warning/task.json` | completed | `acceptance.md`、`closeout.md` |
| H-QA-605 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-25-qa-605-publication-record-gate/task.json` | completed | `acceptance.md`、`implementation-validation.md` |
| H-QA-606 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-25-qa-606-publication-ui-audit/task.json` | completed | `acceptance.md`、`implementation-validation.md` |
| H-RND-501 | `f51edf7e8fa1ffd05bb2de5b21c3f5f0436e9cb6` | `.trellis/tasks/archive/2026-10/10-17-rnd-501-render-plan-block-evidence/task.json` | completed | `closeout.md`、`validation.md` |
| H-RND-502 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-23-rnd-502-formula-omml-fallback/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-RND-503 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-23-rnd-503-image-group-caption-rendering/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-RND-504 | `a12e108fdfde65e8dc897d343f019d6230640819` | `.trellis/tasks/archive/2026-10/10-16-rnd-504-word-preview-provider/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-RND-505 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-24-rnd-505-pdf-ir-word-page-mapping/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-RND-506 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-24-rnd-506-page-level-docx-quality/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-TAB-301 | `1dbb2059cb3fe7ed2a22d94ad5e912dc06e13646` | `.trellis/tasks/archive/2026-10/10-16-tab-301-canonical-table-grid/task.json` | completed | `validation.md`、`implement.md` |
| H-TAB-302 | `b879641fde13710959df3d509c994956ccac661d` | `.trellis/tasks/archive/2026-10/10-16-tab-302-html-normalizer-grid-builder/task.json` | completed | `validation.md`、`implement.md` |
| H-TAB-303 | `b879641fde13710959df3d509c994956ccac661d` | `.trellis/tasks/archive/2026-10/10-16-tab-303-table-validator-quality-flags/task.json` | completed | `closeout.md`、`validation.md` |
| H-TAB-304 | `b879641fde13710959df3d509c994956ccac661d` | `.trellis/tasks/archive/2026-10/10-16-tab-304-large-table-merge-preservation/task.json` | completed | `closeout.md`、`validation.md` |
| H-TAB-305 | `b879641fde13710959df3d509c994956ccac661d` | `.trellis/tasks/archive/2026-10/10-16-tab-305-cross-page-logical-table-rendering/task.json` | completed | `closeout.md`、`validation.md` |
| H-TAB-306 | `71a542de5d5f0d0c665bdd57f58347d17b1a90be` | `.trellis/tasks/archive/2026-10/10-16-tab-306-empty-html-placeholder-blocked/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-TAB-307 | `71a542de5d5f0d0c665bdd57f58347d17b1a90be` | `.trellis/tasks/archive/2026-10/10-20-tab-307-table-evidence-aggregation/task.json` | completed | `validation.md`、`implement.md` |
| H-TAB-308 | `de4efc2d977065f482f8fce04f769b6381c0df77` | `.trellis/tasks/archive/2026-10/10-20-tab-308-table-regression-gate/task.json` | completed | `closeout.md`、`validation.md` |
| H-TR-401 | `de4efc2d977065f482f8fce04f769b6381c0df77` | `.trellis/tasks/archive/2026-10/10-21-tr-401-caption-footnote-translation/task.json` | completed | `acceptance-audit-supplement.md`、`implement.md` |
| H-TR-402 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-21-tr-402-protected-token-codec/task.json` | completed | `closeout.md`、`validation.md` |
| H-TR-403 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-21-tr-403-translation-integrity-validator/task.json` | completed | `closeout.md`、`implementation-validation.md` |
| H-TR-404 | `ad3b624d4c5f5010649c786a0faf382d1d480793` | `.trellis/tasks/archive/2026-10/10-21-tr-404-table-context-builder/task.json` | completed | `human-acceptance.md`、`implementation-validation.md` |
| H-TR-405 | `ad3b624d4c5f5010649c786a0faf382d1d480793` | `.trellis/tasks/archive/2026-10/10-21-tr-405-term-language-post-validation/task.json` | completed | `human-acceptance.md`、`implementation-validation.md` |
| H-TR-406 | `512e4669f1039121777c1b2363672c0be8167fe0` | `.trellis/tasks/archive/2026-10/10-22-tr-406-partial-batch-failure-semantics/task.json` | completed | `acceptance-evidence.md`、`implement.md` |
| H-TR-407 | `de4efc2d977065f482f8fce04f769b6381c0df77` | `.trellis/tasks/10-22-tr-407-four-language-regression-gates/task.json` | in_progress | `implementation-checkpoint.md`、`implement.md` |

IR-207 的额外线索：`349bd759f8120a9a2d09be1b443791f182df5293` 是 TAB-305 的依赖复用提交；其任务验证文字引用已接受 `180c90a` 的23个fixture/runner文件。本批没有据此补造精确 IR-207 的最终接受对象。

## 当前集成差异的精确定位

| 当前不存在的路径 | 历史实现依据 | 本批观察边界 |
|---|---|---|
| `app/services/document_ir/margin_artifact_normalizer.py` | e5e64c01 | 当前 converter 仍有角色投影，缺专门模块不能代替全能力判断。 |
| `app/domains/translation/post_validation.py`、`post_validation_rules.py` | 46248866 | 当前术语配置/匹配不等于后验检查；共享技术完整性 Validator 继续存在。 |
| `scripts/dev/table_regression_gate.py` | 71a542de | 当前 component runner 仍存在，不能视为同等专项门禁。 |
| `scripts/dev/translation_regression_gate.py`、`tests/fixtures/translation_samples/manifest.yaml` | de4efc2d | 当前P1和matrix入口仍在，mode列表只为direct/en2zh/ru2zh。 |
| `frontend/src/pages/DocumentReviewPage.vue`、`frontend/src/api/documentReview.ts` | 1806580a | 当前review/blocks API和旧QA面板仍存在，不代表三栏前端已集成。 |

QA-604 的本次静态入口为 `frontend/src/features/job-detail/useJobDetailActions.ts` 的 `handleDownload`：直接获取链接、打开窗口、再显示 notice；未执行浏览器验证。QA-606 的 `JobPublicationPanel.vue` 按钮没有点击处理；本批不顺带修复。

## 版本与未提交源码

当前 HEAD 为 `d45e46e1233c3f173fa1d738cf75b3ef7a393eb9`。B1 已记录并核验的17份输入复用其证据；尤其 app/main.py、execution.py、router.py和translation_execution.py等当前工作区内容不能仅由HEAD代表。新增阅读输入的SHA-256见B2实施记录。所有21份B2文档核验SHA为null，因为本批只核对文档性质、目标/历史边界及上述局部静态对账，未认证全篇当前实现。

对账建议：优先把有历史接受且当前有入口的项目交由原任务/人工确认登记是否滞后；对有精确集成差异的项目先比较历史增量与当前owner，避免重做；对证据不足项目保留未决。任何状态修正都需另有精确任务ID与接受范围授权，本记录不直接提出或执行批量done。
