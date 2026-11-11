# B2 实施与文档检查

日期：2026-11-10。授权：B1 独立复核通过后，主会话允许实施原 design revision 1 的 B2；未进入 B3。

## 交付范围

- 21份维护文档逐份追加四个治理字段及用途导语：20 active，BAS-001 历史报告为 historical。旧 frontmatter 字段、原任务定义/依赖/AC、报告命令/结果/哈希保持原文。
- 所有 owner 与 last_verified_commit 均为 null：责任人未确认；本批核对用途、旧字段和局部静态/历史证据，没有认证全篇代码或运行行为。
- 新增 b2-preparation.md、manifest-reconciliation.md 与本记录；对账完整45行，Manifest仍8 done/37 todo。未修改产品Manifest、B1、其他批次、主会话三件套/清单/task.json。
- backlog已提供只读对账入口并明确不替代Manifest、不推进执行状态/依赖门；没有新增可执行状态。
- 37个Git任务对象及各自最多两份直接接受/验证记录已定位；历史接受与当前集成差异分别说明，不据目录缺失或提交不可达推断全部功能未实现。

## 当前静态输入内容身份

下表是本批定位或读取的源码/配置/脚本字节；读取局部入口不等于审计整个文件，也不代表相关运行行为通过。B1不变事实可复用原证据。

| 相对路径 | SHA-256 | 与 HEAD 关系 |
|---|---|---|
| `app/domains/translation/modes.py` | `34814d57680fc5e5322ae9b1a4e9886c53191649bf9c789c91fb8f629d66adf0` | 相同 |
| `app/domains/translation/document_ir_translator.py` | `8874aab75f3d63134af339e6ace06447e1360e35627b02438f95d209064aff69` | 相同 |
| `app/domains/translation/integrity.py` | `3b81e1ed4fd35b4edd9adbd88d36356f32c3f4f726a607ac35abf0f121e9ec2d` | 相同 |
| `app/domains/translation/models.py` | `5ff17f9d15c946eba8a57be40406f60552718ddc7d61cd1aa118ed18eb751d16` | 相同 |
| `app/domains/translation/table_context.py` | `9195fb0b948cf0e9a44edda71e7367b1059dbbcab6b4c438ddbb11c1c19f7e80` | 相同 |
| `app/domains/document_jobs/models.py` | `98e3fcb618f402f40472b7bdba94edd677d915f11c0055e1407f3edc0e7323ca` | 相同 |
| `app/domains/document_jobs/execution.py` | `8d662da91d0ebad7b5f403c8a21f09551cf1323c028b04c178e9679eb3b6f27a` | 已有未提交差异 |
| `app/domains/document_jobs/translation_execution.py` | `dcdedf56816beb42b281a3828ed61d385819b65fde8f608e67a44572bd153865` | 未跟踪 |
| `app/domains/document_jobs/router.py` | `b018bbfb6d71c7ee89ef0fceac7e8bf9dce780a6eb52b9b763727c4e5c02b6c6` | 已有未提交差异 |
| `app/domains/document_jobs/service.py` | `00207b571bd262ea49cbab45c17f102bf37915d246035d733963f967f3895355` | 相同 |
| `app/domains/document_jobs/review.py` | `d312e2c8acf4b6b076836f1139783ba0c844be1e0f27fc52e1d6b2b8076f2eb6` | 相同 |
| `app/domains/document_jobs/publication.py` | `f0d9f7a792c4239a430c60896a3c7777c21117c640e17c8168b959a1f5b0225d` | 相同 |
| `app/domains/document_jobs/preview.py` | `a44d6fb453986e4dd1ab5c48f90be306cb09ee21de8c70c81a37cf51b5d35500` | 相同 |
| `app/domains/document_jobs/quality_review_http.py` | `20c94d29baea522be70d992a180371f7b7f277775dca0053c3f7e083d775765c` | 相同 |
| `app/services/document_ir/mineru_converter.py` | `7a4d610e4fdd253537292290959674f8a3170ddd4b83049b214ba2ff06d77748` | 相同 |
| `app/services/document_ir/artifact_validator.py` | `92bc04423b6e3411e4771ec61180900e589b9b163173aae1456544625ddc1787` | 相同 |
| `app/services/document_ir/layout_signals.py` | `3acf980fc0fc1a560819b5be6bb0c3a1f835ae90eb5700cb86bf8fe6f79f4019` | 相同 |
| `app/services/document_ir/logical_table_group.py` | `fcfb21cf6a767efa51956d4431df7b93caff5f540ee70fdb6d9b4dedb945f36d` | 相同 |
| `app/services/document_ir/table_reference_assets.py` | `9e5cdcdf91a119ebaf248a4a00c93c098f43428f16c40855eef60c7bf4e251ec` | 相同 |
| `app/services/document_ir/table_placeholder.py` | `6691fa3d515c70cc2fc637fb699c24b12851a7df0505c7dadf0a0174e062be96` | 相同 |
| `app/services/tables/models.py` | `fe7e3b892019767cad2851717690e952a8bd14b68454a46be2d5fcb1106872cd` | 相同 |
| `app/services/tables/grid_builder.py` | `3aac81e72d4f14383358938000fd1e59afedeb2f168d054553b67fa5383b0948` | 相同 |
| `app/services/tables/validator.py` | `c5cbf4427c5793f548425a137705b63b6e7ee6b56acd08bde5a5b4f0f80ccb4f` | 相同 |
| `app/services/renderer/table_renderer.py` | `197d1833a7ed622e5617c6e1721bb9046372b139b91390525ecb87d0117ccf02` | 相同 |
| `app/services/renderer/word_renderer.py` | `1acebf8137095883fd38d7424964998669c06f567cc28e8188a4e4983e477f09` | 相同 |
| `app/services/renderer/logical_table_plan.py` | `3b8e1460ccf3e87715ddfe295ef9958ff713414f922268e0632b289279f22db9` | 相同 |
| `app/services/renderer/table_content_evidence.py` | `5cb7acfbc34c05fed5ef0f28477cefb7c7338edec40c5c02ceff33597ed0d7a5` | 相同 |
| `app/services/renderer/render_plan.py` | `0c532eabf03fbf0dfe1844f392c024365604ed434d8510b2912b57e42cac4af9` | 相同 |
| `app/services/renderer/image_evidence.py` | `f24c6badfa5205e4fb9d28350b2862267ebe26caa187c37f4284020a0780b1e2` | 相同 |
| `app/conversion/docx_rules/formula.py` | `a7f5bd5d5ebe99657a55e5777d5ca15e76b7feb95d50f4efb1715c2ec9be3905` | 相同 |
| `app/services/preview/provider.py` | `69cd3261a6a32a0ad53cb4727648c153f253d7eb2a451c112a554b80a6af4daa` | 相同 |
| `app/services/preview/sandbox_adapter.py` | `27b4a9540f8fe7d7c340f4515b8d67d893dff5d9fa43e5564184dcf52a1287f6` | 相同 |
| `app/services/preview/page_mapping.py` | `24ae627e855ca4d61e9603bc7dd14ca84bed74bfac5b4313fae2539a1e6bca66` | 相同 |
| `app/services/preview/page_quality.py` | `f6c3922ac51526dac4d937beb8678415706c44e8c598eab422279a4fc7252c4b` | 相同 |
| `app/services/health_service.py` | `bbcd848b4d1814b0acd4f53eb724bfdc277b79ac2f4aa347ef5ffead4dfa7153` | 相同 |
| `scripts/ops/migrate_document_job_state.py` | `5183d01556f221e8be203764a004574981c546abbca7ab63c47fd20e457d35ee` | 相同 |
| `scripts/ops/migrate_document_job_reviews.py` | `1c129f2e82aff8605ee959fe73a687178b7560deda53474b7ea62ce692136392` | 相同 |
| `scripts/ops/check_release.py` | `31c96e03808c7542a526430188e546de0e7836e90329fb4e1dbb84c2419273f0` | 相同 |
| `scripts/dev/run_local_mineru_quality_matrix.py` | `b97d3f1e96cfec3acda16373cd63733471ba603d80aa1a3ab573000224936f3d` | 相同 |
| `frontend/src/api/documentJobs.ts` | `6b93b25afee8bea3f58c01d6d97a73b7487e10ea6100c2a7b422b6b5f1fa2e0a` | 相同 |
| `frontend/src/pages/TranslationResultQaPage.vue` | `d8365a184de593b1a04583dbb7c7f2451f590e892dc66da4f1702ade34523d32` | 相同 |
| `frontend/src/features/job-detail/useJobDetailActions.ts` | `08e3f5e40444120a9a054cdc256c7ea8027b929c8918007fbb5f7a6a9ad94236` | 相同 |
| `frontend/src/features/job-detail/JobPublicationPanel.vue` | `7197a2e2064b60081f3974b395fe41a2c088142d50da7e9286a7a54c19229e07` | 相同 |
| `tests/fixtures/component_pdf_samples/manifest.yaml` | `d32946ea5a89f57024dedec1e0a074afb7d66569091eabc3c757395b476d8fba` | 相同 |

## 文档检查结果

| 检查 | 实际结果 |
|---|---|
| B2一次性文档检查 | `validate_docs.py --batch B2` 通过；selected=21，active=20/historical=1，errors=[]，既有断链=[]。 |
| 原字段与结构 | 重复YAML键、字段类型/枚举及旧frontmatter值检查通过；全部核验SHA/owner为null，没有把原baseline改名或刷新旧日期。 |
| 正文精确保留 | 对21份原文去掉本批明确新增的四字段与H1后单段，逐字比较实施前副本完全相同；原任务AC/依赖、设计细节和历史报告命令/结果/hash保持。已逐份阅读实际新增导语与精确差异。 |
| 45项对账 | 45个ID/原状态与Manifest一一对应；45个原AC相对链接/标题锚点有效。每行含当前入口、记录及具体未决项，没有新增执行状态。 |
| 产品Manifest | 全45个task对象、rules、status_values与实施前解析值相等；仍8 done/37 todo，B2未写产品Manifest。 |
| 格式和卫生 | `git diff --check` 对21份路径通过；三个研究文件另查行尾空白/链接。既有卫生检查器 `--files` 对21份文档+3份研究记录通过，共24份、内容跳过0、规则命中0；未做历史扫描。 |
| 输入身份 | 上述44份本批静态输入在交接时均仍匹配SHA-256。B1原事实的适用范围不扩大。 |
| 工作区保护 | 建项前245条dirty中240条身份不变；累计5条获准文档为B1四条加B2的BAS-001报告。其他原dirty变化0。B2未修改B1文件。 |
| 暂存区 | index条目摘要仍为 `1552991ae88d79c5b5fbc5c839b62cc3ea57eb7f7c800c455dea435c64344e31`，与建项前相同。 |

本批未发现文档检查阻塞。独立复核由主会话另行派发，本实施记录不代替该结论。没有应用测试、构建、lint/typecheck、发布聚合器、Docker、生产访问、依赖安装、stage、commit、push、archive或add_session。

## 未决项与交接

- 45项保留各自未决证据：当前实现/部分实现、历史接受、当前集成差异及证据不足，均未直接判为done或修改依赖门。
- IR-202/TR-401/TR-405/TAB-308/TR-407/QA-603/604/606的精确差异仅为文档对账发现，没有顺带恢复代码或执行历史命令。
- 未确认文档责任人、真实Provider/Word/数据库/生产及部分历史制品的边界保留；主会话收到独立复核后决定批次完成，再安排B3。
- 未修改业务Python；新增/更新的文档说明使用中文，原代码注释/docstring/运行输出未改。

## 21份维护文档候选内容身份

| 相对路径 | SHA-256 |
|---|---|
| `docs/architecture/business-architecture.md` | `573fcf6a7d55d5e1bf263fc8e608776981040ef40fa4f150a18a88a71ec97ce7` |
| `docs/architecture/domain-model.md` | `0d461d23ec18584e10edd51fe3d16f04e67b5e084edab7aa821aaadc6c444678` |
| `docs/architecture/system-architecture.md` | `4dc7ad4e8542403f354660f68b6de99648713e083d846168e6c5f9bf22c9e436` |
| `docs/architecture/technology-stack.md` | `6f0cf77dd98ccdb57515f4b753ac243fb35c7ccd0d96a5f56e56d5c4b10c8fbd` |
| `docs/architecture/workflows-and-state-machines.md` | `42d1b45f30155a8a981f911e7f460f62166a5790e6555370f02e82c97e063e28` |
| `docs/contracts/document-ir-contract.md` | `40185dfb8395417fd496661acb293f7d224210d413fe771ea1449eaf2aa9244b` |
| `docs/contracts/mineru-artifact-contract.md` | `e177e4859daea689dca64ffd9d3b8e57a85746c98368067c0372014ae8061a6b` |
| `docs/decisions/architecture-decisions.md` | `0bb18bb445a37fad2a46ddd73b7df59b7f8ae2357b4fabb56414ff95cb988abd` |
| `docs/design/docx-rendering-template-design.md` | `ed1c49062b8d3551cea402436488a93730147865e40f0a65a43067f02f02a014` |
| `docs/design/quality-review-release-design.md` | `3b70f2e327f77dea6221a12f03827102c4612b01b91fd6554f653610386709ae` |
| `docs/design/table-processing-design.md` | `2092322fba8c178967d439ef635bbd1521d92cbaffc3c65bef1a9c680a8a5b1c` |
| `docs/design/translation-design.md` | `0137b5c1f10724922b8f48f5d523d9659837df8acf8ce74fa30b6ca2334486ed` |
| `docs/engineering/security-observability-operations.md` | `97e30aea31a35a44640713c6c91cba1c192d513ec1f5d67175230b7b1ce8f41d` |
| `docs/engineering/testing-acceptance-strategy.md` | `aac2e8207fea5c35206190d96f00c64aeda6c7297dc58077e4f9c68609e2d8ca` |
| `docs/implementation/baseline-verification-2026-10-12.md` | `27234f771c08b8f7b1a0d015fd35df23ad003f1498a122c7bd2fd7e2cbc89171` |
| `docs/implementation/codex-execution-guide.md` | `add9992ff46e325132940be5cc9d0dd9f484acde18277ec06efbe7646eb5abba` |
| `docs/implementation/codex-task-backlog.md` | `c5e25ae26021a78b580f4b836370a4b69839306627a59780970b0c3acfdc1361` |
| `docs/implementation/implementation-plan.md` | `0ae3a4489f5a2d78daf7ddbe7a138a1531cc58759e51746cbc8ed7b32c5ac0af` |
| `docs/implementation/rollout-and-migration.md` | `f3f2ffdc2364c424da507d7ae6ea5e287e5ec0ddc948ebc07c41bda41e78a790` |
| `docs/product/prd.md` | `40b1419909a4cd040280ccd8520baea507cbba4af214ef59f08944bab9dd6e50` |
| `docs/product/scope-and-decisions.md` | `6c98fc361a47ceb60854b90c7cdb99c49e2195e4275197bb42f851740cca5d82` |
