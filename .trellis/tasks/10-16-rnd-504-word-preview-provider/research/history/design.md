# RND-504 技术设计

## 1. 调查基线与边界

修订 2 及候选实现已由用户审核接受；2026-10-17 在 `/Users/sc/.codex/worktrees/rnd504-implementation/md2word`、`md2word/RND-504` 上基于 `033cb61` 完成实现与复核，并获准按三笔计划收口。任务已归档 completed。下述“现有”描述保留规划调查时的依赖基线；实际证据和归档路径以 `validation.md` 为准。生产 backend 保持 disabled，不部署、不 push、不开始其他任务。

规划文件保存在原根目录，业务调查使用只读 Git 对象 `033cb61e3f6ac91f5d324790eb1a8ea920b783de`（含 CON-102/103）；不得把根目录 `4c40e6c` 当成已整合依赖。详细文件/符号证据见 `research/preview-baseline.md`。

现有 `_render_and_save_word` 在 `quality_checking` 完成 source/renderer integrity，再登记候选并以 first-valid receipt 选定唯一主件；`_finish_prepared_result` 物化同一 descriptor 后完成任务。`result_state.matches_current` 明确拒绝终态，不能为预览重试放宽这个执行 CAS。CON-103 的 `delivery_state_patch` 负责换代/换件失效、blocked 撤销批准及 published 保护。现有 `docx_quality.py` 只检查 OOXML，不应塞入外部排版进程。

本任务只增加 preview 端口、受控执行/文件证据及必要的任务状态桥接。页面映射、页级规则、统一 QualityRun、完整 review/publish/API/UI 分别留给其 backlog owner。

## 2. 模块与唯一 owner

| Owner | 责任 |
|---|---|
| `app/services/preview/models.py`、`provider.py`（新增） | 不可变输入策略、输出、局部错误、WordPreviewProvider Protocol；只接收 DOCX bytes 和策略，不依赖 DocumentIR、任务/文件仓储、AI。 |
| `app/services/preview/sandbox_adapter.py`、`executor_protocol.py`（新增） | 实现 word-preview-exec/v1 的生产进程 adapter、编解码/校验、deadline/终止/清理；缺执行器时 unavailable，但必须以正式子进程协议完成成功路径测试。测试 fake 不成为生产 backend。 |
| `app/domains/document_jobs/preview.py`、`preview_state.py`（新增） | 应用编排与纯状态规则：选定主件、claim/lease、重试、Artifact 绑定、质量摘要；与 provider I/O 解耦。 |
| `app/domains/document_jobs/quality_state.py`（新增最小纯规则） | 在既有任务锁内维护可归属质量贡献及总体状态；预览只替换自己的贡献，未归属旧结论和其他生产者不能丢失。不创建 QualityRun 或其他检测。 |
| `DocumentJobRepositoryProtocol` 与三 adapter | 在既有同 job 序列化点原子 claim/finish；不在锁内执行 provider、文件存储或网络 I/O。 |
| `FileUploadService` / document_files | 二进制登记、hash、归属、保留期；任务 service 负责哪些预览 ID 对用户可见。 |
| `Settings`、`build_runtime` | 非敏感策略快照、生产 backend 选择及依赖注入；不新增插件框架、服务或转换流水线。 |

这些边界用于真实的 I/O 测试替换和状态所有权；不为单次函数调用再建立 forwarding wrapper、工厂层或通用质量框架。

## 3. 数据流

1. 创建新任务时在 `request_snapshot.word_preview` 固化策略版本、backend/profile ID、profile hash、required、页面开关及资源上限；不保存命令路径、环境变量或密钥。普通 retry 使用原策略；clone 默认继承，显式使用当前配置时重新固化，沿用既有 clone 选择语义。
2. 正式 renderer 与现有确定性 integrity 检查保持原顺序。只有选定 receipt 后，`_finish_prepared_result` 物化该 DOCX，并让 preview service 读取同一 descriptor 的字节，校验 size/SHA-256。主件读取失败或字节与 descriptor 不符是主产物存储/完整性错误，继续原失败合同，不能包装成可成功下载的普通预览失败。
3. 锁内 claim 当前 receipt 的 preview attempt，锁外调用 provider；只有赢家可推进。PDF/页面/manifest 写入独立对象，再锁内按 claim token 和来源身份提交 manifest 引用与安全摘要。
4. 成功或预览失败已持久化后，执行按既有 CAS 完成为 succeeded；预览失败同时 quality blocked、internal_draft，DOCX 保留。已有 OOXML/integrity/主件存储失败继续原错误合同。
5. Worker 重投先检查选定 receipt、已提交 preview 和租约，复用有效结果或在过期后接管；不另选主件。`retry_word_preview` 内部应用入口支持已完成且未发布任务的失败/不可用预览重试，不重新执行转换。
6. 现有任务文件列表和下载授权只接受当前已提交 manifest 的 PDF/page/manifest ID。后续 QA-602 从同一应用服务读取，不另建证据真源。

## 4. 合同与持久化

### Provider 合同

`WordPreviewProvider.render(docx: bytes, *, policy: PreviewPolicy) -> PreviewResult`。

- `PreviewResult`：PDF bytes、正整数 `page_count`、可选按 `page_index=0..n-1` 排序的 PNG 列表、provider ID/version 和 renderer profile hash；无服务器绝对路径、object key 或文档正文摘要。
- `PreviewPolicy`：协议版本、总 deadline、单次 timeout、最大尝试数、DOCX/PDF/页面总字节、页数、单页像素、临时空间、CPU/内存预算和可选页面开关。
- `PreviewFailure`：稳定局部 code、retryable、经过白名单处理的 message；原始 stderr、路径、文档内容不进入公共响应/事件。
- port 输出不含 block ID、source spans、bbox 或 Word 页映射；这些是 RND-505/506 的 owner。

### 任务私有状态

新增可选 `DocumentJobRecord.word_preview_state`，缺省 `None`，以已有 JSON payload 持久化，不新增 SQL 列或独立运行表。它保存当前主件身份、当前 run 指针及有界历史去重账本，类型由 `preview_state.py` 定义：

```text
schema_version
source_generation / source_result_file_id / source_docx_sha256
profile_id / profile_sha256
revision / current_request_key / max_runs_per_result
runs_by_request_key[initial | canonical_request_uuid]:
  run_id / request_fingerprint / requested_by / reason_sha256
  status: pending | running | succeeded | failed | unavailable
  attempt_count / max_attempts / next_retry_at / run_deadline_at
  lease_token / lease_expires_at
  manifest_file_id / error_code / started_at / completed_at
```

安全投影写入 `quality_summary.checks_v1.word_preview`：质量贡献状态、来源身份、run/manifest、provider/version/profile hash、页数、文件 ID 和局部错误码；不使用无人消费的 needs_quality_reaggregation 标志代替恢复。lease/token、request 去重账本、reason 摘要、绝对路径、stderr 和内部配置不能进入 API、事件或日志。现有 presenter 继续白名单输出，incident 等旁路同样检查。

私有账本是 run/幂等状态的唯一 owner；current_request_key 只选账本项，不另存一份可修改状态；manifest 是不可变结果证据，不能代替首次 claim 的去重登记。换 generation/真正换主件时清当前身份的状态和质量贡献，历史 Artifact 保留，旧代请求先按来源身份拒绝，不进入新账本。旧 payload 无字段可读，不隐式生成预览或提升旧 QA 批准。

### Artifact

新增 file_type：`word_preview_pdf`、`word_preview_page`、`word_preview_manifest`。manifest schema 为 `word-preview/v1`，记录来源身份、run/attempt、profile、状态、局部失败码、PDF/page file ID + hash + MIME + size、页数、provider/version、UTC 时间。request key/fingerprint 和 actor/reason 只在私有账本，通过 run ID 关联；可下载 manifest 不携带这些字段，不通过改写下载字节来伪装脱敏。

- 复用现有 document_files 存储和 FileUploadService；对象名由服务生成，并包含 generation/result ID/run ID/attempt ID/page index，禁止复用原始文件名或可重复的 `preview.pdf` 对象键。现有 `_generated_object_key_for` 同类型同 filename 会重用路径，必须在调用 owner 消除覆盖风险。
- 每次尝试追加新文件，不更新已写二进制或旧 manifest。所有输出登记完成且校验通过后才能提交成功引用；中途失败的已登记文件仅作诊断，不能进入当前成功列表。
- 首轮实现复核补充：preview 文件必须先 insert 带 `word_preview_artifact_protocol=1` 的 pending metadata，再写独立对象并在既有文件锁内确认 uploaded。初次 insert 失败不写对象，写入/确认失败保留可追踪 pending；沿用既有过期/清理入口，不能复活过期/删除文件或放宽 generated_word 物化。PDF/page/manifest 任一登记不可确认均传播原存储失败，不以失败 manifest 掩盖后完成执行。
- 保留期采用现有按 file_type 策略，且不长于主件有效期；登记时同时固化有效期。复用现有过期/删除流程，不能复活 expired/deleted 文件。没有跨 Artifact Store/metadata 的原子事务：失败后保留已登记部分输出并交既有清理，不能为了“回滚”删除主件/历史证据。
- 继承 CON-102 的明确限制：retention 标 deleted 后才完成的迟到对象写入，仍被禁止确认 uploaded/进入当前 manifest；但二进制可能存在且后续 retention 跳过 deleted 墓碑。保留记录和 key 不等于承诺全部迟到二进制已物理回收，不扩展本任务为新清理协议。
- 不把正文、PDF/DOCX/PNG 二进制存入 DB。file_type 当前公共 schema 为 string，需更新合同文档及相关筛选，不强行制造 API enum 变更。

## 5. 幂等、并发与生命周期

新增窄仓储操作 `claim_document_job_preview` / `finish_document_job_preview`，由三 adapter 调用共享纯规则；不能复用无条件 update 实现检查后写入。

claim/finish 都在既有 file job.lock、SQLite BEGIN IMMEDIATE、MySQL SELECT FOR UPDATE 下重读并检查：

- tenant/company/job、generation、当前 receipt/result ID、源 DOCX hash、profile hash；
- 首次预览允许 `running/uploading` 且 receipt 已选定；独立重试只允许 `succeeded/completed` 且当前主件与 receipt 一致；不支持扫描旧件补猜；
- deleted/archived/canceled/failed/published 拒绝；运行期还检查原总任务 timeout；
- 当前 revision/lease token/lease expiry 和 max_attempts。有效租约重复调用返回 busy/已有结果；旧 token 不能提交；过期接管也不能重置已消费尝试数。

finish 还必须匹配当前 request key/run，不能仅检查历史账本内旧 run 的 token。首次 running/uploading 预览受原任务 deadline 约束，已取消/总超时后不能完成；已完成任务的内部重试则在首次 claim 固化独立 run_deadline_at，不使用已经过去的 job.timeout_at，也不修改原 timeout/status/stage。接管不能延长 run deadline，迟到输出不能提交。

首次 run 的幂等作用域为 tenant/company/job + generation + result ID/hash + profile hash，使用服务保留的 initial key。独立重试由应用 service 先 `get_job(..., user=...)` 校验 owner/Admin，再接纳 reason 和规范化 UUID request ID；fingerprint 包括上述身份、动作、actor 和 reason hash。先查历史 key/冲突，再决定新 key 是否复用成功结果或建立 run；同 key 同 fingerprint 返回历史 run，不改变当前较新 run 的选择，不增加 attempt 或调用 provider；同 key 不同 fingerprint 返回既有 conflict，不覆盖旧记录。

首次消费 key、创建 run 和 claim attempt 必须在同一个 job 锁/事务原子完成，先于 provider、事件或 manifest 写入；请求 A 失败→B 失败→重启→A 重放仍读到 A 的历史结果。旧 A 即使有残余自动重试资格，也不能绕过已选 B 再 claim。账本覆盖当前结果整个有效期，不按时间或 LRU 淘汰已消费 key；每个来源身份的 max_runs_per_result 固化在快照，建议初值 16（含 initial），达到上限用既有 conflict 拒绝新 key，已有 key 仍可查询/幂等重放。冲突/限额拒绝不创建新质量失败或改动当前证据。主件失效后先拒绝来源，再按既有生命周期保留历史，不把过期 key 重新视为新请求。

已成功的同 profile 直接复用，不提供强制刷新已发布/成功预览的旁门。没有 receipt 的 legacy 主件继续原有下载/完成合同，预览单独重试明确 conflict，不扫描猜测或伪造 receipt；若快照要求预览但身份凭据不足，记录 unavailable+blocked，不能声称检查通过。

成功复用也消费新 request key：锁内记录 fingerprint/actor/reason 到原成功 run 的关联，同 run_id 与 attempt 不变、current 不移动；重启后同 key 同参返回该关联，异参 conflict。max_runs_per_result 在实现中限制已消费 key（含复用关联），不淘汰旧 key；统计实际执行按 run_id 识别，不能将关联行计作新执行。

外部 I/O 在锁外。输出写完到提交前进程中断允许留下不可见候选；租约到期后新 attempt 不覆盖其字节，旧 attempt 返回也不能选中。已提交状态但事件追加失败不回滚当前选择，不因日志异常重新生成主件；记录诊断，复用原状态恢复。保留既有事件与状态分步提交的限制，不引入 outbox。

任务执行 CAS `matches_current` 的终态拒绝保持；新 preview CAS 仅能修改本检查状态、安全摘要、必要的质量阻断/复核失效，不能改 status/stage/generation/result/receipt。最终执行完成仍由原 CAS 负责。

## 6. 质量、错误和权限

| 场景 | preview 结果 | 任务影响 |
|---|---|---|
| disabled 且 required=false | unavailable / preview_disabled，无成功证据 | 预览贡献 pending，总体按下述规则保留未检查/其他阻断，不产生通过 |
| required=true 但 backend/profile/sandbox 不可用 | unavailable + blocker | quality blocked；主件可内部下载 |
| 暂态超时/暂时性执行器故障 | 有界重试，耗尽 failed | 最终 blocked，保留主件；不改为 render_failed |
| 空/损坏输入、非法输出、资源超限 | failed，不盲重试 | blocked，保留错误 manifest；主件生成已有失败不在此降级 |
| 预览成功 | succeeded + committed manifest，预览贡献 passed | 按已知基础贡献合成总体状态；单凭预览不能把 pending 置 passed，不批准/发布 |
| 成功重试此前失败 | 仅替换本预览贡献，保留历史失败 | 基础 pending/warning/passed 分别恢复；其他、未知或并发新增 blocker 继续 blocked；旧批准不恢复 |
| metadata/主件存储不可确认 | 不宣称成功 | 保持原存储错误/恢复语义，不完成或晋升 |

局部错误码固定为 `preview_disabled`、`preview_provider_unavailable`、`preview_profile_unavailable`、`preview_sandbox_unavailable`、`preview_input_invalid`、`preview_timeout`、`preview_resource_exceeded`、`preview_output_invalid`、`preview_engine_failed`、`preview_storage_failed`、`preview_unexpected_error`。配置/输入/安全/输出错误不重试；timeout 和明确暂态由 bounded policy 决定，不能仅按异常文本猜测。`busy`/stale 是并发控制结果，不作为质量成功或转换错误。

### 可归属阻断与恢复

本任务必须闭合自身 blocker 的增改和解除，不能等待 RND-506/QA-602。采用 `quality_summary.checks_v1` 的小型贡献表，各 producer 只更新自己的结果，不实现新检查或 QualityRun。首次引入时，将当前已存的 quality_status 原样保存为保守的 `__unattributed__` 基础贡献，保留其他摘要；不从旧 QA 或 flag 文本推断通过。已有非法/未知 checks_v1 结构显式冲突，不覆盖。

`quality_state.py` 通过三 adapter 共用的 `result_state.patched_job → delivery_state_patch` 路径接入：在原记录上先执行既有 published 不可变检查，再处理换代/换件重置或质量贡献合成，最后用合成后的 quality_status 执行 blocked 的复核/交付失效并验证模型。不能先按旧质量检查批准，再在其后写入 blocked；原 delivery_state 继续拥有这套顺序，不在多个模块复制 published/批准规则。首次绑定主件保留本代质量。

producer-aware 更新只替换授权贡献；既有调用者显式写 quality_status 而不声明 producer 时更新 `__unattributed__`，即使新旧枚举值同为 blocked 也登记，防止并发新增阻断被预览成功误清。普通进度、事件或 receipt 补丁没有显式质量输入时不重复捕获当前 blocked；通用 summary 更新不能删除/修改 producer 结果。producer 上下文只由内部窄 CAS 传入，不接受 HTTP 字段或直接保存为 payload。换代/换件清当前贡献，历史证据不删。

所有贡献和总体质量在同一 job 锁内提交，规则为 blocked 优先，其次 pending，再 warning，全部已知为 passed 才能 passed。预览失败/required-unavailable 将自己的贡献置 blocked；开始新重试不提前清旧 blocker；成功只把本贡献置 passed。基础 pending→失败→成功恢复 pending，基础 warning 恢复 warning，基础 passed 恢复 passed；原有/未知 blocked 或并发写入其他 blocked 保持 blocked。旧批准、ready/published 不随恢复自动复活，历史失败 manifest 不删除。全部 OOXML flags 升级 fatal 仍被禁止。

复用当前 `get_job` 的 tenant/company/owner/Admin 检查。应用下载授权入口必须核对当前 manifest、来源 hash/generation、file 归属、uploaded/expiry，禁止同 retry_count fallback；本地 HMAC Token 在实际应用下载时再次检查，默认下载仍为主 DOCX。

保持既有 S3 合同：签发 presigned URL 前检查当前引用，S3 直连读取只受签名/对象/TTL 控制，不再经过任务服务。替换 manifest 后不能再签发旧文件 URL，但已签 URL 不承诺立即失效；新预览 URL 的 TTL 不超过现有签发上限、文件和主件剩余有效期。测试分别证明应用拒绝和有限 TTL，不以本地 Token 测试冒充 S3 撤销证明；本任务不新增下载代理或更换存储策略。

没有新匿名路径，也不增加当前尚不存在的 publish 功能；禁止批准依赖既有 quality blocked 校验，未来发布必须同时校验本预览与当前结果的绑定。当前没有发布 API，不能把负例写成“真实发布 E2E 已通过”。

## 7. 生产 adapter 与资源控制

不选择外部 SaaS，不把本机开发脚本直接接入线上。本任务在 `sandbox_adapter.py` / `executor_protocol.py` 交付完整生产调用代码及 word-preview-exec/v1 schema/符合性测试：创建输入、启动/终止子进程、解析/校验结果、错误映射、清理和 Artifact 交接。运维维护实现该协议的实际引擎/解码器 launcher 与隔离部署，并提供批准的 profile；这是明确的部署依赖，不把协议设计或 adapter 代码留给未来未定义任务。缺部署能力可关闭 backend，但仅有 readiness 拒绝、Protocol 类或内存 fake 不算 adapter 交付。

### word-preview-exec/v1 执行协议

- 调用固定为 `[absolute_launcher, "render", "--protocol", "word-preview-exec/v1", "--request", absolute_request_json, "--result", absolute_result_json]`，`shell=False`，cwd 为本 attempt 私有目录。所有路径/argv 来自服务和批准配置，不能由用户或原始文件名拼接；环境为白名单，禁止继承密钥。
- 目录固定为 `source.docx`（只读副本）、`request.json`、`result.json`、`out/preview.pdf` 和可选 `out/page-000000.png` 起的连续零基页文件。launcher 不回写 DOCX，不读取目录外内容。result 的路径必须符合这些名称并通过常规文件/非 symlink/目录边界检查。
- request JSON 为 UTF-8，必需字段：`protocol_version="word-preview-exec/v1"`、`input={path:"source.docx",sha256,size_bytes}`、`profile_id/profile_sha256`、`render_pages`、`budget_ms`、`limits={max_output_bytes,max_pages,max_page_pixels,max_temp_bytes,max_cpu_seconds,max_memory_bytes,max_processes}`。sha256 使用既有 `sha256:<64hex>` 格式；不传任务仓储、IR、凭据或客户文件名。
- result 必需 `protocol_version/status`、`input_sha256`、`profile_id/profile_sha256`、`provider_id/provider_version`。`status="ok"` 还需正 `page_count`、`pdf={path,mime_type,size_bytes,sha256}` 及 `pages=[{page_index,path,mime_type,size_bytes,sha256,width,height}]`；关闭页面时 pages 必须为空。`status="error"` 只接收白名单 `error_code`，不接收可执行数据或任意错误正文。adapter 重算大小/hash、核对输入/profile 与页序，不信任结果自报即通过。
- 退出 0 只对应完整且校验通过的 ok；20→preview_input_invalid，21→preview_resource_exceeded，22→白名单 preview_provider_unavailable/preview_profile_unavailable/preview_sandbox_unavailable，23→preview_output_invalid，24→永久 preview_engine_failed，25→暂态 preview_engine_failed。只有 25 和允许重试的 timeout 消耗后续预算。缺失/矛盾/未知退出或 JSON 明确失败，不能从文件存在或 stderr 猜成功；未知退出映射 preview_unexpected_error。
- 预检 argv 为 `[absolute_launcher, "describe", "--protocol", "word-preview-exec/v1", "--result", absolute_capabilities_json]`；返回相同版本/profile、engine/validator 版本和 PDF/PNG 能力。配置 pin profile 内容 hash 与 launcher 指纹，实际不符或能力不足则不可用；describe 自报不等于沙箱证明。
- adapter 负责总/单次 deadline、新进程组、超时先 TERM 后在有限 grace 内 KILL、等待退出和本 attempt 目录清理；launcher 的部署 owner 负责终止其隔离域中的所有引擎/子任务，不能留下脱离进程组的后台服务。未能确认终止或清理时显式失败并诊断，不交付成功输出或删除主件。

符合性门必须运行一个 tests-only 受控子进程执行上述正式协议，经过真实生产 adapter 的启动/文件/JSON/输出校验路径，覆盖有效 PDF、可选 PNG、错误退出、timeout、profile/hash 错配、坏 schema/路径和清理。该子进程是测试替身，不是生产 backend。报告分别记录 adapter_contract_ready 和 production_ready：前者可由此闭环证明，后者还需要实际获准引擎、字体、隔离及解码证据；不能把 unavailable 或假 PDF 当成真实排版验收。

生产启用条件：隔离执行器已由运维批准，能证明无网络/外部资源更新、宏和活动内容不执行、仅挂载单次输入输出目录、非特权用户、CPU/内存/磁盘/进程数/页数上限及整个子进程组超时终止。`subprocess timeout`、临时目录或执行器自报 capability 都不等于已证明沙箱；证据不足时 backend 不 ready，不降级为本机裸跑。

输入先做有界 OOXML ZIP/CRC/必要部件验证，限制条目数、解压总量和压缩比，拒绝活动宏/嵌入执行内容，不执行外部链接；正常超链接不作为联网许可。输出路径只能是私有工作目录的常规文件，拒绝绝对路径/穿越/symlink/目录，先限大小再读取。PDF 的完整解码和页数校验必须由批准的隔离校验工具执行；没有该能力返回 unavailable，不能只看 `%PDF` 魔数判成功。PNG 需签名、解码尺寸、页序和像素预算匹配。页面关闭时不调用光栅化工具。

Settings 计划新增 `word_preview_backend=disabled|sandboxed`、`word_preview_required`、`word_preview_profile_id`、launcher/profile 配置路径、资源限制和 max_runs_per_result；fake 不进入配置枚举。backend 默认 disabled、required 默认 false；生产 profile 需明确资源上限和固定 launcher 身份。快照只保存非敏感 profile 标识/hash/策略及预算，不保存部署绝对路径或私有指纹。

初始保护上限建议复用现有 50 MiB 上传和 200 页边界，单次 60 秒、每 run 最多 2 次、PDF+页面合计 100 MiB、单页 20M 像素、临时空间 512 MiB；CPU/内存上限由批准的 sandbox profile 明确声明，缺失则不 ready。这些是可配置安全预算提案，不是已校准容量/SLA；实现以 synthetic 边界样本验证，生产以实际 Datasheet/字体样本校准后发布新 profile。总尝试及退避必须在当前任务剩余 deadline 内，不能与 1200 秒任务总预算竞争到主件无法登记。

## 8. API、DB、前端与兼容

- 不新增 preview/publish HTTP 路由或 available action；QA-602/CON-104 保持各自范围。现有 detail 的 `quality_summary` 和 files/download 通道提供最小可观察边界。
- 私有状态不公开，响应字段仍为已有 JSON 摘要/string file_type；预期 OpenAPI schema 无破坏性差异，必须运行 snapshot check。若实现改变公开字段/枚举，先同步合同/快照再评审，不能临时扩张后续 API。
- 三 adapter 仅新增 payload 字段与窄 CAS 方法，复用 CON-103 质量列投影，不新增 DDL、表或 backfill；已有显式 CON-103 迁移是实现环境前置条件，不在此重做。
- 不做前端页面、路由/query key/URL 状态变更，不生成第二套业务状态机；现有客户端手写类型以 string/JSON 接收新增预览类型与摘要，实施时确认实际消费者，不无差别重生成。
- 滚动部署前暂停相关写者，统一部署能保留私有字段的新代码后再启用；旧 Pydantic writer 可能丢弃新字段，不能因“只加 JSON 字段”声称任意混部兼容。

## 9. 安全、可观测性、迁移与回滚

仅按现有 storage backend 读写，不向 SaaS/AI/新 URL 发送内容；沙箱只收到当前 DOCX，不挂载源 PDF、完整资源库或凭据。临时目录每 attempt 独占，成功/失败/取消都清理；Artifact 按内部隐私和现有保留策略处理，专有文件/截图不入 Git。

业务事件/审计记录 preview_started/succeeded/failed/retry_requested 的非敏感摘要：job、generation、result ID/hash、provider/profile、页数、attempt、duration、error code；内部租约只用于控制，不进入公开摘要。优先复用既有 business logger、document_job events、audit_service；不增加 REL-702 的整套 metrics/告警工程。记录无法原子提交的事件缺口。

回滚点：尚未接线时仅撤回新模块；接线后停用 backend/新请求并保留兼容代码、私有状态、manifest、历史审计与全部主件。不能通过 disabled 清空 blocked/批准旧件。已有策略快照不重写；紧急停用使在途预览 unavailable/blocked，不偷偷换 profile。禁止回退到会丢字段的旧写者，禁止 DROP、清历史或覆盖发布件。真实 MySQL/InnoDB/部署 FS 锁门仍是生产写者启用条件，fake SQL/本机文件锁不能替代。

## 10. 验证边界与规划结论

实现用 fake/provider executor、正式最小 DOCX、三 adapter、定向 API 权限/下载和 receipt 故障注入验证。生产 adapter 的真实引擎、字体和沙箱能力需要部署环境证据；Microsoft Word 最终视觉人工验收另列。不能由本轮静态调查推出通过。详细 AC 到测试映射和命令见 `implement.md`。

方案没有要求选择 SaaS、破坏性迁移或改变冻结规则；交付必须包括可执行协议 adapter、自身阻断恢复和跨 run 去重，不把这些留给后续任务。生产部署启用另受证据门控制，当前根目录仍须先整合依赖。独立审查的原始反例及修正追踪见 `planning-review.md`。
