# B2 独立文档复核

日期：2026-11-10。依据：本任务 PRD、design revision 1、implement.md 及 B1 已完成的静态证据。复核方仅持有本报告，不修改维护文档、产品 Manifest 或业务源码。

结论：**B2 的 21 份文档候选与 45 项只读对账通过独立复核，未发现需要修改的缺陷。** 本结论仅覆盖文档合同与下述静态/历史证据，不是产品或生产验收。

## Findings (fixed)

无。未修改对账记录、维护文档或业务实现。

## Findings (not fixed)

无已确认而留待修复的缺陷。对账中保留的真实运行、人工签字、原版本与当前集成等未决项有明确范围，不由本次文档治理消除，也不推进任务状态。

## 45 项对账的独立复核

对象：[manifest-reconciliation.md](manifest-reconciliation.md)。

| 范围 | 直接观察与结论 |
|---|---|
| ID、状态与 AC 引用 | 解析对账表与产品 Manifest，45 个 ID 唯一齐全，集合与原状态逐项一致：8 done、37 todo。45 个“原 AC”本地目标及 backlog 标题锚点均可定位。研究建议没有替换执行字段或形成可执行依赖门。 |
| 37 个历史对象 | 逐一通过 Git 对象读取 37 个 task.json，其 status 与定位表一致；每项列出的同目录直接接受/验证资料均存在。对账表将 IR-202/203/206 和 TR-407 的阶段差异并列说明，没有用后续接受文字覆盖早期对象状态。 |
| 重点接受记录 | 抽读 CON-102/103/104、IR-202、TAB-308、TR-401/405/407、QA-603/604/606、RND-501/504/505/506 的 task 字段及直接接受/收尾文字。已接受实现、规划接受、实现检查点、归档和生产启用的区别均有记录依据。未把未跑/失败或替代客户端观察记成本轮通过。 |
| 历史路径与集成 | 直接确认 e5e64c01 的 margin_artifact_normalizer.py、46248866 的两个 post_validation 模块、71a542de 的 table_regression_gate.py、de4efc2d 的四方向 gate/manifest、1806580a 的 DocumentReviewPage.vue/documentReview.ts 均在历史对象存在、当前指定路径不存在。上述工作提交不在当前 HEAD 祖先链；研究记录同时保留需比较当前 owner/字节的限制，未由不可达直接断言整项功能缺失。 |
| IR-202 | 当前 converter 仍调用 layout_signals.role_for_source_type；对账记录将角色投影与原跨页重复/位置规范化目标区分，未仅由专门类名缺失判整项未实现。 |
| TR-401 | 当前 extract_translation_items 调用 text、list、table HTML 三类提取；apply_replacements 对应回填这三类，未见显式 captions/footnotes 分支。与原显式 annotation AC 和历史实现存在局部差异的判断有源码依据，记录未外推完整翻译行为。 |
| TR-405 | 当前 forbidden_translations 可在模型/管理字段定位，共享 Validator 仍维护技术完整性。对账记录没有将配置存在当作 mandatory/forbidden/目标语言后验已执行。 |
| TAB-308、TR-407 | 当前 component/matrix 入口仍在；matrix 的 ALL_MODES 是 direct/en2zh/ru2zh。指定历史专项 gate/四方向清单缺失的精确观察成立，不能据此认定当前工具完全等价或四方向实译已验收。TR-407 原检查点明确人工 pending、P1 阻断和 release_readiness 未评估。 |
| QA-603 | 当前指定三栏文件缺失，旧 QA 面板与 review/blocks 后端不被当作三栏同步完成。原 closeout 明确 F6 四文件仅独立静态复核、没有重跑运行检查；对账保留该限制。 |
| QA-604 | useJobDetailActions.handleDownload 先取链接并打开，再展示 notice；函数内没有下载前确认。原接受记录限定隔离树交付、不合回根业务，对账没有宣称所有下载入口均已核对。 |
| QA-606 | 当前 JobPublicationPanel 发布按钮没有点击处理，documentJobs 客户端未见对应发布/记录/最终下载方法。原接受明确不含根业务合回或生产启用；后端存在不被当作前端全流程完成。 |
| CON 与 RND | 复用 B1 扩展阶段及未提交翻译协作者事实；另静态核对 quality/review/delivery 字段、迁移入口、下载响应、quality_review_router、publication 资格检查、RenderPlan、PreviewProvider 默认 disabled、page_mapping 与 page_quality 接入。对账保留真实持久化、外部执行器、Word 与当前全 AC 未验证边界。 |
| 当前已 done 与无命中项 | 研究表没有用本次静态调查撤销原 8 项 done。QA-607/REL 等未定位精确接受对象被记为有界检索和证据不足，未将无目录或无专名等同于没有能力、测试或接受。 |

## 21 份文档候选

直接阅读 21 份文档相对主会话实施前只读副本的完整差异；正文变更仅为标题后的范围导语及对账入口，原任务定义、AC、依赖、专项合同、历史命令/结果/哈希均保留。原字段不改值，旧 status、baseline_commit、last_reviewed 等不被新字段覆盖。

| 维度 | 复核结论 |
|---|---|
| 用途与生命周期 | 20 份仍维护的目标/合同/决策/执行说明使用 active；BAS-001 以 historical 保留 2026-10-12、fcea60ff 基线及六项当时结论。生命周期判断未把设计 accepted 或目标冻结解释为能力已实现。 |
| 核验字段 | 21 份 owner 和 last_verified_commit 均为 null。逐份 verification_scope 说明用途核对、旧字段和局部证据性质，明确没有认证全篇代码/运行；没有虚构维护团队或统一填入 HEAD。 |
| 混合历史与目标 | 系统架构保留 e51e6ccd 与 2026-11-06 局部范围；技术栈指出旧表不能证明安装版本；表格设计第 2 节旧差距与当前 grid 区分；翻译/渲染设计保留专项合同及外部未验边界。 |
| 规则和执行入口 | 测试策略、执行指南、实施计划与迁移说明区分建议检查/flag 和实际授权/配置；未改变原 AC、依赖门或产品范围，未凭文档触发额外产品验证。 |
| backlog 对账入口 | 新增入口指向本任务 45 项只读对账，并明确不替代 Manifest、不推进任务状态或依赖门。引用原任务定义仍有效，没有另造状态系统。 |
| 候选内容身份 | 21 份文档当前 SHA-256 全部匹配 b2-implementation.md 的交接表，实施文档验证输入未变。 |
| 静态源身份 | 独立比对 B2 实施记录列出的 44 份源码/配置/脚本 SHA-256，全部相符；与 HEAD 相同、已有未提交差异及未跟踪三类关系也一致。该身份检查不外推整文件审计或运行验收。 |
| Spec 同步 | 没有业务代码或实现合同变更；新字段的规范 owner 已由 B1 治理说明承担，本批不需要另改 .trellis/spec/。 |

## Verification

- 对账表结构、45 ID/原状态与 AC 链接：通过，独立定向读取；未导入或运行业务代码。
- 37 个历史对象及其列出的记录定位：通过；重点语义抽查范围如上，不声称重做全部产品验收。
- 21 份维护文档结构、字段类型/枚举、重复键、原字段/正文保持与链接：通过，复用主会话/实施方的定向检查；selected=21、errors=[]、既有断链=[]。候选身份已独立核对，未重复运行整批检查。
- Manifest 全业务结构保持、24 个显式文件卫生及差异检查：通过，复用已交接结果。工作区保护复用 245 条原 dirty 中 240 条不变、累计 5 条为获准文档叠加、范围外变化 0、index 不变的记录；复核方没有写入这些文件。
- 新增/更新的本复核报告：格式、相对链接与文件卫生通过，仅检查报告自身。
- Lint / TypeCheck / 应用测试：不适用，未运行。
- Build / CI / 发布脚本 / Docker / 生产访问：未执行。
- 未安装依赖，未 stage、commit、push、archive 或 add_session。没有 Python 变更或 Python 注释/docstring/运行输出改写；新增报告使用中文。
