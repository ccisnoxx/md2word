# BAS-001：当前能力与测试基线核验

## 目标与业务结果

将 `docs/implementation/current-gap-analysis.md` 的不确定项转成可追溯、可复现的当前事实，使后续任务能复用现有能力、识别真实缺口，并选择正确测试入口。交付的是能力与测试证据基线，不改变转换、翻译、下载或发布行为。

阶段：R0（文档与基线）。父任务：`10-12-datasheet-docx-delivery-quality`。分支：`md2word/BAS-001`。
规划日期：2026-10-12（America/Los_Angeles）；调查 HEAD：`fcea60ff8c131edff7fd5ba360e1bf4e37ec4227`。

## 前提与权威关系

- manifest 中 BAS-001 初始为 `todo`，唯一依赖 DOC-001 为 `done`；归档任务 `archive/2026-10/10-12-doc-001-documentation-package-index/task.json` 记录人工验收，依赖通过。
- 产品范围由 `docs/product/prd.md`、`docs/product/scope-and-decisions.md` 决定；冻结技术决策见 `docs/decisions/architecture-decisions.md`。backlog 定义任务，manifest 管理执行状态；当前代码/测试说明已有事实，不能以未来文档冒充已实现。
- 本会话只调查、创建规划和配置 context，停在评审门；不执行 `task.py start`。实施和基线测试待本规划另行获批。
- 工作区初始只有 `.gitignore` 为未识别改动，必须保留。不得 stash、清理或覆盖其他任务内容。

## 已确认背景

详见 `research/current-capabilities.md` 的代码、测试、API、脚本及历史路径：

- 本地 DOCX→PDF/PNG 视觉验收已有；尚无正式任务级 Word Preview Provider、API 和产物模型。
- translation QA 与配置版本发布已有；尚无文档结果 PublicationRecord / publish API。
- annotations 已进入 IR，但 translator 只回填 text/list/html；caption 的 text 副本可能被翻译，captions/footnotes 数组不被翻译。
- 有自然分页、空表续页归一化；未发现保留 source spans 的跨页语义段落合并。
- 图片/chart 资产已有 file/hash 链；table reference 未进入这一登记链。
- MySQL 有 bootstrap 和列/索引维护，sqlite 有 bootstrap；没有版本化 schema migration/up/down 体系，shadow copy 是后端搬迁工具。
- 已有 release、Golden、component、translation、frontend 入口；历史通过记录不等于当前 HEAD 通过。仓库没有 `baseline-verification-*.md`，BAS-001 整项不满足跳过条件。

## 范围与交付物

1. 六项能力逐项核验，写明入口、调用链、存储/API/UI、现有测试、已证实行为、缺口和证据限度。
2. 在规划获批后的执行阶段产出 `docs/implementation/baseline-verification-<date>.md`。日期使用实际执行日的 America/Los_Angeles 日期；若当日执行则为 `baseline-verification-2026-10-12.md`。
3. 报告包含当前 release、Golden、component、translation、frontend 的精确命令、环境前提、实际结果或明确未运行原因；区分静态事实、本次执行、历史运行、外部/人工证据。
4. 输出逐任务的 `SKIPPED_EXISTING` 候选、缩小范围和依赖调整建议；建议单独列在报告，不自行修改其他任务状态或依赖。
5. 默认不新增/重构测试或脚本；如现有测试与临时只读探针仍无法核验，提出具体覆盖缺口，回到规划评审后再决定。

## 冻结不变量

- 一次只实现 BAS-001，不提前实现其他 backlog 任务；本任务不得修改业务行为。
- 保持模块化单体，不引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；其他语言必须创建或克隆新任务。
- `direct_pdf_to_word` 不调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口，不增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格，不以截图作默认简化。
- 质量 `blocked`、翻译 `unreviewed` 均可内部下载，但不得批准或发布；这是目标约束，报告不能把尚未实现的状态维度写成现有保障。
- 前端不得推断发布资格，必须消费后端权威状态或 available actions。
- 不新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 调查结论引用真实代码、测试或文档路径；配置默认值不证明生产配置，历史记录不证明当前部署状态。

## 权限与失败语义

使用仓库文件、fake Provider、临时 file/sqlite 与 fake MySQL；不读取凭据正文，不连接生产 DB，不触发 MinerU/LLM、发布、重试或审计写操作。
在线 Golden/P1 会创建任务并调用外部系统，必须有明确环境和操作授权。缺失时记录 `not_run`/`blocked_by_environment`，不得写为 pass，也不启动本地服务代替生产门禁。
已知产品缺口或现有测试失败作为基线事实记录，不顺手修复，不更改断言或 gate 以制造通过；环境失败与产品失败分开分类。
目标要求与当前实现的差距不自动构成规划阻塞；必须改变冻结规则才能完成 BAS-001，或权威文档存在不可消解冲突时才停止。

## 验收条件

| ID | 可观察结果 |
|---|---|
| AC1 | 报告记录 HEAD/分支/日期、dirty 清单、依赖状态、环境和命令；六项能力每项至少有权威实现或明确搜索范围及交叉证据。 |
| AC2 | Word Preview 与本地视觉工具、文档发布与资源发布、跨页段落合并与自然分页、迁移与 bootstrap/shadow copy 分别核验，不混淆。 |
| AC3 | 五类测试均有命令和结果栏；获批的本地 release、定向测试、component、frontend unit/build 实际执行；Golden/P1 在线和浏览器/Word 若未执行，原因、历史适用版本及残余风险明确。 |
| AC4 | 每个“已实现”结论指向代码和既有测试；未执行的测试不标通过。annotation/reference/paragraph 的最小复现通过现有正式入口，必要时在临时目录运行只读探针。 |
| AC5 | backlog 建议有任务 ID、已覆盖部分、剩余验收和依赖理由；整项完全满足才建议 `skipped_existing`，状态变更须人工验收。 |
| AC6 | 业务代码、测试框架、配置、OpenAPI、DB、资源 seed、既有样本保持不变；其他任务状态与依赖不变，`.gitignore` 保留。 |
| AC7 | PRD/design/implement/context 齐全，`task.py validate`、规划/报告路径和差异检查通过；规划停在 `planning`，执行交付停在 manifest `review`，不自动提交、push 或归档。 |

## 非目标与停止条件

不修调查发现的问题，不重构测试，不实现 Preview/Publication/TokenCodec/表格或状态功能，不建立迁移框架，不新增专有样本，不部署、不运行生产回归或补造人工签字。

停止条件：依赖非 `done`/人工接受的 `skipped_existing`；PRD/冻结决策/已接受 ADR 不可消解冲突；需要未批准的破坏性迁移、覆盖发布文件或删除审计；需要改变冻结任务模式、表格原生化、下载/发布规则；必须使用未授权样本/外部系统/安全授权且 fake/adapter 无法完成范围内核验。
目前未发现阻止本规划形成的条件。待审的是本规划；产品或风险偏好的阻塞问题为空。

## 2026-10-12 执行授权与结果补记

用户已明确审核并接受三份规划，授权实现 BAS-001。上文“本会话只规划/待获批”描述的是前一规划轮次；本轮已准确 start 子任务并执行既有基线和三项合成探针。实际结果见 `docs/implementation/baseline-verification-2026-10-12.md` 与本任务 `validation.md`、`research/reproduction-evidence.md`。

按本轮明确要求运行 P1 `--preflight`，因缺认证信息退出 1；未调用真实 Provider。根据“更新受影响 Spec”要求，为 database-guidelines 的现有 schema 段补充 MySQL maintenance 顺序和 fake 证据边界；只补当前事实，不建立迁移合同、不更改业务。API 当前性检查通过，API 文档/快照不变。没有触发五类停止条件。

交付状态为 manifest `review`、Trellis `in_progress`；规划已接受不等于实施已人工验收。等待人工验收和提交授权，不 done、不 archive、不提交、不 push。

## 2026-10-12 人工验收与收尾授权

用户已明确接受 BAS-001 的实现、测试证据和残余风险，并确认当前 commit plan，授权只提交、归档当前任务，不 push、不启动后续任务。上文 planning/review/in_progress 和等待授权的语句保留为阶段历史。

BAS-001 新交付六项事实、当前基线报告与可复现证据，整项报告此前不存在；最终 manifest 使用 `done`，不是 `skipped_existing`。Trellis 通过 archive 转为 `completed`；操作结果及 AC 复核见 `validation.md`。无新业务、Spec 合同或测试需求，复用已接受的业务测试证据，仅运行收尾轻量验证。
