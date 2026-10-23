# RND-504 技术设计（修订 4）

2026-10-23，仅规划。目标基线 `01e6c1a`，源实现 `931d2f6`，原任务归档 `48818e9`。历史修订 2 和验收记录在 `research/history/`，不是本次实施授权。事实、源码定位、测试边界见 `research/current-state.md`；逐文件 blob 比较见 `research/integration-inventory.json`。

本修订吸收全新 architect 对修订 3 的两项 P2，并经主会话独立核实源函数反例；审查及修订追踪见 `planning-review.md`。历史 40 项通过不覆盖这两个恢复窗口，不能直接照搬对应源分支。

## 1. 当前实现与复用决策

当前 `execution._render_and_save_word` 完成 IR→renderer→质量认证，上传候选后以 first-valid receipt 选定唯一主件；`_finish_prepared_result` 物化并重验原件后做 completed CAS。三种恢复入口保留 RND-502/503 的公式/图片来源认证。`result_state.matches_current` 拒绝终态，不能为预览重试放宽。

当前已有 CON-103 状态/复核锁、CON-104 下载分类与后端 action、TR-406 批次生命周期；`FileUploadService._generated_object_key_for` 已按每次 file_id 隔离所有生成件。当前没有 preview port/adapter、类型、状态、策略和接线。开发质量矩阵仅给出外部 render_docx.py 的视觉证据命令，不是正式任务预览服务。

历史源实现已有完整离线合同，三个模块本轮复跑 40 项通过。源改动 37 个路径，其中 12 个在目标缺失、25 个已经存在；已有文件中部分与源父版本相同，其他已经继续演进。决策：复用新增模块和测试，逐 hunk 接入当前 owner；不整体 merge/cherry-pick 或复制旧共享文件，不引入后续 RND-505/506、QA-601 代码。源测试通过不代替目标集成门。

## 2. 模块边界与唯一 owner

| Owner | 责任与复用方式 |
|---|---|
| `app/services/preview/{models,provider}.py` | 复用不可变策略、结果、局部错误及 WordPreviewProvider Protocol；只消费 bytes/策略，不导入 DocumentIR、任务仓储或翻译。 |
| `app/services/preview/{sandbox_adapter,executor_protocol}.py` | 固定进程协议、校验、deadline、终止和临时目录；不拥有质量/任务/Artifact 选择。 |
| `app/domains/document_jobs/{preview,preview_state}.py` | 应用编排及纯 claim/finish/ledger 规则；选择当前 receipt、登记证据、内部单独重试。 |
| `app/domains/document_jobs/quality_state.py` | 最小贡献合成，保守保留未知质量，仅替换预览贡献；不实现新检测或 QualityRun。 |
| 当前 `result_state.py` / `delivery_state.py` | 唯一主件、generation、已发布保护、质量及复核失效；适配现有公式降级，再合成预览贡献。 |
| 当前 repository 与 file/SQLite/MySQL adapter | 复用同 job 锁/短事务，窄 claim/finish；不在锁内做 Provider、渲染、文件或网络 I/O。 |
| 当前 `FileUploadService` / `result_registration.py` | 共享独立 file_id 对象键、metadata-first 预览候选及生命周期；不另建 Artifact Store。 |
| `Settings` / `build_runtime` / `AppRuntime` | 既有配置入口与注入；策略可追溯，生产默认 disabled。 |

该 port 是实际 I/O 与测试替换边界。沿用模块化单体，不增队列/微服务/通用插件框架，也不将进程转换塞入 renderer 或 docx_quality。

## 3. 数据流

1. 新任务创建时冻结 `request_snapshot.word_preview` 的非敏感策略/profile hash/预算；普通 retry 复用快照，clone 沿用当前保留/刷新配置语义。旧任务无字段不自动补跑。
2. 原 renderer、IR/OOXML/公式/图片认证和候选选定顺序保持。receipt 物化后重验原 DOCX，再在最终 completed CAS 前运行 `ensure_initial`。
3. 读取同一 descriptor，检查归属、uploaded/有效期、size 和 SHA-256；主件读取或身份失败仍是原主产物失败，不能当成普通预览问题。
4. 锁内 claim 当前来源和请求，持久化预算/lease；锁外执行 Provider。先登记 PDF/pages，最后登记 immutable manifest；锁内按来源、revision、request 与 token 提交唯一当前引用。
5. 可靠提交的普通预览失败使质量 blocked，但执行可完成并保留可下载 DOCX。busy/有效租约时保持原任务等待重投，不误称完成；metadata 不可确认传播原存储失败。
6. 已完成未发布任务可经受权 `DocumentJobService.retry_word_preview` 只重试预览；不改 execution status/stage、generation、result、receipt 或原 timeout，不调用 MinerU/AI/renderer。
7. 现有 files/download 只承认当前 manifest 引用。后续页映射/审核任务可复用该服务，但本次不实现其路由/前端。

legacy 明确历史主件没有 receipt 时保留原完成/下载行为，不扫描猜身份或伪造 receipt；若策略 required 则 unavailable+blocked，内部预览重试 conflict。三种原结果恢复入口均须回归。

## 4. Provider、fake 和生产配置

签名复用：`WordPreviewProvider.render(docx: bytes, *, policy: PreviewPolicy) -> PreviewResult`。

- result：PDF bytes、正整数 page_count、按 `0..n-1` 的可选 PNG、provider ID/version、profile SHA-256；不含 block ID/bbox/source spans/任务仓储或服务器路径。
- failure：稳定 PreviewFailure code/retryable，白名单消息；未知异常形成 preview_unexpected_error，不把原 stderr 或正文输出。
- fake：只在测试依赖注入，记录调用并返回合法合成 PDF/PNG 或明确错误；Settings 不得出现 fake backend。

复用 Settings 的 `word_preview_*` 字段，backend 仅 disabled/sandboxed，required/render_pages 默认 false，profile ID/hash 默认 unconfigured/全零标记。launcher/profile 路径来自受控部署配置，不能来自用户、文件名或任务参数。实际启动要求绝对常规文件、固定 launcher SHA-256、原 profile 字节 hash、协议/profile 身份一致及非空 approval_reference。

策略初值沿用已接受实现：输入 50 MiB、PDF+页面合计 100 MiB、200 页、单页 20M 像素、临时目录 512 MiB、CPU 60 秒、内存 512 MiB、16 进程、单次 60 秒、run 125 秒、最多 2 attempts、每当前来源最多 16 个 request keys。均有严格边界，不是已校准生产 SLA。生产 profile 必须覆盖限制；不能仅把 bool 或配置存在当作已证明隔离。

本机能定位 soffice/pdftoppm/Docker，仅证明可执行文件存在；本会话没有启动它们，也没有验证生产版本、沙箱或字体。实际 engine/validator/font/profile 的批准和部署是 production_ready 门，缺失时 disabled，不裸跑、不安装兜底、不采购 SaaS。port/fake 与正式 adapter 协议可以在没有该依赖时完成范围内开发。

## 5. 固定进程协议与资源边界

复用 `word-preview-exec/v1`，本任务交付 adapter 和协议符合性；实际部署 launcher 实现 Office 引擎、完整 PDF 解码与隔离，不把协议设计留给未来。

- describe argv：`[absolute_launcher, describe, --protocol, word-preview-exec/v1, --result, capabilities_json]`。
- render argv：`[absolute_launcher, render, --protocol, word-preview-exec/v1, --request, request_json, --result, result_json]`，shell=False；cwd 为 attempt 私有目录。环境白名单，禁止继承 API/存储/数据库密钥。
- 固定输入 `source.docx` 只读副本，输出仅 `out/preview.pdf` 和按零基序的 `out/page-000000.png` 等。输入 hash/size/profile/预算进 request；结果回报同一输入/profile、provider/version、页数及文件 MIME/size/hash/尺寸。
- describe 必须有 engine/validator 版本、完整 PDF 解码能力及所需 PNG 能力；能力声明只作一致性验证，真实沙箱证据另验。adapter 复算 hash/size，检查页序和输入未变化，不能仅凭 PDF 魔数或文件存在认成功。
- 0 仅完整合法 ok；20=input_invalid，21=resource_exceeded，22=provider/profile/sandbox unavailable，23=output_invalid，24=永久 engine_failed，25=暂态 engine_failed；未知/矛盾退出或 JSON=unexpected/output invalid。只有明确暂态和 timeout 可继续消耗预算。
- 输入在隔离前有界检查 ZIP 条目、总解压量、压缩比、CRC、必需 OOXML；按解码 XML 语义拒绝宏、活动嵌入、DTD/实体，覆盖 UTF-8/UTF-16 和重命名 part；正常超链接不授予联网许可。
- 输出限制大小后读取，仅允许常规非 symlink 文件和固定相对路径；拒绝路径穿越、绝对路径、FIFO、目录及硬链接别名。PNG 验证 CRC/解压/尺寸/像素预算，PDF 完整解码/页数由批准隔离 validator 负责。
- adapter 管理单次和 run 剩余 deadline、新进程组、TERM→有限 grace→KILL→wait 及本次目录清理；launcher 必须终止整个隔离域。CPU/内存/进程/网络/挂载等不能只靠 subprocess timeout 实现；运维需实证无网络、无宏、私有挂载、非特权和资源限制。

正式 adapter 必须真实运行 tests-only 子进程的成功/失败协议测试。该测试不称为真实 DOCX 排版、隔离证明或 Microsoft Word 验收。

## 6. 持久化、幂等和并发

私有可选 `DocumentJobRecord.word_preview_state=None` 使用已有 JSON payload，不新增 SQL 列/表/DDL/backfill。包含当前来源 generation/result ID/hash/profile、revision、current_request_key、max_runs_per_result，以及 `runs_by_request_key` 账本：run ID/fingerprint、actor/reason hash、status、attempt/max_attempts、固定 deadline、retry_at、lease token/expiry、manifest/error/时间。另为当前 attempt 保存最小登记阶段（未开始 Artifact、已进入登记、当前终态 manifest 已确认）及确认所属 attempt；这是中断分类证据，不是通用事务日志。缺少阶段的历史在途记录按未知处理，不默认成“未开始”；历史终态需核验原 manifest 的完整身份后才可作为已确认依据。私有字段不出公开 response、incident、events 或可下载 manifest。

首次 claim 在同 job 序列化点原子登记 key、fingerprint 和 attempt，然后才做 I/O。初始 key 为保留的 initial；内部重试为规范 UUID，fingerprint 含 tenant/company/job、generation、主件 ID/hash、profile、action、actor/reason hash。

- 同 key 同参返回该 key 的历史 run，不能把 current 当作被重放 run；同 key 异参 conflict。
- A→B→重启→A 不移动 current、不重置预算、不再调用 Provider；只有完整成功 Artifact 仍有效时，新 key 才原子记 fingerprint→原成功 run 关联，不新增实际 run/attempt。历史成功状态不等于当前可用性，失效恢复见 §8。
- 账本当前来源有效期内不 LRU 淘汰；满额拒绝新 key，既有 key 仍可幂等读取。失败/忙碌不消耗虚构新 generation。
- 有效 lease 返回 busy；过期接管须先按下述登记阶段分类，允许继续 Provider 时才消耗原 run 剩余 attempts，不能延长 run deadline。finish 必须匹配来源、当前 request/run、revision、token、lease 和 deadline；不能把 exhausted 一律当成已完成。
- initial 仅 running/uploading+receipt，受原任务 timeout；独立重试仅 succeeded/completed+当前 receipt，使用独立固定 run deadline。published/归档/删除/取消/失败/旧代均拒绝。
- 预览 CAS 只更新私有状态、预览质量贡献及必要复核失效；原执行 CAS 仍拒绝终态，不能借用其 allowed_statuses 绕过。

三 adapter 共享纯规则：file 稳定 lock 文件，SQLite BEGIN IMMEDIATE，MySQL 短事务 SELECT FOR UPDATE，保留同连接质量列投影、commit/rollback。TR-406 的批次方法和锁协议保持，不能用源旧文件替换当前 adapter。真实 MySQL/部署 FS 是写者启用门，fake SQL 不能证明真实锁。

### 6.1 登记中断与预算耗尽的收口

源 `claim_preview` 的 exhausted 分支会在没有当前失败 manifest 时返回 failed/blocked，源应用又把该 disposition 视为完成；这段不能原样复用。attempt 领取时初始化“未开始 Artifact”；首次调用任何 PDF/page/manifest 登记（包括失败 manifest）前，必须以同一来源、current/revision/attempt/token 在 job 锁内标“已进入登记”，成功后才允许文件副作用。增加的窄标记 CAS 与 claim/finish 由同一 owner 管理，仍不在 job 锁内执行文件 I/O。

只有完整登记的终态 manifest 与本次来源/run/attempt/描述符一致，并随窄 finish CAS 选中，才能标“终态已确认”。新 attempt 必须重置阶段，旧 attempt 的失败 manifest 即使保留也不能作为新 attempt 的完成证明。恢复分三类：

| 锁内状态与可证明事实 | 处理 |
|---|---|
| 当前 attempt 已确认终态 manifest | 复用该终态；普通可靠预览失败可按原规则 succeeded+blocked，不再调用 Provider。 |
| 确认尚未进入任何 Artifact 登记，且有剩余 Provider 预算 | 可按原 lease/token 接管规则重试 Provider，原 attempts/deadline 不重置。 |
| 尚未进入登记但 Provider 预算耗尽 | 不直接完成；仅在原 run/job 截止仍允许时，用窄的失败收口领取登记本 attempt 的失败 manifest，禁止再调用 Provider或增加 attempt。收口仍比较当前来源/revision/token、使用不超过原 deadline 的 lease，先标登记阶段；登记/确认成功才可按普通失败完成。不能延长原 deadline；来不及确认则保持不可完成并显式失败。 |
| 已进入登记但未确认，或在途阶段未知 | 存储结果未知。即使还有 Provider 预算，也不能以新一次渲染或 exhausted 掩盖；本修订采取失败关闭，不自动推测对象/metadata 已成功，不引入通用事务/自动对账。 |

未知登记记录保留来源/run/attempt、阶段、候选 metadata/对象及局部 `preview_storage_failed`。initial 沿原 uploading/oss_failed（原任务总超时先发生时仍 document_job_timeout）失败，绝不能返回 preview_finished=true 再 completed。已成功主任务的独立重试遇到同类情况，保留主 DOCX 和既有 execution 终态，内部调用显式返回存储失败并保持预览 blocker，不伪装为成功重试。重复相同 key 不得把该未知失败在下一次历史重放中变成“完成”。

这不保证每个进程退出都能自动恢复为可下载草稿；已可靠留证的普通预览失败与存储不可确认是不同合同。若实现要加入自动确认恢复，须另行说明来源证明/幂等边界并回规划评审。过期/删除、换代、取消、published 和原 job timeout 始终优先；旧 token 或迟到确认不能复活状态。

## 7. 质量合成与当前公式行为适配

复用最小 `checks_v1.word_preview`，首次保守捕获原 quality 为 `__unattributed__`，保留其他 summary；非法结构显式拒绝。合成优先级 blocked > pending > warning > passed。普通显式 quality 写入更新未归属贡献，包括同值 blocked；普通进度/receipt patch 不重复捕获聚合后的 preview blocker。通用 summary patch 不能删除或改写 producer 贡献，producer 上下文仅由窄内部 CAS 提供。

| 场景 | 预览贡献 | 总体影响 |
|---|---|---|
| disabled、required=false | pending/unavailable | 未检查；不伪造 passed |
| required 不可用，或实际 Provider 失败 | blocked | 保留主件，可内部下载；拒绝批准/发布 |
| 预览成功 | passed | 只替换自身贡献，保留基础 pending/warning/blocked |
| 开始独立重试 | 保留前次 blocker | 成功前不先清质量 |
| 主件读取/metadata 不可确认 | 不作普通预览成功收尾 | 原 oss_failed/恢复语义 |

当前 `result_state.patched_job` 在 selected receipt 完成时合并 formula_summary，原质量 passed 且有 fallback 才降 warning；源旧实现没有这段。必须以锁内选定 receipt 为准保留该规则，并在质量合成前合入其非预览结论：读取非预览基础（已有 __unattributed__，否则原质量），仅原 passed 遇 fallback 变 warning；未改变时不能把当前聚合的 blocked 显式写回基础。summary 保留 checks_v1 与其他 owner，绝不能用旧全量摘要覆盖较新值。

顺序为：原 published 不可变拒绝→换代/真正换件重置→选定 receipt 的现有公式摘要/降级合并→预览与非预览贡献合成→按最终 blocked 撤销批准及交付晋升→模型验证。不能在合成后另写 quality_status 绕过批准失效。此处只适配已存在的公式语义，不新增公式检查、token 或 renderer 行为。

需证明：基础 passed+fallback+preview失败为 blocked，成功重试后 warning；基础 pending 仍 pending；无 fallback 的普通完成不能把自身 blocker 永久写入未归属贡献；并发同值 blocked 不被成功清掉。旧批准、ready/published 不随恢复复活。

## 8. Artifact、生命周期和授权

新增 `word_preview_pdf` / `word_preview_page` / `word_preview_manifest`。复用现有 document_files，word-preview/v1 manifest 记录来源 ID/hash/generation/profile、run/attempt、状态/错误、provider/version、页数、PDF/page 的 ID/hash/MIME/size/页序/尺寸和 UTC 时间。无原始正文、服务器路径、lease、actor/reason/request 账本。

每次尝试均新 file_id 和不可变对象；使用当前共享 `_generated_object_key_for`，所有生成件继续含 file_id，不迁入源旧的 preview 专用 `_object_key_for` 分支，不修改其他 file_type 路径。原文件名只作下载名，不能成为共享可覆盖 key。

preview 登记必须先 insert `pending_upload` metadata（严格 `word_preview_artifact_protocol=1`），再写对象，最后在已有 file 锁内确认 uploaded/etag。insert 失败不写对象；写/确认失败或响应丢失显式传播，保留可追踪记录，不通过失败 manifest 掩盖。禁止代理上传内部候选；原 generated_word 物化限制不放宽。

成功输出全部校验登记后才能提交当前 manifest；部分/落选记录保留但不授权。失败 manifest 只提供安全诊断，不代表成功 PDF。有效期不长于主件且遵守现有按类型保留策略；不新增清理框架，不复活 expired/deleted，也不删除旧证据或主件。继承现有限制：墓碑之后的迟到对象写可能残留，不能承诺全部物理回收或 S3 真实删除。

### 8.1 成功复用与生命周期失效恢复

源代码仅凭 run.status=succeeded 建 alias，会把过期 manifest 永久复用。新 key 的复用前置必须核对当前成功 manifest、PDF 和策略所要求的全部 pages：来源/result hash/generation/profile/run/attempt、归属、uploaded、期限、MIME/size/hash/页序与描述符均一致，且对象确实可读；主件本身也须仍有效。复用检查在锁外执行，形成绑定 source/current run/revision/manifest 与文件描述符、最早到期时刻的内部观测；不能将未经检查的布尔值交给任意调用者绕过入口。

窄 claim 在同 job 锁内先核历史 key/fingerprint，再比较该观测的 source/current run/revision/manifest，并按锁内当前时间检查未到最早到期点；只在条件一致时 alias。条件变化返回 stale/busy 或重新读取，不借旧观测消耗新预算/提交旧引用；锁内不读对象或跨文件仓储开启事务。

- 有效完整成功证据：新 key alias 原成功 run，原 run/attempt/current 不变。
- 主件有效而 manifest/PDF/必需 page 过期、删除或已确认不存在：新 key 在既有 key/run/attempt 额度内创建新 run，追加全新预览文件；同 CAS 将预览自身贡献置为失效 blocker，成功前不能继承旧 passed。不改 generation/result/receipt，不重渲染 DOCX，不复活旧文件，不恢复旧批准。
- 读取超时、连接错误或无法确认 metadata/对象：是存储未知，显式传播，不当作“文件缺失”启动新 run。描述符/hash/来源不一致按完整性错误失败关闭，不通过重新生成来掩盖。
- 旧 key 始终只返回原历史 run，不移动 current、不再调用 Provider或消费预算。内部重试结果需区分历史 run 的执行状态和当前 Artifact 可用性；旧成功但已失效不能报告为可用成功。
- 主件无效、deleted/archived/published、额度耗尽等继续原拒绝合同；满额不能为恢复而淘汰历史 key。

文件在锁外检查与锁内 claim 间仍可能过期/删除；本项不承诺 job/files/storage 跨域原子事务。alias/新 run 收口后，在内部结果宣称“当前可用”前重验；若此时失效，明确返回不可用/存储错误，不回滚已消费 key、不以同 key 偷开新 run，后续新 key 才按上述规则恢复。下载/本地 Token 读取和 S3 签发仍独立核对当前引用及实际期限，最后瞬间的失效不能获越权授权。

任务列表、下载授权和本地 Token 实际读取共同核对 current manifest、来源/hash/generation/profile、归属、uploaded/有效期及描述符。不得用“同 generation 文件” fallback 授权 preview。S3 签发前检查当前引用，TTL ≤既有上限/主件/预览剩余期；已签 URL 不即时撤销。保留 CON-104 主 DOCX classification/warning 与授权/审计，不让 preview 变成另一用户主文件。

## 9. 模型、API、数据库、前端和兼容

- 模型：可选私有 preview_state、新内部事件类型和文件类型；不增加 DocumentIR 字段，也不增加 execution/quality/review/delivery 枚举值。
- DB：新增私有 JSON payload 和窄仓储方法，沿用四字段投影。无 DDL、DROP、历史回填或二进制入库。CON-103 显式迁移和真实写者启用条件保持，不重新执行。
- OpenAPI：不新增 HTTP preview/retry/publish 路由；既有文件类型为 string、quality_summary 为 JSON，预期 snapshot 不变。只按实际公开差异更新，若需要新公开合同先回评审。
- 前端：无页面、编辑器、路由、类型生成或 available action 新字段。继续消费后端状态和 CON-104 actions。publish.eligible 仍仅核心资格，enabled 仍 false；现有 preview_unavailable 表示发布预览验证尚未接通，publication_unavailable 保留。登记预览不自动启用发布，也不宣称实际发布 E2E 通过。
- 历史记录：缺 snapshot/state 可读，不补预览、不猜批准；旧 result receipt/公式/图片报告恢复合同不变。新策略/Artifact 不重写历史 DOCX 或冻结资源。
- 滚动部署：先暂停相关 API 内联/Worker 写者，再统一部署可保留新字段的兼容版本；旧 Pydantic writer 可能丢私有字段，不能无条件混部。新读者读旧记录可行不等于旧写者写新记录安全。

## 10. 安全、隐私和可观测性

只使用既有存储 backend。沙箱只接收选定 DOCX 的私有副本，不挂载源 PDF、资源库、宿主目录或密钥；无新 SaaS/AI/URL 外发。固定 argv/shell=False、无网络、宏拒绝与隔离是共同防线，不能拿输入预检替代生产隔离证明。专有 PDF/DOCX/页面图不入 Git。

复用 business logger、job events 和内部重试审计；记录安全的 job/generation/result hash、run/attempt、profile/provider/version、页数、duration、错误码。保留当前 renderer 事件白名单、公式/图片私有报告和 incident 投影，不复制源旧自由 metadata 展开。现有事件与状态分步提交仍无 outbox；事件追加失败保留已提交状态并记录可见诊断，不触发重复转换。主数据或 Artifact metadata 失败不得由此吞掉。

不增加 REL-702 监控工程。production_ready 要求实际批准引擎/解码器、字体、隔离/终止/清理、真实 MySQL/部署 FS/对象存储和必要 Word 人工证据；adapter_contract_ready 只代表正式协议测试通过。

## 11. 迁移、回滚与停止点

本轮只恢复同一任务的规划身份，不恢复业务代码。后续实施只做列明的源增量集成，不迁历史文件、不更改已发布件、不重跑历史任务。依赖 gate 或共享 owner 实际不符时先停。

未接线前可撤回未使用新模块；接线后先停新预览和相关写者，保留识别 preview_state/checks/receipt 的兼容代码。disabled 不清 blocker、不恢复批准、不改冻结快照；在途不可用按策略留证。保留新增 payload、manifest、文件记录和审计，不 DROP/删历史。回滚不能退到会丢 preview/质量/receipt 字段或覆盖对象键的旧写者，也不能用截图策略替代原生表格。

停止条件完整继承 PRD；生产依赖未经批准时保持 disabled。若 port/fake 无法完成本项，或集成需跨越页映射/质量/发布 owner，必须回规划评审。
