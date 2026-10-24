# WordPreviewProvider 与任务预览合同（RND-504）

## 1. 范围与触发

修改 `app/services/preview/`、DocumentJob 预览状态/重试、quality 贡献、预览 Artifact、下载引用校验或运行时 preview 策略时必须遵守本合同。本次以历史 `931d2f6` 合同为基础，保留当前 CON-104/TR-406/RND-502/503，并加入批准修订 4 的中断确认与生命周期复用边界。它只拥有生成当前主 DOCX 的预览证据；不拥有 renderer、RND-505 页映射、RND-506 页级检查/QualityRun、QA-602 公开 API/UI 或 QA-605 发布。

默认 backend 为 disabled；本地测试的 protocol adapter 可用，不代表生产引擎或视觉通过。只读预览不修改主 DOCX、DocumentIR 或发布件，不重新调用 MinerU、翻译 Provider、Prompt、术语集或 renderer。

## 2. 签名与 owner

- `WordPreviewProvider.render(docx: bytes, *, policy: PreviewPolicy) -> PreviewResult`：只消费 bytes 与策略；错误使用 `PreviewFailure`，不得泄漏路径、stderr 或客户内容。
- `claim_document_job_preview(job_id, *, request: PreviewClaimRequest, observation: PreviewArtifactObservation | None = None) -> PreviewClaim` / `finish_document_job_preview(job_id, *, request, revision, lease_token, status, manifest_file_id, error_code, retryable, evidence) -> DocumentJobRecord | None`：窄仓储 CAS，file/SQLite/MySQL 共用 `preview_state.py` 纯规则，复用 CON-102 的同 job 序列化点；I/O 在锁外。PreviewClaim 保存命中的 run 快照，不能把 current 当成被重放 run。
- `begin_document_job_preview_registration(job_id, *, request, revision, lease_token, attempt) -> DocumentJobRecord | None`：在首个 Artifact 副作用前比较当前来源/revision/attempt/token，标记登记中并递增 revision；finish 使用返回的当前 revision。三 adapter 复用同 job 锁，不写文件或做网络 I/O。
- `DocumentJobService.retry_word_preview(job_id, *, user, reason, request_id, trace_id=None) -> PreviewRetryResult`：受权内部应用入口，校验 owner/Admin、tenant/company、reason、规范 UUID request ID 及当前 receipt。返回 job 为当前权威记录，run 为该 request key 命中的历史或新 run，available 单独表示当前证据可用；历史重放不移动 current。没有新增 HTTP 路由；执行 CAS 仍拒绝终态。
- `preview_download_ttl(job, record, file_repository, file_service, *, expires_seconds) -> int`：领域层重新核当前完整预览，两个现有 S3 签发点均把 TTL 限至全部必需证据（包括 manifest/pages）最早期限与原 file/source 上限。不能只取所请求 PDF 的期限，绕过更短的当前 manifest。
- `verified_current_preview_files(job, file_repository, file_service) -> dict[str, DocumentFileRecord]`：一次观测返回本调用已验证的预览文件集合；列表一次取用并比较完整 Record，单件授权每次独立调用。取代逐文件重复完整观测的私有 guard，不提供跨请求缓存或跳过校验参数。
- `quality_state.py`：只维护最小贡献合成；通过 `result_state.patched_job → delivery_state_patch` 在原锁内执行，published 检查先于质量合成，批准失效使用合成后的状态。
- 文件二进制由 `FileUploadService` 管理，任务 service 选择可见文件；不增加独立 Artifact Store、队列或转换流水线。

## 3. 请求、持久化与执行协议

### 来源与策略

Settings 使用既有环境配置入口（环境键为对应字段的大写形式）：

| 字段 | 默认/约束 |
|---|---|
| `word_preview_backend` / `word_preview_required` / `word_preview_render_pages` | disabled / false / false；backend 仅 disabled、sandboxed，fake 不能配置。 |
| `word_preview_profile_id` / `word_preview_profile_sha256` | unconfigured / 全零 sha256 标记；实际 profile 必须固定身份/hash。 |
| `word_preview_launcher` / `word_preview_profile_path` | 空；非空启用时必须是批准的绝对路径，不能来自任务参数。 |
| `word_preview_timeout_seconds` / `word_preview_deadline_seconds` | 60 / 125；单次与 run 总预算，不能超出当前 claim deadline。 |
| `word_preview_max_attempts` / `word_preview_max_runs_per_result` | 2 / 16；消费预算持久化，不靠内存重置。 |
| `word_preview_max_input_bytes` / `word_preview_max_output_bytes` | 50 MiB / 100 MiB；输出总量含 PDF+页面。 |
| `word_preview_max_pages` / `word_preview_max_page_pixels` | 200 / 20,000,000。 |
| `word_preview_max_temp_bytes` / `word_preview_max_cpu_seconds` / `word_preview_max_memory_bytes` / `word_preview_max_processes` | 512 MiB / 60 / 512 MiB / 16，批准 profile 必须覆盖请求资源上限。 |

部署 profile 为有界 JSON，精确原始字节的 SHA-256 与配置及快照一致；包含 `profile_id`、`protocol_version`、`launcher_sha256`、非空 `approval_reference`，sandbox 的 no_network/no_macros/private_mount/unprivileged/resource_limits/terminate_domain 均为 true，limits 明确 temp/CPU/memory/process 上限。实际批准证据不能由这些自报布尔值替代；只有批准部署 owner 可配置 profile。缺失、不匹配或能力不足失败关闭。

新任务在 `request_snapshot.word_preview` 固化非敏感策略/profile hash/预算；普通 retry 使用原快照，历史任务无快照不自动补跑。不得把 launcher 绝对路径、密钥或部署私有指纹写入快照。preview 在选定 receipt 物化并完成当前公式/图片原件认证后、最终 succeeded CAS 前运行，校验同一 file ID、SHA-256、size 和 generation；主件读取/hash/metadata 失败保留原错误合同。

`DocumentJobRecord.word_preview_state` 是可选私有 JSON payload，不加 SQL 列/表/回填。当前来源身份绑定 generation/result ID/hash/profile，账本 `runs_by_request_key` 保存 run、fingerprint、预算、固定 deadline、lease 和 manifest；current request 指针只选账本项，不复制可修改状态。私有账本/lease/actor/reason 不出 presenter、incident、事件或可下载 manifest。

首次消费 key、建立 run、claim attempt 在同一 job 锁内提交，先于 provider、事件和文件。先查历史 key/fingerprint，再决定成功复用或新 run；同 key 同参数返回历史 run，不改较新 current，不增加预算；同 key 不同参数 conflict。成功复用须先满足下方生命周期观测合同，不能只看 run.status。成功复用的新 key 也必须在同锁持久化 fingerprint/actor/reason 与原成功 run 的关联，保留同一 run_id、current、attempt 和文件，不重新调用 provider。账本上限按已消费 key（包括成功复用关联）计数；实际 run/attempt 按 run_id 识别，不把关联行当成新执行。账本在当前来源有效期内不按时间/LRU 淘汰，上限拒绝新 key、保留旧 key 的幂等查询。A→B→重启→A 不得重新调用 provider。旧 source/旧 run/token/expired lease 不得完成或接管当前 run。

首次运行受原任务 timeout 约束；成功任务的内部预览重试固化独立 `run_deadline_at`，不得重置原任务 status/stage/timeout。接管不能延长 deadline 或重置已消费尝试。cancel/failed/删除/归档/published 不接受迟到提交；legacy 无 receipt 预览重试 conflict，既有 DOCX 下载保持。换代/换件清当前预览/贡献，不删历史 Artifact。

### 当前 attempt 登记阶段与中断（修订 4）

claim 初始化当前 attempt 为未登记；首次 PDF/page/manifest（含失败 manifest）副作用前，必须通过同来源/current/revision/attempt/token 的窄 CAS 标为登记中。只有完整当前来源/run/attempt 的终态 manifest 经 finish 选中，才是已确认；新 attempt 重置阶段，前次失败 manifest 不构成本次证明。历史在途缺字段按未知处理，历史终态仍须核验 manifest 身份。

私有 `PreviewRun.artifact_stage` 为 `not_started` / `registering` / `confirmed`，缺省 None 表示历史未知；`confirmed_attempt` 绑定确认的 attempt，不能以 run 曾有 manifest 推断本次已确认。

历史当前终态缺阶段时，完整观测通过后可在同次 claim 锁内确认；新 UUID key 和同当前 key 都应支持，不能要求内部重试入口提交其不接受的保留 key `initial`。确认与 alias/新 run 同锁提交，观测比较使用升级前 revision，最终再递增；历史在途缺阶段始终未知，不由此升级。

- 已确认终态：可复用，普通可靠预览失败允许主任务 succeeded+blocked。
- 确认尚未登记且还有预算：过期 lease 按原 attempts/deadline 接管；不延长 deadline。
- 确认尚未登记但 Provider 预算耗尽：仅在原 run/job deadline 内领取窄失败收口，禁止再调用 Provider 或增加 attempt；标登记中后登记失败 manifest，确认成功才可完成。
- 登记中未确认或阶段未知：失败关闭为存储不可确认，即使预算尚余/耗尽也不能通过新渲染、exhausted 或历史 manifest 伪装完成。本修订不做自动对账/通用 WAL。

initial 保持原 uploading/oss_failed 失败语义（总任务 timeout 优先）；内部独立重试保留既有 execution 终态及主 DOCX，显式报告存储失败并保留自身 blocker。重复同 key 不把未知状态变为已完成，迟到 token 不得提交。

### 成功复用的生命周期观测（修订 4）

新 key alias 前，锁外确认当前成功 manifest、PDF、策略要求的全部 pages 以及主件仍可读：核对 source/generation/result hash/profile/run/attempt、tenant/company/job、类型、uploaded/期限、MIME/size/hash/页序和描述符。观测绑定 source/current run/revision/manifest、已核文件描述符及最早到期点；锁内仅比较该身份和当前时间，不做文件 I/O，也不接受任意外部布尔值作为授权证明。

`PreviewArtifactObservation` 是仅内部使用的冻结 dataclass，包含 generation/result/hash/profile、revision/current request/run/attempt/manifest、文件描述符、earliest_expires_at 和 available；由受权应用检查产生，不能通过公开 payload 或请求注入。

有效观测允许关联同一成功 run。主件有效而预览确定过期/删除/不存在时，新 key 在原额度内创建新 run/全新 Artifact，同 CAS 先令自身 blocked，保持主 DOCX/generation/receipt 不变。存储超时/连接错误/未知不当作缺失；描述符/来源/hash 不符按完整性错误失败关闭，不通过再生成掩盖。观测后 current/revision/期限变化返回 stale/busy 或重读。

旧 key 始终重放原历史 run，不移动 current、不新消耗预算或调用 Provider；内部结果区分历史执行成功与当前 Artifact 可用性。返回“当前可用”前重验；跨 job/file/object 无原子保证，后验失效明确返回不可用/存储错误，不回滚 key、不以同 key 偷开 run。后续新 key 可按规则恢复。下载和 Token 仍独立校验，S3 旧 URL 仅有界期限而非即时撤销。

### 质量贡献

`quality_summary.checks_v1.word_preview` 为预览拥有的贡献；首次保守捕获已存 quality 为 `__unattributed__`。非法/未知结构 conflict，不猜默认覆盖。优先级 blocked > pending > warning > passed，全部已知通过才能 passed。通用显式 quality 更新（包括同值 blocked）更新未归属贡献；普通 progress/receipt patch 不重复捕获。通用 summary patch 不得删除/改写 producer 贡献；producer 上下文只由内部窄 CAS 传入。

失败或 required-unavailable 将自身置 blocked；disabled 且非必需置 pending；开始 retry 保留旧 blocker。成功仅将自身置 passed，恢复可证明的原 pending/warning/passed，保留其他/未知/并发 blocker；不恢复旧批准或提升 delivery。既有内容完整性失败继续 fail-closed，不把所有 OOXML flag 升级 fatal。

选定 receipt 的公式摘要先按当前 `result_state` 规则合并：非预览基础 passed 遇 formula_text_fallback 降为 warning，原 pending 保持；不得把聚合后的预览 blocked 再捕获为基础。顺序为 published 不可变检查→换代/换件失效→现有公式非预览贡献→预览质量合成→按最终状态撤销批准/交付晋升。成功不恢复旧批准。

### Artifact 与授权

文件类型为 `word_preview_pdf`、`word_preview_page`、`word_preview_manifest`。文件名由服务生成，包含 generation/result/run/attempt/page 身份；物理不可变性使用当前共享 `_generated_object_key_for` 的独立 file_id 路径，所有生成件保持相同规则，不恢复历史 preview 专用路径分支。`word-preview/v1` manifest 保存安全来源、run/attempt/profile/provider/version、结果及文件 ID/hash/MIME/size，不能含私有请求或 lease。

所有输出校验并登记后才选中成功 manifest；部分输出/旧 attempt 不可见。三个 preview file_type 的 FileUploadService 登记先创建带 `word_preview_artifact_protocol=1` 的 pending_upload metadata 和独立 file ID/key，再写对象，最后经既有文件锁确认 uploaded/etag。初次 insert 失败不写对象；对象或确认失败保留可追踪 pending，不选 manifest，不把未完成对象提前标 uploaded。禁止代理上传内部候选；到期 pending 仅凭严格类型+marker 进入既有 expire/retention，普通待上传源文件与 generated_word receipt 物化规则保持。

PDF/page/manifest 登记的对象/metadata 无法确认必须传播原存储失败，不能捕获成普通 preview failure 后返回 completed=true；provider 自身明确失败且诊断 manifest 成功持久化时才允许 succeeded+blocked。保留 receipt/主件与已登记候选，不承诺跨 job/file/object 的原子事务。保留期不超过主件，过期/删除不可复活，失败候选交既有保留策略处理。默认下载始终为主 DOCX；blocked/unreviewed 内部下载继续可用。

新增预览 source/Artifact 的 metadata、对象读取、写入与确认边界须使用安全固定存储错误，不能把原始系统/SDK异常字符串传入公开 job.error_message、事件或日志。仍向外失败为原 uploading/oss_failed，不能吞为可靠Provider失败；独立重试也显式失败。生命周期缺失和身份/幂等冲突保持自己的语义，模拟进程退出的 BaseException 不捕获。测试以含路径/敏感canary的异常验证投影及receipt/pending保留。

沿用 CON-102 的物理回收限制：若 retention 已将 pending 标为 deleted 后，对象写入才迟到完成，uploaded 确认仍拒绝，但二进制可能继续存在，后续 retention 不会重扫 deleted 墓碑。保留 metadata/key 可追踪，应用不选入当前 manifest、不签发下载；不能把“metadata 不复活”表述为“任意迟到二进制已物理回收”。本任务不扩建跨存储事务或新的清理框架。

应用授权检查当前 manifest+source、归属、uploaded、expiry/hash，preview 不走普通同 retry_count fallback。本地 HMAC 读取时重校验。S3 签发前检查，TTL 取既有上限与完整当前预览（含 manifest/必需 pages）和主件剩余有效期之小；直连读取没有应用重校验，旧 URL 不保证立即撤销，不为本任务引入下载代理。

一次文件列表请求只建立一次完整当前预览观测，再按其中已验证的文件身份/描述符过滤。不能对每个 page 重读并解码整套预览，避免页数 N 时放大为 N² 的对象读取/PNG 校验。该观测仅在本次调用内复用，不是全局或持久缓存；Token/单文件下载仍独立重验。未知存储、过期或损坏不能暴露部分输出，多页测试必须核对实际对象读取次数。

### word-preview-exec/v1

固定 argv：

```text
<absolute-launcher> describe --protocol word-preview-exec/v1 --result <absolute-capabilities.json>
<absolute-launcher> render --protocol word-preview-exec/v1 --request <absolute-request.json> --result <absolute-result.json>
```

`shell=False`，cwd 为本 attempt 私有目录，环境白名单不继承凭据。输入只读 `source.docx`；输出固定 `out/preview.pdf`、可选连续零基 `out/page-000000.png`。禁止绝对结果路径、穿越、symlink 和目录；先限大小后读取。

request 必含协议版本、`input={path,sha256,size_bytes}`、profile ID/hash、render_pages、budget_ms，以及 output bytes/pages/page pixels/temp bytes/CPU/memory/process limits。hash 为 `sha256:<64hex>`。result 必含版本、status、input/profile hash、provider/version；ok 需正 page_count、PDF descriptor 和 pages descriptors（index/path/MIME/size/hash/width/height），页面关闭时列表为空。adapter 重算 hash/size/页序；PDF 完整解码与页数校验依赖批准的隔离 validator，不只检查魔数。describe 必须符合固定版本/profile、engine/validator 版本和 PDF/PNG 能力，自报不等于隔离证明。

退出 0 只接受完整有效 ok；20 input invalid，21 resource exceeded，22 白名单 provider/profile/sandbox unavailable，23 output invalid，24 engine failed 永久，25 engine failed 暂态；未知退出为 unexpected error，不能从文件存在或 stderr 猜成功。只允许明确暂态/timeout 消耗后续预算。超时终止整个进程组，TERM 后有限 grace 再 KILL、wait，成功/失败都清私有目录。launcher 部署 owner 保证隔离域内无脱离子任务残留。

输入校验限制 DOCX ZIP 条目、解压量、压缩比、CRC 和必要部件，拒绝宏/活动内容。宏/活动检查基于已解析 XML 的 ContentType 和 relationship Type，不能依赖 ASCII 原始字节或约定 part 名；UTF-16 与重命名 part 同样拒绝，解析器在字符解码后拒绝 DTD。普通超链接保持兼容，不授予网络访问。PNG 当前接受非交错 8-bit gray/RGB/gray-alpha/RGBA（color 0/2/4/6），检查 CRC、有界完整解压、尺寸与 filter；其他编码显式 output_invalid。launcher 必须按此配置编码，不能只写正确签名/尺寸而缺像素。读取结果使用 nonblocking/no-follow 打开并 fstat 拒绝 FIFO/非常规文件，避免时限外阻塞；未知退出在读取 result 前归类 unexpected error。

实际执行域必须禁止网络/外部资源更新、非特权、单次挂载并限制 CPU/内存/磁盘/进程；仅临时目录/subprocess timeout 不能证明 sandbox。缺部署证据保持不可用，不能 fallback。

## 4. 验证与错误矩阵

| 触发 | 结果 |
|---|---|
| backend disabled，required=false | unavailable/preview_disabled，pending 贡献，无通过证据。 |
| required 且 backend/profile/sandbox 不可用 | unavailable + blocked，主件仍可内部下载。 |
| 暂态/timeout | 有界重试，耗尽 failed/blocked；重投不重置预算。 |
| 损坏输入/非法输出/资源超限 | 永久 failed/blocked，不盲重试。 |
| 主件缺失/hash 或 descriptor 不符 | 保留原 storage/integrity 失败，不降级成功。 |
| 幂等冲突/满额/旧来源/失效 lease | conflict/stale/busy，不新增质量失败或覆盖当前证据。 |
| 成功重试 | 自身 passed；只解除自身 blocker，旧批准不复活。 |
| metadata 不可确认 | 不完成/不晋升，保留 receipt、主件及已写诊断。 |

局部 code：`preview_disabled`、`preview_provider_unavailable`、`preview_profile_unavailable`、`preview_sandbox_unavailable`、`preview_input_invalid`、`preview_timeout`、`preview_resource_exceeded`、`preview_output_invalid`、`preview_engine_failed`、`preview_storage_failed`、`preview_unexpected_error`。顶层转换成功不伪造 render_failed；storage 错误保持原映射。

## 5. 正常、历史与错误场景

- 正常：receipt 选定主件→校验来源→锁内 claim→锁外 provider/Artifact→锁内 finish→原执行 CAS 完成；预览 PDF/page/manifest 绑定同一主件。
- 历史：无 preview 字段的 payload 可读且不自动重跑；无法证明的 quality 保持 pending/blocked。legacy 主件下载不受影响，不能补猜 receipt。
- 错误：仅保存当前 request ID、失败后删去 key、重试时重置预算、成功时直接写 quality passed、用同 retry_count 暴露未提交输出、或退回不认识新 payload 的写者。

## 6. 必要测试与启用门

- `tests.test_word_preview_provider`：正式最小 DOCX；测试 fake 之外经生产 adapter 真实子进程协议成功 PDF/可选 PNG，describe/request/result/hash/profile、退出码、坏路径/schema、超时终止与清理、边界资源。
- `tests.test_document_job_word_preview`：renderer→preview→Artifact，失败主件 ID/hash/字节不变、下载/权限；质量自身恢复与其他/并发 blocked，disabled/required、无新公开路由、private state 不泄漏。
- `tests.test_document_job_preview_persistence`：三 adapter 相同规则；真实临时 file/SQLite 竞争、恢复和 lease；A→B→重启→A、成功后新 key 复用/重启/异参冲突与 cap、claim 后崩溃、stale/delete/archive/published/换代；pending preview 候选过期与禁止复活；最后一次 attempt 的 PDF/page/manifest 登记中断及旧失败 manifest；主件90天/预览1天、PDF/page失效的新 key 恢复、未知存储与观测竞争。fake MySQL 只证明 SQL/调用，不证明 InnoDB 竞争。
- 既有 execution_stages/result_persistence/delivery_state/modes 与关键 FastAPI 下载/范围测试，component OPA228、OpenAPI/current 及项目 release 门；实际执行证据见当前任务 `implementation-validation.md`；历史通过记录不能替代当前候选。
- `adapter_contract_ready` 需要正式 subprocess 成功路径；`production_ready` 还需要真实 engine/validator/font/批准隔离、真实 MySQL/部署 FS 及当前 Word 视觉证据，未满足则 disabled。不能以 fake、像素相似度或 PDF 可打开代替生产视觉验收。

滚动部署须暂停旧写者、统一支持并保留 preview/quality 字段的 API/Worker 后再启用；无 DDL 不代表任意混部安全。回滚关闭 backend/新请求并保留兼容代码、状态、Artifact 和审计；不清 blocker、不回退丢字段 writer、不覆盖发布件、不 DROP。

## 7. 错误与正确做法

错误：

```python
repository.update_document_job(job_id, quality_status="passed")
```

正确：在当前来源和 lease 的 `finish_document_job_preview` 窄 CAS 内只替换 `word_preview` 贡献，由共享质量规则合成总体状态后执行 review/delivery 失效。泛化 quality 更新保留未归属结论，预览成功不获得审核或发布权限。


## RND-505可选导航对象

word-preview/v1成功manifest可含独立版本page_mapping；不更改本合同claim/registration/finish、重放/alias、TTL或发布资格。旧manifest无字段合法；内层未知/坏hash/错binding仅映射不可用，原manifest完整性或存储错误仍原失败。Provider失败不为映射增加文件。新增私有证明/映射的公开出口只投影受控计数，详[页映射Spec](./page-mapping-contract.md)。
