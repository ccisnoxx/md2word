# B3 实施与文档检查

日期：2026-11-10。B2 整批独立复核通过后，主会话正式授权执行 design revision 1 的 B3。完成后停在 B3，未写 B4。

## 交付范围

- 51 份维护资料逐份追加四个治理字段：39 active、7 superseded、3 historical、2 draft。原 status/doc_type/日期/源文件清单等全部保留。
- 49 份 Markdown 仅加一段用途/适用范围导语；docs/dev/repository-hygiene.md 仅加 frontmatter，正文逐字不变；docs/api/manifest.yaml 只加顶层字段，原 entries/guides/OpenAPI 等业务对象不变。
- 所有 owner 和 last_verified_commit 均为 null：未确认人类责任 owner；局部入口/命令声明对照不足以认证全篇，已知 dirty 依赖不绑定假提交。verification_scope 使用相对任务证据路径。
- 新增本批 b3-preparation.md 与本报告。前者记录 51 份实施前身份、分类理由、17 个 API family、18 个脚本声明与 41 份静态输入身份；没有把这些表格变成第二套产品完成状态。

## 文档检查结果

| 检查 | 实际结果 |
|---|---|
| B3 一次性文档检查 | validate_docs.py --batch B3 通过；selected=51，errors=[]；生命周期计数与上文相同。 |
| YAML/frontmatter | 重复键、字段类型/枚举、原字段值与两个 docs YAML 原业务对象检查通过；未刷新旧日期。 |
| 精确保留 | 逐份去掉本批明确增加的五行字段块和单段导语后，51 份原文与实施前副本字节对应一致；原命令、AC/依赖、示例和历史结论无改写。卫生页仅元数据，正文完全一致。 |
| 链接 | 新增相对路径/锚点有效；存在两条实施前已有断链，详见下表；未顺带修复。 |
| 格式和卫生 | git diff --check 对本批 51 路径通过；显式 --files 卫生检查对 51 资料与 b3-preparation.md 共 52 份通过，内容跳过0、规则命中0。本报告另用同一显式 --files 入口检查通过，新增研究文本无行尾空白。 |
| 静态输入 | b3-preparation.md 所列 41 份源文件/脚本/样本 Manifest 身份在报告生成时全部匹配。只定位/读取必要部分，不等于审计整文件或执行功能。 |
| 已过批次及后续批次 | B1（含新增治理说明）与 B2 共 32 份候选仍匹配已记录 SHA-256；B4 全52份与实施前字节一致。未修改主会话三件套/清单/task.json。 |
| 原 dirty 保护 | 建项前245条中 225 条内容身份不变；累计 20 条变化均为已授权 B1/B2/B3 维护文档，范围外原 dirty 变化0。 |
| 暂存区 | index 条目摘要仍为 `1552991ae88d79c5b5fbc5c839b62cc3ea57eb7f7c800c455dea435c64344e31`，与建项前一致。 |

没有运行应用测试、lint/typecheck、build、CI、OpenAPI 导出、check_release/其他发布聚合器、Docker 或生产访问；没有安装依赖、stage、commit、push、archive 或 add_session。文中历史命令及验收声明均未在本批重跑。

## 既有断链与准确边界

| 文档 | 原目标（实施前已不存在） | 处理 |
|---|---|---|
| docs/api/document-jobs.md | `../../.trellis/tasks/archive/2026-10/10-15-con-102-document-job-stages/receipt-validation.md` | 保留原引用；不据此否定历史验证，也不声称已阅读此不存在路径。 |
| docs/api/document-jobs.md | `../../.trellis/tasks/archive/2026-10/10-15-con-102-document-job-stages/receipt-review.md` | 保留原引用；历史状态/集成证据沿用 B2 对账的明确对象身份。 |

- API Manifest guides 的 current/approved 与被索引 deferred 占位之间有旧口径差异，mineru-callbacks 的一条 source_files 指向不存在的旧文件；只在准备记录登记，不改业务对象。
- 旧根启动脚本、StageWorker、额外 callback token、旧镜像构建示例及组件修复路径用最小导语限定适用范围并链接维护入口；原命令语义和原文保留。
- Golden 两份 triage 报告定位原 2026-06-02/03 批次，FE/BE 计划第9节仍只表达原2026-06-10声明；未重开原制品、判定当前缺陷或宣布新的发布通过。
- 准备记录的 Document Jobs 文件级装饰器计数已按预复核修正为39：主router24、quality9、new_generation2、publication4。此修正仅限报告口径，没有变更 API 文档或应用。
- 未确认环境开关、真实 Provider/数据库/Word/权限行为、外部插件路径可用性和仓库外 YAML 消费方。模板空白项/示例不是实际验收签字。

## 51 份维护资料候选身份

| 相对路径 | SHA-256 |
|---|---|
| `docs/api/acceptance.md` | `d138aab6f1c1d05b76d194b82a6884ffba46d8bdad5eb1bb4001c05c53dcc7f3` |
| `docs/api/auth.md` | `6893743be148ae15c8d985346f43fc00d34f95484eb3f14b4483ca50ceaa2d1e` |
| `docs/api/config-workbench.md` | `1fd9647b2c647be9f6350d37f32ea7c4c48ebe4b2e66ce8e77bff1c24e6062d3` |
| `docs/api/document-jobs.md` | `10d8f1820efa6a15d7ac1394433a66e9a85053d7bbe9e6336387e44bbbae6cd2` |
| `docs/api/files.md` | `f9a4a5e6045957b9df70f046ce38b6fe6c4bfb769d8ccd9752086a91b75a4bf4` |
| `docs/api/health.md` | `fd13085223f2259d7756a3dfe724406b0c307b78a4496ef5d8314f71fcbd1124` |
| `docs/api/jobs.md` | `ae73a1e6e9d49ad0dd139b4c7d6eb0949ea255c82606677fd458bce53d624517` |
| `docs/api/manifest.yaml` | `30962d6a06818ce84f7c23a292de2cf36c3b754e30aa980f93c8a907c55e805c` |
| `docs/api/mineru-callbacks.md` | `edddbf6ce6cbfb767e8992badb1fbbb0e5146e252ad69421398a16b24088ba8a` |
| `docs/api/mineru-config.md` | `8648e5a5248772ed1670d4fbeab06108ad807b02e1394cc6ab7f02a2e0f07acf` |
| `docs/api/ops.md` | `7d3527b7164d87dbeb6e782ebdfe0dee8432fd140de9856598717570dac924d0` |
| `docs/api/templates.md` | `80acb118311488e2872404f8d86a42194f41a3a7823db3f9e4237d7ed2814197` |
| `docs/api/term-rule-categories.md` | `39795a21310ac705eb6da7e8a1d1feb5a4762d45ee0325de660b23ba512c5714` |
| `docs/api/term-rule-sets.md` | `ad7843bcc71f5e86258b40b345e0ba798f823e11d245438108995a2dafac98c4` |
| `docs/api/term-rules.md` | `202725c58e73c488b13fdf0cd96decf53b4df8996940696f672c6026468b74fd` |
| `docs/api/translation-profiles.md` | `6694a86bad97af1aae60899e51850bd10a3fe6051558a12d5619a74e006044a4` |
| `docs/api/translation-term-proposals.md` | `834d674db9a7a860b8428da4b28c7925020b5e644fa961b8077c05cc69eca80a` |
| `docs/api/translation-term-sets.md` | `e8e5d553cb298e9422ae664f247a28a301af00d3d63d0f5193cdc82dbb3e7eb9` |
| `docs/api/users.md` | `1dff89d04bd7fbd14be5b0b90cdc94de69049b1b08ca128639f9d41c25dde1e3` |
| `docs/dev/backend-architecture-baseline-and-issues.md` | `912bb9e6b4c933a8b7e7855e3921a300e678322544012341fee6ebc5d3ce0f47` |
| `docs/dev/backend-design-implementation-plan.md` | `d92fd492d8a92a543877867a893e1137e8fbe301cd5d20caba629a0cdc5ea106` |
| `docs/dev/backend-dev-docs-index.md` | `6318a7ef0e341d9c7f31d082ce8bce21cf6babbbb79e6c325226c103ff1dcbda` |
| `docs/dev/backend-local-minimal-env-and-commands.md` | `3df864cc9be1f5716a2e938ee1474b94a0e68fbb24d51e03b9b7c3cde926d358` |
| `docs/dev/backend-local-setup-and-architecture.md` | `cb8dd30934d72303fcfa1c115b44e7caa228406ee2dbe201044d7e87986c10ec` |
| `docs/dev/backend-pdf-online-completion-change-summary.md` | `8e9c63903250e2867d8157534273adab0623d57361fad2aa8e1e791a525b7413` |
| `docs/dev/component-pdf-regression-governance.md` | `ab33eeae1027aea9f558407b2b10032f811ab067af518976542bd876b905053d` |
| `docs/dev/document-ir-v1.md` | `38c9765fa5f5c8f5aa85a10b0015bdd297975dae069fff43b29dfda8e82ff6c5` |
| `docs/dev/document-ir-v2.md` | `b65b4e604aaf6680c46d9a4aaf155809117b221e86473cc4b95f21828e8296d4` |
| `docs/dev/local-component-pdf-debugging-implementation-plan.md` | `4ba180d624e17244c3ea334361e43d42379bf4a92218010be7bb2128354df4da` |
| `docs/dev/local-conversion-sandbox.md` | `ed2b81b52b195172d8c02108024cc5c0a667789f6b3eea599fc3c58e9c590cef` |
| `docs/dev/repository-hygiene.md` | `e2c9b9018fc33b9d7aa456b7d00ea5d692a7e8f368f8fa746cf492fcdf076f75` |
| `docs/dev/runtime-observability-and-health.md` | `0b1eb634ab929a8cd1ae83e09905e2480136137be541a837147454ceffaa384d` |
| `docs/dev/template-config-package-v1.md` | `a1201d69993d75a18d3903f35433ff4666f7c1f0247bbbcd3fc159a7e0e8d055` |
| `docs/dev/term-assets-sql-versioning-tasks.md` | `57bf1b20dce5d489973fa1409686e111f3cc86e98d4ca579137a16226c2c128d` |
| `docs/dev/term-assets-sql-versioning.md` | `2ad665c6d09c1d73089fc00f7340899b84956f283e4cec729092a5131ad2d7ec` |
| `docs/dev/term-rule-set-versioning-guide.md` | `8d0c28e91d8173c8e4357dfe804a85cc401a2acb8e9b10abd61550dfc3cf738b` |
| `docs/dev/translation-ai-audit-debug.md` | `f6e329fd44adf6f1fea8808ac3ec3f51f8d7c16e68db333971e50c16f7d667ec` |
| `docs/dev/translation-profile-and-segment-trace-guide.md` | `80a664e7eec351324d5a0cb2cff658caab65a139ba7f5a7f6300f54fb44cb0c9` |
| `docs/dev/translation-terms-v1.md` | `65a86df4f25806312f6bcf635bd40e42e74c6d611c6fca5a57126ff1aa18f74b` |
| `docs/runbooks/backend.md` | `58c3ef713f3dcc89e5838caf8fe3a7501c6f882a3cd4236e714ca20125b8ed2d` |
| `docs/runbooks/internal-portal.md` | `1dc98b9c30e41d210c113a65330d46876a1b74d1432e7949a1a67b16b83bf549` |
| `docs/testing/md2word-fe-be-integration-acceptance.md` | `e17ffd6f9eb8876ceb2dc5edbe10327962def9d571869b6d05b65efbe832c600` |
| `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md` | `83880db13c9f30cf6736c856c1e557b924d4bbd878513a0824c8403e26f764e8` |
| `docs/testing/pdf-to-word-gs-003-quality-triage.md` | `ac45b0a48d15ea2ed13d9ef2adf85c36779dbd4873c99a8fe75bbb870bf6f313` |
| `docs/testing/pdf-to-word-p0-integration-guide.md` | `42ed6fc7021fe22ad59f65153c7f71db55ca1820d7ea1d57da496a4ebce8aa91` |
| `tests/fixtures/component_pdf_samples/README.md` | `504ea39112d9ffd9db83caa13f17af306a53c650937615d4e0eb0fbce0667d51` |
| `tests/fixtures/component_pdf_samples/acceptance-record-template.md` | `479eefcb629bfcd25f90dd37a85d35fe8d61d811a4d5e4fb643e4c24b457702c` |
| `tests/fixtures/golden_samples/README.md` | `28af08f22754dd4e6faa944d540cd8317cf831cd37fa6645e92a44d2f08e1e3f` |
| `tests/fixtures/golden_samples/acceptance-record-template.md` | `4e8a34c0a02ca36d76d298631de5abd62c99f90242d14ee689b578e620b46c7f` |
| `tests/fixtures/p1_translation_samples/README.md` | `2c506860093da32807b22e74a6f22d7e580c2a7e7cd92f4edd9e8d8e261bc69e` |
| `tests/fixtures/p1_translation_samples/acceptance-record-template.md` | `0e17f7156da81d75922075ef6aeda9cc94fa9a7b2bffc79fe87983a7e04eb52d` |

## 交接

本批文档检查未发现新增阻塞；两条旧断链与局部说明漂移已精确登记。候选交主会话安排独立复核，该复核不由本实施报告代替。B3通过前不进入B4。
本批没有业务 Python 改动，代码注释/docstring/运行输出未变；新增元数据说明、导语与研究材料使用中文。
