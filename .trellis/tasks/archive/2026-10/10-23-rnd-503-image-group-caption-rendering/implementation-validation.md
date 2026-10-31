# RND-503 实施与验证记录

2026-10-23最新授权：用户已人工验收并接受列明边界，授权任务限定提交和归档；此前review/待授权内容保留为历史，当前收口以closeout.md为准。

本轮全新critical复审后又有修复；本文早期数字保留首轮历史证据，当前候选以文末“全新实际实现复审后的最终验证”和post-review-validation.json为准。

2026-10-23。实际分支 `md2word/RND-503`，HEAD `1835263621a2a18627a5730e7fd62b6bc7cae8c2`，本轮未提交。用户已接受 v2 三件套和独立复核并授权实施；三件套保留批准时原字节，开头的历史“仅规划”说明由 `implementation-preflight.md` 记录的本轮授权和 manifest/task 当前状态取代，不改变验收范围。

## 依赖、实现与边界

IR-204=done，接受业务来源17cde1f及归档接受证据已核对。当前HEAD原未含依赖，先完成有边界工作树集成，165项原基线及174项依赖门通过后才start准确子任务。来源、失败诊断、传递IR-201输入门和B0指纹详 `dependency-integration.md`。没有把依赖提交伪称为HEAD祖先，没有改变其它任务状态。

图片计划采用严格同页源连续run、纵向连通分量全组复核及唯一归组，阈值与已批准design一致。确认组写固定无边框1×N原生表格，原资产字节、inline等比尺寸、逐图完整caption/footnote、SEQ/REF/富文本/公式保留；旧制表位图片writer已删除。拒绝组按源序单图，普通单图无多余warning，缺坏图保留全部注释且仍拒绝缺图成功件。

新增私有 `image-layout/v1` 与 `image-render-inputs/v1`，源IR/冻结实际模板与格式输入/最终OOXML三方认证，附加图片计划不改变旧LayoutPlan aggregate。layout/content/total表分别对账；marker不是内容表豁免凭据。首次登记核对构建身份，三恢复入口按原文件IR、模板及冻结输入重验，不读取当前配置。部分新字段残留也不能降级旧合同。无新公开API/schema、DB/迁移、仓储协议、任务状态机、权限、前端路由/query key/URL/generated types或新依赖。

内部新增image_evidence owner及schema owner的load_content(bytes)已在preflight核实现有接口后记录：共享真实投影/规则，实际解析值与hash单次读取同源；没有第二转换链、通用快照系统或运行时feature flag。

## 最终实际命令与结果

以下所有命令在仓库根执行。原始输出在ignored `tests/tmp/rnd503/logs/`；不将含测试事件的原始日志加入版本库。

```bash
.venv/bin/python -B -m unittest tests.test_image_group_rendering tests.test_document_ir_word_renderer_layout tests.test_document_ir_mineru_converter_layout tests.test_caption_reconciler tests.test_document_ir_layout_contract tests.test_formula_rendering tests.test_document_job_result_persistence tests.test_document_job_modes tests.test_conversion_sandbox_dev_tools tests.test_rnd503_dependency_integration tests.test_mineru_artifact_validator tests.test_template_layout_config_schema tests.test_formula_translation_boundary tests.test_document_job_delivery_state
```

**301 tests / OK，45.264s，exit0**，`final-core-unit.log`。覆盖实现计划规定九模块、输入安全、依赖恢复、template schema、公式翻译边界及下载/发布状态回归。

```bash
.venv/bin/python -B -m unittest tests.test_render_config_characterization
```

**13 tests / OK，0.013s，exit0**，`isolated-characterization.log`。首轮把该legacy模块与真实链混在同一进程运行314项，发生两项ParserError（`final-unit.log`，48.402s，exit1），没有抹去或称为通过。原因是既有runtime_direct_loaders替换全局sys.modules中的yaml/bs4/docx，而已加载shared模块保留真实yaml；mock未作用到同一个模块。用HEAD原terminology代码在同样加载顺序独立探针也出现ParserError且两yaml对象不同，见 `characterization-isolation-probe.log`。分进程是既有stub隔离，未改业务、未删断言、未放宽测试。

```bash
.venv/bin/python scripts/dev/run_component_pdf_regression.py --output-dir tests/tmp/rnd503/component
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core --output-dir tests/tmp/rnd503/direct
.venv/bin/python scripts/ops/check_release.py
```

- component：exit0，**1/1**，`component/20261023T080952Z/report.json`；仅ti-opamp-opa228-p1-smoke，不冒充ZK图对或全册。
- direct：exit0，**5/5**，OPA228_P1/P2/P6/P7、RS2G04，P0 issues=0；`direct/20261023T080952Z/report.json`。phase3_entry_ready=false/p1_p2_backlog_required仍保留，不擅自提升为下一阶段验收。
- release：exit0，**202 tests / OK，8.075s**；OpenAPI current，164 paths/324 schemas，changed=false；frontend contract及smoke mock静态合同通过。没有生成API/types差异，没有启动持久前后端/worker/数据库服务。

```bash
.venv/bin/python scripts/ops/run_golden_sample_regression.py
.venv/bin/python scripts/ops/run_golden_sample_regression.py --preflight --preflight-output tests/tmp/rnd503/golden-preflight.json
```

均exit1。实际Golden命令在认证前因缺 `GOLDEN_SAMPLE_PASSWORD/GOLDEN_SAMPLE_BEARER_TOKEN` 退出；preflight列 `golden_sample_auth_missing`、`golden_sample_api_unreachable`（127.0.0.1:8000拒绝连接），4个manifest PDF齐备。**不是Golden通过**；没有尝试取凭据、部署/SSH或上传专有样本。

```bash
.venv/bin/python -B tests/tmp/rnd503/run_b1_build.py
```

exit0。实际B1源码覆盖树/模块hash及294项来源清单已核对；正常构建三份既有产物读回成功，4 selectors / OK，14.700s，内部45个subTests；正常reader读取实际B1新件通过。详情见 `b1-validation.md` 及 `b1-build-manifest.json`。源码验证期间与结束后指纹相同；不是线上部署或生产回退演练。

`git diff --check`、27个变更/新增Python的compile()和正式renderer/adapter/execution导入检查通过；Trellis check额外检查未跟踪新文件差异。仓库无后端lint/type配置，venv无Ruff/Pyflakes/Mypy/Pyright，故未声称运行这些工具，也未安装新依赖。最终task validate和工作区保护结果见本记录末尾与 `workspace-protection-final.json`。

## 质量flag解释

唯一新增业务warning为 `image_group_uncertain`，受控原因完整列在Word Spec，普通单图/B1主动单图不误报，不加入blocking_quality_flags，不改变发布资格。caption_binding_uncertain仍归IR-204。

direct现存flags包括OPA228_P1候选标题1、P6候选标题3，RS2G04 LaTeX残留2和候选标题11。为解释差异，实际以B0镜像renderer/evidence/terminology/adapter与原schema、同一已接受依赖及同一输入重跑direct：5/5，其他flags一致，RS2G04标题候选由10变11。全相等诊断断言因此失败，未称flags完全不变。逐段hash/锚点定位确认：旧合并图片caption段长度44，等于当前block_0115/captions/0与block_0116/captions/0两段9+35的逐字拼接；按本任务要求分段后启发式候选计数+1，并非新增源标题/漏内容。详 `quality-flag-comparison.json`、`quality-flag-explanation.json`；不为消除此提示改标题算法或质量阈值。RS2G04残留2在B0同样存在，后续复核，不在本任务扩做公式子集。

## PRD逐条验收证据

| AC | 实际证据与边界 |
|---|---|
| AC1 | image-group模块阈值内/等/外、2/3图/多行、竞争/传递/逆序/缺bbox/跨页/中断/重复顺序测试通过；原IR不变、重复计划一致。 |
| AC2 | 1×N、六边nil、fixed/grid/tcW=dxa、无填充/浮动、inline四距0和cell绑定测试通过；七类源裁切/填充/翻转/旋转/偏移篡改均拒绝。 |
| AC3 | 横/竖非方图的内外层EMU尺寸/比例/有效宽高、非默认模板缩进及section几何通过。真实LO曾暴露缩进和默认9.05pt图距裁切，修复后3份中性样本均1页、四边完整；Word/部署客户端仍待验。 |
| AC4 | 每图多caption/note、SEQ/REF/bookmark/富文本/公式、重复来源及外部独立paragraph测试通过；删注/串图/交换整个图行/额外正文拒绝。表题空格兼容保持。 |
| AC5 | 正式合成ZIP→IR→DOCX图5/6、24/25可靠边界通过；已授权去标识不可靠源串保持uncertainty和一次可见内容；普通单图/无注/legacy通过。没有声称专有ZK全册或客户数据已验。 |
| AC6 | 所有受控拒绝/资源失败、缺坏图全部注释与完整性失败通过；NaN/±Inf报告经DocumentFileRecord JSON往返一致，原IR不变。正式输入非法bbox仍前置拒绝；typed IR把非有限值写null后的重读不在本任务扩展。 |
| AC7 | layout/content/total独立对账及marker复制/伪造/多漏表、关系/图/注释交换、非inline、单位/变换负例通过；纯图片布局表不伪造数据表可编辑性。 |
| AC8 | renderer并发隔离，三入口/明确跨代历史指针按原文件输入恢复；配置删除/变化后通过，未知版本/缺字段/错绑/损坏拒绝且不重新选件；B1实际构建双向兼容、旧公式与45个subTest通过。 |
| AC9 | unit/component/direct/release/OOXML/实际LO辅助预览及hash已记录。Golden环境未满足；Microsoft Word字段更新前后与部署预览未验证，不作视觉签字。 |
| AC10 | scope、安全/状态/权限静态复核及mode/delivery/receipt回归通过，文档/Spec同步；仅RND-503→review，Trellis保持in_progress，未done/archive/stage/提交/push。 |

## 实际预览Artifact

`tests/tmp/rnd503/visual/` 含三个中性ZIP、正式adapter产出的DOCX/IR、实际OOXML和 `evidence.json`；`previews/` 含PDF/PNG及image-geometry.json。图5/6、24/25各1个认证布局表/2个inline，单图0布局表/1个inline，三份blocking=[]/quality_flags=[]。原图均中性非方PNG，无OCR/翻译/专有图像。

LibreOffice **26.2.4.2**（0229ac93fcf0d7cbc6376066c6f35021cef002dc）以独立临时UserInstallation进行headless PDF导出，Poppler转PNG，主会话实际查看图对和单图；当前图对两张图矩阵宽/clip宽均222.1pt，源比例保持。导出有macOS Task policy日志但exit0/PDF可打开。辅助探针对照证明：仅表级边距/对齐/schema重排不能修复裁切；inline四距0才去掉导入图距。未重采样或缩小比例掩盖。

既有FIELD-002限制仍在：客户端更新SEQ会把非1起始/跳号图号重排，LO PDF显示Figure1/2；原DOCX缓存图5/6或24/25及源归属保真。此限制已在批准v2非目标中列明，本轮不改全书编号策略。Word更新字段前后需要人工明确验收，不能据LO产物宣称图号策略已修复。

## 不变量、安全、回滚与待验

保持模块化单体、MinerU唯一入口、direct零Provider/Prompt/翻译术语、原生HTML表格、每job唯一主DOCX、图片内部文字不译；没有OCR/重绘/第二流水线/新微服务/在线编辑/批量/知识库。冻结内容仅必要规范化格式值/hash/几何，普通事件不展开报告/规则/原文，模型错误不泄露私有快照。资产读取仍沿既有file owner/tenant/company/checksum和包路径边界。

不改事务/锁/仓储DDL、first-valid receipt、CAS/retry_count/generation；渲染/I/O仍在job锁外，恢复使用原文件身份，迟到/竞争回归保留。新登记损坏映射quality_checking/render_failed，历史恢复损坏uploading/oss_failed。质量blocked/翻译unreviewed仍可内部下载但不可批准发布，前端不维护新状态机。

停止条件仍沿已批准PRD；本轮没有未解冻结决策/破坏性迁移/发布覆盖/审计删除或必要实现授权缺口。B0仅用于未产新件的开发撤销；已有新报告后只能用保留reader/marker分类/输入投影/三入口/公式/receipt的B1，生成侧固定single-only/v1。先暂停/排空消费，不删除历史件/审计/选中receipt。实际构建只做本地验证，deployed=false。

未运行或未验：Microsoft Word、实际部署预览、线上Golden；真实MySQL/S3/MinIO与生产队列/跨主机回退演练。前端build/browser和真实DB迁移检查无适用变更；不以fake adapter/OOXML/LO替代这些证据。后续只列RND-504/505/506、FIELD-002编号限制及既存RS2G04风险，不提前实现。

最终停在manifest=review、Trellis=in_progress及commit plan；人工验收后才可done/归档。原暂存302项删除及无关dirty保持，具体提交候选与排除项见 `implementation-summary.md`。

最终收口实测：`git diff --check` exit0；`python3 .trellis/scripts/task.py validate .trellis/tasks/10-23-rnd-503-image-group-caption-rendering` exit0，implement/check各10条、无警告。批准v2三件套SHA保持；原暂存binary patch字节相同，44个其它manifest任务及RND-503块之外原文本保持，四份已识别无关dirty文件hash相同，最终正常294项业务来源hash仍与测试/B1清单一致。实际文件清单为25个原有文件本轮变更、11个新增业务/测试/授权fixture及当前子任务记录；不包含无关原dirty。

## 全新实际实现复审后的最终验证

准确任务 `.trellis/tasks/10-23-rnd-503-image-group-caption-rendering`，实际分支md2word/RND-503；IR-204 done，当前manifest review、Trellis in_progress。未重新start，未stage/commit/push/archive。三项P2与单位/省略默认兼容补充均修复；原始失败→主会话复核→修复→独立复验逐项见post-implementation-review.md。

最终候选命令和结果：

- `.venv/bin/python -B -m unittest tests.test_image_group_rendering tests.test_document_ir_word_renderer_layout tests.test_document_ir_mineru_converter_layout tests.test_caption_reconciler tests.test_document_ir_layout_contract tests.test_formula_rendering tests.test_document_job_result_persistence tests.test_document_job_modes tests.test_conversion_sandbox_dev_tools tests.test_rnd503_dependency_integration tests.test_mineru_artifact_validator tests.test_template_layout_config_schema tests.test_formula_translation_boundary tests.test_document_job_delivery_state`：exit0，311 tests / OK；`tests/tmp/rnd503/post-review/closure-core-unit.log`。
- `.venv/bin/python -B scripts/dev/run_component_pdf_regression.py --output-dir tests/tmp/rnd503/post-review/closure-component`：exit0，1 / 全部成功；`tests/tmp/rnd503/post-review/closure-component.log`。
- `.venv/bin/python -B scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core --output-dir tests/tmp/rnd503/post-review/closure-direct`：exit0，5 / 全部成功；`tests/tmp/rnd503/post-review/closure-direct.log`。
- `.venv/bin/python -B scripts/ops/check_release.py`：exit0，203 tests / OK；`tests/tmp/rnd503/post-review/closure-release.log`。
- `.venv/bin/python -B tests/tmp/rnd503/run_b1_build.py`：exit0，7 tests / OK；`tests/tmp/rnd503/post-review/closure-b1.log`。

核心311项/40.943s、release203项/7.379s；OpenAPI unchanged，164paths/324schemas。B1 7selectors/13.280s、55subTest，实际17份B1 reader产物+正常reader读新旧B1两次。Component仍只有OPA228 smoke；direct5/5，P0=0，但phase3_entry_ready=false（既有P1/P2backlog）。本轮flags与首轮实际issues精确相同，详post-review-quality-comparison.json；没有新未解释quality flag。

`git diff --check` exit0；`python3 .trellis/scripts/task.py validate .trellis/tasks/10-23-rnd-503-image-group-caption-rendering` exit0，implement/check各11条。Spec摘录30751bytes，含最新源SHA，低于32768上限。业务与测试七文件语法/正式imports通过；项目没有配置或安装后端lint/type工具，不伪称运行。

PRD增补证据：AC1/AC6保持原阈值（旧gap0.10保留uncertain，新增0.025可靠组），逆序图片仍源序单图；AC2/AC3认证有效表定位、真实模板20000dxa覆盖、direct exact行高拒绝、合法旧对齐/单位/缺省属性；AC4/AC5继续逐图全部caption/footnote/公式、可靠图5/6和24/25；AC7仍源/实际OOXML独立认证和表格分类；AC8新增真删全部报告键、三入口原receipt不变、真旧无marker及17+2实际B1/正常互读；AC9六份LO共8页逐页实看；AC10权限/模式/状态/不可变未改，旧dirty/索引保护见最终记录。

LO五个常规样本各1页，图界与注释所属正确；mixed-geometry为缺bbox极端竖图3页，图第2页/其普通注释第3页，未错绑或丢失，但不是同页。该分页局限仍需Word人工验收，不能写成keep链保证绝不分页。字段更新非1起始/跳号仍为既有FIELD-002非目标。PDF工具fitz在项目与bundled Python均缺失，未安装，改用pdfinfo/pdftotext/Poppler与实际查看；原失败探针不记通过。

未重跑未受影响的13项isolated characterization，原成功日志保留，避免将全局legacy stub与真实模块混跑；首轮314两错误的历史仍保留。Golden本轮未重试：上次确实运行失败，缺GOLDEN_SAMPLE_PASSWORD/BEARER_TOKEN且127.0.0.1:8000不可达，未有环境变更；未伪称通过。Microsoft Word、部署预览、真实MySQL/S3/MinIO和生产跨主机回退未验。无新API/DB/迁移/前端构建适用变更，不部署、不触达外部专有样本。

本轮业务代码只再改7文件：execution、word/image renderer、image_evidence及3份相关测试；无新业务文件。内部私有image-render-inputs/v1可选image_geometries只存真实section差异，旧缺键原hash不改；没有公开schema/DDL/API/generated types/权限或前端状态变化。I/O与渲染仍在job锁外，CAS/retry_count/generation/first-valid receipt不变；legacy新marker提前拒绝避免无效候选占用，错误仍uploading/oss_failed。安全/路径/敏感事件和direct零外部翻译调用合同保留。新中文职责注释及单位docstring已同步，没有为显然代码添加注释。
