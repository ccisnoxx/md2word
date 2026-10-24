# RND-505 页映射与应用接入实施记录

本分工业务代码已停止编辑。全部改动仅位于批准隔离工作树；G0 未提交基线保留，不覆盖原根、不提交或推送。

## 实际文件和职责

- `app/services/preview/page_mapping.py`：独立严格模型、canonical/hash、有界构建/reader、固定源 rank/真实输出顺序/最近邻推断。固定上限 8 MiB 与 100000 条，超限返回小型 unavailable，不发布截断条目。
- `app/domains/document_jobs/preview.py`：只从已选 receipt 与原 IR/认证 trace/独立证明构造 binding，成功预览的原 manifest 增加可选 page_mapping；`current_page_mapping` 内部只读视图在原完整预览认证后独立消费内层 mapping。仅纯 mapper 的意外异常局部隔离。
- `app/domains/document_jobs/execution.py`：三恢复入口的共用原 aggregate 成功边界后局部认证可选证明，保留原 metadata 字节/值；普通事件明确剔除新完整私有键。原完整性、receipt、CAS、状态与错误边界不变。
- `tests/test_preview_page_mapping.py`：12 项，覆盖比例、稀疏 rank、S=1 退化、实际输出序异于 IR、nearest tie、P=1、无来源/无目标、coalesced、缺证据、错绑/版本/非有限/计数及预算、typed 多 span。
- `tests/test_document_job_word_preview.py`：新增 7 项，真实 renderer→receipt→manifest、成功 alias/replay 不重算、旧/坏/错绑 mapping 的局部读取、错误安全、权限/过期、缺原 IR 生命周期、坏 proof 不追认 namespace/旧首名。
- `tests/test_document_job_result_persistence.py`：新增 1 项（30 个 subcase），file/SQLite × legacy/explicit/receipt × valid/missing/unknown/bad hash/bad trace；保留原主件、证明、状态和事件/文件摘要隔离。

新增/实质触及 Python 注释、docstring、开发者错误消息均使用中文。未修改 Provider/executor/profile/API/DDL、质量/发布资格或生产开关。

## 可调用合同

- `MappingBinding`：source_pdf_file_id、document_ir_file_id、input_ir_sha256、plan_sha256、source_generation、result_file_id、docx_sha256、run_id、attempt、profile_sha256、preview_pdf_file_id/sha256、page_count。文件 hash 沿原 sha256: 格式，IR/plan hash 沿原裸 64 位。
- `build_page_mapping(*, binding, plan, block_evidence, block_anchor_evidence=None) -> dict`：plan/trace 由 renderer owner 认证，bookmark 只来自认证独立证明。
- `read_page_mapping(value, *, binding) -> dict`：schema/hash/完整 binding 独立认证；旧/坏/未知仅映射 unavailable。
- `unavailable_mapping(binding, reason, total=None)` 与 `mapping_summary(mapping)`：前者保留可证明基本身份，后者只允许版本/状态/受控原因/固定五计数。
- `current_page_mapping(job, file_repository, file_service)`：内部授权调用方的只读映射视图；无新 HTTP 路由，无写入或重新生成副作用。

entry 包含 block_id/anchor_ref/bookmark_name/anchor_reason_code/disposition/representative_block_id、source、location 和 fallback。location 的 page_range 永远 null；多页都是 low 估计。source provenance 与页置信度独立。counts 固定为 total/located/high/low/anchor_available。

## 失败与历史边界

- 完整有界 trace 但无正文 target：保留全部条目、source/owner/disposition，unavailable/no_target、location 不可用、fallback=null。
- 缺 trace 或不可用预览：小型 entries=[]，未知块数 total=null。
- 原 IR 已知缺失、过期、删除或跨 scope：不读取越权字节，仅映射 unavailable，不引入新的预览可用性门。原 IR 未知存储故障、描述符/字节损坏及原内容/公式/图片认证错误继续显式失败；原 IR JSON 错误使用安全固定消息。
- 历史持久 trace/proof 缺失、坏绑定或未知版本只降低映射/锚点可用性；原内容/hash/公式图片/23 键恢复门不被降级吞掉。主件 metadata 不回填、删除、重算或补 marker。
- 本分工没有改 claim/registration/finish CAS、幂等 key、alias、TTL 或权限；旧运行/迟到 attempt 沿原 RND-504 拒绝。

## 本轮检查

1. 四模块合并回归：`tests.test_preview_page_mapping tests.test_document_job_word_preview tests.test_document_job_preview_persistence tests.test_document_job_result_persistence`，103 项，96.398s，全部 OK；日志 `mapping-tests.log`。
2. 最终定向复验：`tests.test_preview_page_mapping tests.test_document_job_word_preview.DocumentJobPageMappingTests`，19 项，6.363s，全部 OK；日志 `mapping-final-targeted.log`。该次覆盖最后的安全 IR 错误消息/receipt binding/负来源页边界，未重复完整 103 项。
3. `git diff --check` 通过。所有权文件当前指纹见 `mapping-source-fingerprints.json`。
4. 初始单测夹具失败为测试 table() 参数误用、explicit 历史入口不创建 receipt 的断言误设，均诊断并修正测试；未为过测改变原业务语义。

## B0/B1 与交接

实际 G0 reader 源码已通过新增 selector `DocumentJobPageMappingTests.test_g0_old_manifest_reader_accepts_new_manifest_and_keeps_unknown_mapping_optional` 读取当前新 manifest。旧 manifest→新 reader、未知/坏 mapping 局部不可用已通过实际登记文件验证。

B1 兼容分工由主会话构建/冻结源码快照。停止 mapping writer 的精确文本范围：从 `if status == "succeeded":` 下紧接 `_mapping_source(file, docx, ...)` 的整段开始，到 `# manifest 或 CAS 持久化失败` 前结束；保留所有 reader/helper。renderer 的 B1 停新 marker 由其 owner 处理，不新增业务配置。

可重用三恢复 selector：`tests.test_document_job_result_persistence.DocumentJobBlockAnchorRecoveryTests.test_three_recovery_entries_preserve_optional_proof_and_never_rerender`。设置 `RND505_COMPAT_ROOT` 时会动态加载该源根的 execution.py 类。该测试的共享 app reader 依赖仍是当前进程模块，主会话须用 B1 全 app 指纹确认除两个停用 writer 外源码相同，或用子进程 PYTHONPATH 完成完整 B1 加载；尚未把 B1 全链验证标记通过。

release/component/direct、独立检查与最终验收由主会话统一执行。本分工没有安装依赖、启动服务或外部引擎。真实 Word/WPS/预览引擎分页与视觉、真实 InnoDB/部署存储仍不由离线 fake/SQLite 证据代签；所有多页页码仍仅估计。
