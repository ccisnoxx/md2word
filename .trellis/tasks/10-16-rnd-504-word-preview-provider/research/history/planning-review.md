# RND-504 独立规划审查与修订

审查发起于 2026-10-16，修订收口于 2026-10-17（Asia/Shanghai）。仍为 planning，只修改规划与任务记录，不激活任务或修改业务代码。

## 审查来源与候选

按用户明确请求，以 fresh `critical_reviewer`、`fork_turns=none` 独立只读审查三份初始规划，业务合同以 `git show 033cb61:<path>` 为准。审查者未继承主会话历史，没有修改文件或执行实现/业务测试。主会话在审查结束前冻结候选；审查前后 1368 个受 Git 跟踪或非忽略文件的路径/字节集合指纹一致，确认该仓库范围未观察到写入。

原始候选 SHA-256：

| 文件 | SHA-256 |
|---|---|
| prd.md | ba394c888eb622355e86b1a337fb7856371a6f8a70fce2fca373dd89b026170f |
| design.md | e797fb854c2f5b2c05bd0ffcb91a43605c7621921da09af195431d480bde37b3 |
| implement.md | 2f78d6a5f7906cd5a01f44f7efff6e23e73bf5aff4852a9bad380df215269579 |

以下旧行号均定位上述候选，不能当作修订后行号。独立审查完成和工作交付验收不表示用户已经批准最新规划。

## 确认发现与处理

### R1 / P2：成功重试不能解除自身 blocker

原位置：design.md:98、prd.md:28、implement.md:79。基础 pending/warning 的任务首次预览失败后变 blocked，重试成功仍永久 blocked，等待尚不存在的 needs_quality_reaggregation 消费者；现有普通 retry 只处理执行失败，无法补救这个 succeeded+blocked 主件。

依据：`033cb61:app/domains/document_jobs/service.py:540` 与 `delivery_state.py:65` 拒绝 blocked 批准；service.py:661 是失败任务 retry。目标质量设计以当前 blocker 决定 blocked。

处理：采纳。PRD P8/AC7、design 第 6 节和 implement 的状态任务/测试改为本任务闭合预览贡献的增加、替换、解除。引入最小 quality_state 纯规则和 checks_v1 贡献表，保留原始/未知基础贡献；所有写者通过既有 job 序列化点，预览只更新自身贡献。成功恢复可证明的 pending/warning/passed，其他 blocker 保留；review/delivery 不自动恢复。通用调用显式写入同值 blocked 也记录为未归属贡献，进度/receipt 非质量补丁不重复捕获预览 blocked。没有新增检查、QualityRun 或后续发布能力。

### R2 / P2：外部 launcher 交付合同未定义

原位置：design.md:111、implement.md:41/56。只有 launcher/profile 路径，缺 argv、输入输出布局/schema、退出码与 owner，可以让永久 unavailable 伪装成已完成 adapter。

依据：ADR-015 和原 RND-504 提示词要求可替换端口及生产 adapter 边界，允许真实引擎未批准时使用 port/fake，但仓库不存在可直接依赖的 launcher 实现。

处理：采纳。design 第 7 节固定 word-preview-exec/v1：render/describe argv、request/result/capability、固定文件路径、输入/profile/hash 校验、退出码、超时/进程组/隔离域清理责任。本任务交付实际 adapter、协议 codec 和符合性测试；运维维护实现固定协议的实际引擎/解码器 launcher 与已批准隔离部署。必须经生产 adapter 启动 tests-only 子进程完成有效结果路径；adapter_contract_ready 与 production_ready 分别验收。没有批准真实引擎时不安装、不裸跑、不选择 SaaS，不能声称生产启用已验证。

### R3 / P2：当前 request ID 无法提供跨 run 幂等

原位置：design.md:46/61/65/83。A 失败、B 失败、服务重启、A 延迟重放时，只保存当前 request ID 的状态无法识别历史 A，可能创建 C 并刷新预算。

依据：现有 receipt 在锁内持久化选定身份；preview 也必须由同 job 序列化点拥有历史请求消费事实，不能靠异步事件或事后 manifest 去重。

处理：采纳。word_preview_state 以有界 runs_by_request_key 为唯一 run 状态，明确作用域、UUID/fingerprint、冲突及 max_runs_per_result；首次 claim 原子登记，先查历史 key 再决定新 run。当前结果有效期不淘汰已消费 key，满额拒绝新 key，旧 key 仍幂等查询；旧代先按身份拒绝。补 A→B→重启→A、冲突、满额及 claim 后崩溃的三 adapter 测试计划。没有新增运行表。

### C1：S3 读取时复核的适用范围

原位置：design.md:105。审查者将其列为证据边界，未确认既有权限缺陷。基线 router.py:618 直接签发 S3 presigned URL，对象读取不经过应用服务；本地 HMAC Token 测试不能证明已签 S3 URL 即时撤销。

处理：澄清并采纳边界。应用签发入口始终检查当前引用，本地 Token 在读取时再次检查；S3 继续有限 TTL/签名语义，不能再签发旧 manifest，但已签直连 URL 不承诺即时失效。预览 TTL 上限取现有上限与主件/文件剩余有效期的较小值。没有新增代理、匿名路径或降低跨租户/owner/Admin 检查。

## receipt/CAS 与兼容核对

- 保留执行 matches_current 的终态拒绝；preview 采用窄 CAS，不改变 status/stage/generation/result/receipt。
- 初次预览在已选 receipt 后；旧 token/run、取消、删除、归档、published 或旧代返回不提交。
- 首次运行受原任务总 deadline 约束；已完成任务的独立重试使用持久化独立 run_deadline_at，不受过去的 job.timeout_at 误拒，也不重置原执行时间。
- legacy 无 receipt 不猜测身份，预览重试明确 conflict，原 DOCX 下载合同保留；required 身份不足时不可伪造成功。
- 主件存储/hash 错误继续原失败语义，不能降级为普通预览 blocked；首次主件绑定仍保留本代质量。
- 三 adapter 更新 payload/既有质量列；不引入 DDL/backfill。旧 writer 不任意混部，停用/回滚保留兼容代码与证据。

## 修订后反例对照（静态推演，非业务测试）

| 反例 | 修订合同要求 |
|---|---|
| 基础 pending / warning / passed，只有预览失败再成功 | 依次恢复 pending / warning / passed，不恢复旧批准 |
| 预览已 blocked 时其他 writer 新写 blocked（包括同值） | 未归属/其他贡献留存，预览成功后仍 blocked |
| 原本 unknown/blocked 或只有进度/receipt 更新 | 未知 blocker 保留；普通非质量补丁不把预览 blocker 变成永久未知 blocker |
| A→B→重启→A，或 claim 后 manifest 前崩溃 | 原子历史账本返回 A 旧结果，不增加 run/attempt/provider，不改当前 B |
| 生产 adapter 只有拒绝 readiness | 不满足交付；必须通过正式受控子进程成功协议测试 |
| 完成任务原 timeout 已过去，或旧 run 迟到 | 新 run 用自己的固定 deadline；旧 run/token 不提交，不改原执行状态 |
| manifest 被替换后旧下载链接 | 应用不再签发；本地读取拒绝旧引用；S3 已签链接只声明有限 TTL |

## 证据与限制

审计 Bundle `20261016T155059Z-rnd-504-1f39fea6` 已关闭且 audit-verify 通过，无异常；SUBAGENT_EXECUTION_DIGEST 为 1 次执行、1 次审查交付验收、1 次独立复核，写入观测为空。这里的验收仅指审查任务交付，不是产品/实现验收。

独立审查覆盖修订前候选；修订由主会话按源码及反例核实、自查并执行规划校验，没有第二次独立复审。没有运行实现级竞争测试、真实 MySQL/部署 FS、引擎、字体、沙箱、S3 或 Microsoft Word 验证；这些仍是实施证据门。最终 task.py validate 和格式/工作区结果见 planning-validation.md 的本次修订记录。
