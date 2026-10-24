# RND-505 实施计划 v2

当前仅规划，未授权实施/start。执行本计划前必须人工接受最新三件套，G0未满足时不得写RND-505业务实现。当前分支仅为保留工作区，不自动切到建议分支。

## 1. 有序任务与评审门

- [ ] G0-A：按research/dependency-baseline.md保存统一基线选址、base/来源SHA及dirty/index保护；在批准的隔离环境复用两依赖，不覆盖根目录。集成路径候选见research/integration-paths.json，不把文件内容差异直接判成需覆盖。
- [ ] G0-B：融合RND-501 WordRenderResult/collector与当前RND-502 formula_report、RND-503 image_layout_report；真实三图cell、所有题注、公式owner、历史三恢复入口和两依赖execution/router共存。依赖缺口超出最小集成时停下重新评审，禁止实施其它backlog。
- [ ] G0-C：记录组合输入/代码指纹；运行下方基线定向/回归并独立只读复核高风险共存合同。差异归因完成后记录G0=passed，才进入本任务新行为。G0历史测试不当作当前候选通过；本轮不执行A/B/C。
- [ ] I1：在既有collector接点实现真实通用block书签，遵守命名/模板冲突及非可见写入合同。完成后最终save/freeze；保持原v1首名、targets数量/role、封闭Reason及所有报告验证；独立block_anchor_evidence仅记录同次成功新建事实，图片paragraph marker不扩大drawing内容owner。
- [ ] I1-B：将独立可选证明随WordRenderResult→renderer metadata→原主件receipt登记；在三恢复入口保留/局部校验证明、在所有事件/文件摘要/错误出口剔除全文。证明失败只降低锚点可用性，原内容/报告/hash错误继续失败关闭。
- [ ] I2：新增纯page_mapping模型、稳定canonical序列化/hash与design §5固定算法；区分单页证明、低置信起点估计、导航fallback及不可用。限制source provenance，所有来源spans有界保留，不扩IR规范化。
- [ ] I3：preview.py只从选定receipt/trace与当次已验证PreviewResult/PDF descriptor构造binding，将可选mapping写入原manifest。映射局部异常隔离、预算降级与安全摘要不进入quality贡献；原登记/存储/CAS错误照常显式失败。
- [ ] I4：添加独立mapping reader：既有preview/hash/权限校验后校验内层版本/hash/binding；坏mapping返回局部不可用，原preview不受影响。旧manifest缺字段正常；不新增GET副作用、后台重算/队列、HTTP路由、file_type或DB列。
- [ ] I5：统一定向验证、原报告/receipt/preview回归、旧新reader交叉测试和B1兼容回退证明；诊断失败后只重跑受影响集合。
- [ ] I6：更新合同/Spec、规划中已批准但实现有变化的细节，运行完整受影响范围Trellis check及独立只读风险复核。检查无内容/权限/发布倒退；最终停review，等待人工验收及独立提交授权。

## 2. 计划修改文件与范围

以下为G0完成后的RND-505功能候选，不把尚未实际集成的文件说成现根存在。

| 路径 | 计划修改 |
|---|---|
| app/services/renderer/block_evidence.py | 接入同次锚点物化及私有创建对象引用；WordRenderResult可选证明，原v1首名/targets/Reason不变 |
| app/services/renderer/block_anchors.py（新增） | 独立锚点证明模型、物化、最终对象关系认证、有界序列化及局部错误隔离 |
| app/services/renderer/word_renderer.py | 物化→save→freeze顺序及同次结果绑定；不得额外render |
| app/services/renderer/evidence.py | 附加独立可选锚点证明认证与metadata；保留旧aggregate、原v1认证和完整性负例 |
| app/services/preview/page_mapping.py（新增） | 独立模型、纯推断、canonical/hash、有界构建及reader；不是新Provider或服务层 |
| app/domains/document_jobs/execution.py | 精确接入证明随主件metadata登记、三恢复入口保留/局部校验及事件/摘要/错误出口脱敏；不改receipt协议或业务状态 |
| app/domains/document_jobs/preview.py | 接入原manifest构建/读取和安全摘要；不改状态/质量/CAS协议 |
| tests/test_renderer_block_anchors.py（新增） | 最终OOXML、稳定性、模板/既有marker冲突、并发和非可见内容守恒 |
| tests/test_preview_page_mapping.py（新增） | 精确单页/低置信推断/近邻/空/超限/版本与identity负例 |
| tests/test_document_job_word_preview.py | 正式renderer→manifest、状态不变、权限/当前文件/存储故障和历史兼容 |
| tests/test_renderer_block_evidence.py、tests/test_document_job_result_persistence.py、tests/test_document_job_preview_persistence.py | 新marker与原trace/receipt/preview三adapter恢复共存，补实际行为缺口而非复制测试 |
| docs/design/docx-rendering-template-design.md | 通用marker和可降级起点范围；页数推断不是真实排版 |
| docs/design/quality-review-release-design.md | 映射diagnostic不进入质量/发布判定，引用独立合同 |
| docs/contracts/pdf-ir-word-page-mapping-contract.md（新增） | schema、binding、算法、例子、confidence和兼容/错误语义 |
| .trellis/spec/backend/page-mapping-contract.md（新增）、index.md | 映射唯一owner及后续触发入口 |
| .trellis/spec/backend/render-plan-evidence-contract.md、word-preview-contract.md、word-generation-rules.md | G0集成正式Spec后增量更新物化时机/manifest可选字段/不变性，保留已验收历史合同 |

不计划修改前端、OpenAPI schema、SQL/schema/bootstrap、API路由、发布/复核状态机、provider/executor协议、requirements/config。若I1需要深入个别writer取得真实目标，可在既有collector接点小范围调整text/table/image writer，先记录精确owner与理由，禁止重构布局或复制第二套writer。

G0依赖集成的文件不是本轮修改清单。若实施授权只含RND-505而未含G0准备，继续停在前置门，不绕过缺失模块写兼容fallback。

## 3. 测试映射与定向命令

### T0 统一基线与现有行为（G0后运行）

核实文件/测试在统一基线真实存在，先运行：

```bash
.venv/bin/python -m unittest tests.test_renderer_render_plan tests.test_renderer_block_evidence tests.test_word_preview_provider tests.test_document_job_word_preview tests.test_document_job_preview_persistence
.venv/bin/python -m unittest tests.test_formula_rendering tests.test_image_group_rendering tests.test_document_ir_word_renderer_layout tests.test_document_job_result_persistence tests.test_document_job_execution_stages tests.test_document_job_delivery_state
```

补已验收RND-501/504验证记录中明确的TR/CON共存selectors，按实际合入差量选择；将已知API7项或RND-504既有失败逐项关联原基线同签名证据。不得因为历史失败数相同就推定本轮失败既有。

### T1 新行为（AC1–AC6、AC9）

```bash
.venv/bin/python -m unittest tests.test_renderer_block_anchors tests.test_preview_page_mapping
```

- 最终ZIP/XML而非mock计数：heading/paragraph/list/formula/table/caption、三图片cell、shared/coalesced/TOC、header/footer/superseded、空块；真实target与bookmark_start/end/数字ID配对；保留原公式和图片marker。
- 同IR同名；两个不同IR相同block ID必须通过IR/hash区分；模板预占名、既有高数字ID、同实例交错/并发均无覆盖；无空段/可见文本/额外分页。模板预占expected generic且恰在target内部时，证明仍无成功entry、mapping为anchor_missing。
- 无caption单图/三图cell：drawing后代无generic bookmark仍可由独立创建证明绑定paragraph marker；旧v1首名与targets数量/role投影保持。伪造别图run、同cell但不同paragraph、错part/缺end/重复ID/陈旧child_path不得认证。
- 证明不存在/未知版本/跨IR-plan-DOCX错绑/超限：只使锚点不可用；原DOCX/hash/公式图片报告篡改仍失败。主件登记前证明冻结，三恢复入口不得按名字回填创建事实；公开所有出口做新键canary。
- source typed多span与空fragment owner守恒、legacy布局与自由metadata区别；source index稀疏、source与Word页数不同、源页单页而Word多页、无source候选、真实输出序≠IR顺序、nearest tie、coalesced代表及无目标。
- 固定公式例S=3/P=5→0/2/4；P=1正文→0/high；T=3/P=2无来源→0/0/1（中点平局低页）；T=1/P>1→0/low；S=1/P=5/T=3的三个有来源正文owner→0/2/4且reason=source_page_rank_degenerate；header/suppressed的location对象为unavailable/页null/none，fallback可低置信；长表range=null。
- 成功预览+完整有界trace但只有suppressed/header/footer/not_emitted：保留全部source/owner/disposition entry，报告unavailable/no_target，每项location不可用、fallback=null，total等于已证明块数；与缺trace/预览失败的entries=[]明确区分。
- preview不可用/旧trace的最小unavailable对象（IR/plan/PDF允许null，不造hash）/未知版本/非有限数/超8MiB或100000条：整体不可用有原因，不能截断后complete。全mapping字段不得进日志canary。
- 归一化移除新marker后比较所有受影响Word XML部件的可见文本、OMML、图片、表格、尺寸、样式、分页/section属性；不比较ZIP时间戳，不用单一“可打开”代替内容守恒。

### T2 应用、身份和持久化（AC3、AC6–AC8）

```bash
.venv/bin/python -m unittest tests.test_document_job_word_preview tests.test_document_job_preview_persistence tests.test_document_job_result_persistence tests.test_renderer_block_evidence
```

- 用真实renderer/主件receipt+fake preview结果验证mapping只绑定winner：同代双渲染、跨代、旧run/attempt、new key alias/历史key重放、无重渲染；source/result/IR/plan/PDF/profile错绑拒绝。
- 对照preview有/无/坏mapping，execution/quality/review/delivery/available_actions/主DOCX hash保持；blocked/unreviewed内部下载不变，原内容完整性错误不能降级。
- manifest存储失败与单纯mapping不可用分开；registering中断、PDF成功而manifest失败、迟到finish/租约失效不伪成功；新字段不扩大原跨存储事务承诺。
- file真实双进程与SQLite独立连接沿原tests，fake MySQL仅证明SQL调用/事务形状。真实InnoDB/部署文件系统并发在启用前门，不由mock代签。
- owner/Admin、tenant/company隔离、当前manifest引用、过期/删除、S3最短TTL和本地技术Token重新检查；不暴露完整映射到普通file摘要/incident/events。
- 三恢复入口、历史23键aggregate、RND502/503报告与布局表分类均保留。新manifest→旧v1读者、旧manifest→新读者、未知mapping版本→局部不可用，原preview仍合法。独立锚点证明由三恢复入口保持，缺失/坏证明只影响mapping；B0若丢字段或泄露新私有键则禁止直接回退，先交付通过同等验证的B1兼容读者。

### T3 项目回归门（AC10）

```bash
.venv/bin/python scripts/dev/run_component_pdf_regression.py
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode direct --sample-set phase2-core
.venv/bin/python scripts/ops/check_release.py
```

使用已提交/已授权最小MinerU样本，保留run目录及输入/输出/代码hash。direct Provider/Prompt/术语调用为0。纯规划本轮不运行这些命令；实施候选必须有证据，不能把历史OPA228通过借用为本轮通过。OpenAPI预期current且无schema改动；若变动先查意外file_type/路由泄漏，不机械更新快照。

前端未改，故不运行前端build/Vitest/Playwright作为本任务默认门。项目online-first规则保持，不为补证启动本地API/Worker/MySQL/Redis。Golden与真实Word/部署预览使用授权环境执行并记录版本、页数/定位偏差与人工结论；无环境时标未验并保持生产disabled，不虚构passed或开启外部服务。本任务首版不以多页像素匹配率作自动验收，所有低置信估计必须可解释。

## 4. 文档与Spec

只在实施后更新实际已实现合同；本轮研究快照不是已部署Spec。新合同给合法/缺省/非法例、绑定关系和错误矩阵；现有Word规则记录非可见marker及最终freeze顺序，明确mapping不改预览质量贡献。保留旧结果恢复规则，不复制长篇状态机形成多真源。所有新增/实质触及Python注释/docstring/开发者错误消息按项目要求中文，机器字段保持原值；不清理未触及旧文件。

## 5. 回滚与停止

- R0：G0组合基线；未写新产物前可撤回RND-505候选业务变更，保留依赖，不回到当前缺依赖根目录。
- R1：已写产物后停止新marker/mapping生成并保留兼容读者与原独立锚点证明metadata。先证明B1不会删除/重算/泄露新字段，再允许新写入；以B1源码指纹证明旧/新manifest与带marker DOCX的三恢复入口通过；不删除Artifact、历史审计、批准记录或重写已发布件。
- 原所有停止条件与design §9适用；权限/发布/内容校验出现必须削弱才能过测的路径直接停止。
- 每轮结束检查准确diff/status，无关dirty/index不变；不bulk stage、不stash、不自动提交/push。

## 6. 完成定义

规划完成：三件套、研究、真实context与task validate通过，停planning等待人工评审；G0未满足如实保留。

实现完成：AC0–AC10逐项证据、material问题关闭、必要回归与文档Spec完成、残余未验边界可审查；停review等待人工验收。后续commit/archive/add_session分别按授权执行，不由本规划自动授予。
