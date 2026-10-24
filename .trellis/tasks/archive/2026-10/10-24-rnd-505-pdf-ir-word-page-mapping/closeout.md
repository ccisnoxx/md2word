# RND-505 人工验收与本地收口

2026-10-24。用户明确接受 RND-505 实现与本轮全新 critical_reviewer 独立复审结论，授权仅在隔离工作树完成 Trellis 收口并本地提交 G0 与 RND-505 相关改动；不 push、不合回原根、不扩大范围、不重复测试。该授权覆盖工作提交、当前任务归档及会话日志提交，不覆盖其他任务归档或生产启用。

## 提交范围与顺序

实际工作树 `/Users/sc/.codex/worktrees/rnd505-page-mapping/md2word`，分支 `codex/rnd505-v2-implementation`。父提交 `8fa11d9779ce05e9cba1cfb7afee34ecbd58a4cf` 已有 RND-504；G0 复用已验收 RND-501 `69906a5e1e4b676a3e775fa50a94cef0ebc799c9`，融合并保留现有 RND-502/503、TR/CON 能力。G0 和 RND-505 作为已组合验证的统一候选一次工作提交，不借收口重做集成或改业务。

1. `feat(renderer): 集成 G0 并实现 PDF/IR/Word 页映射（RND-505）`：已验收清单内 48 个维护文件、父任务既有 children 登记及本任务的规划/实施/复审证据。只按具体文件路径暂存。
2. `chore(task): archive 10-24-rnd-505-pdf-ir-word-page-mapping`：本任务 completed、manifest RND-505 done/implemented、准确归档路径与工作提交号。父任务和其他任务状态不变。
3. `chore: record journal`：developer 777 的本次会话记录，只引用工作提交，不将归档提交当作工作实现。

已有 manifest/父任务的历史登记从原根保护基线带入；与原根比较，仅 RND-505 条目在本次收口改变，不重新接受或关闭其他任务。原根中与隔离 HEAD 不同的已验收状态不回退。`.venv`、`mineru_result` 链接及 tests/tmp 输出不提交；本任务历史日志、源码指纹、反例和审查记录保留。批准的 v2 三件套字节保持。

归档后只迁移 implement/check context 的自身研究路径，并使任务内 B1 快照辅助脚本在归档位置仍能定位仓库；不改业务或重跑 B1。原辅助脚本保存在 pre-closeout-evidence，旧验证日志仍是历史事实。收口元数据不改写此前“当时未授权/未提交”的审计记录。

## 已接受的验证证据

最终实际实现复审见 `post-implementation-review.md`，全新只读 reviewer 核实修复后未发现剩余可行动实质缺陷。两轮实施复审发现的可选证明递归边界、归并代表/disposition 认证问题均已修复和独立复验。

- 最终新增修复定向 56 项通过；B1 三入口 30 子场景通过，独立进程 file/SQLite 停写兼容通过，305 个 app 指纹匹配。
- 最终 release 203 项通过，OpenAPI current / changed=false；component 1/1、direct 5/5、P0=0。
- 此前集中 339 项：**5 次 failure、0 error**，不能称为全部通过。已逐项核对基线触发和失败签名，详 g0-failure-comparison.json、final-targeted.log、implementation-validation.md。

本轮只核对 Git 范围、已接受源码指纹、context 引用及收口文件，没有重复运行测试、release、component/direct、服务或外部调用。

## 五项基线失败

| Selector / 子场景 | 已核实原因与边界 |
|---|---|
| DocumentJobExecutionStageTests.test_automatic_word_discovery_requires_current_generation_and_final_ir | 旧 fixture 主件含图片布局 marker 却无所需报告，原完整性认证仍拒绝；失败签名与 G0/原基线相同。 |
| DocumentJobExecutionStageTests.test_explicit_result_reuses_old_generation_but_checks_file_identity，invalid=None | 同类旧 fixture 报告缺失；未放宽主件认证。 |
| DocumentJobDeliveryStateApiTests.test_operator_approval_updates_owner_and_safe_audit_while_remaining_draft，backend=file | 旧断言期待 quality_summary={}，实际已有 RND-502 formula 摘要。 |
| 同上，backend=database | 同一摘要断言差异，作为独立失败子场景保留。 |
| DocumentJobDeliveryStateApiTests.test_qa_keeps_owner_tenant_company_admin_and_direct_boundaries | 同一已有 formula 摘要断言差异。 |

未为使其通过修改断言、权限、审计、内容校验或发布规则。G0 原零翻译单元用例的已接受 fixture 修正及空输入独立拒绝证据保留，不与上述五次失败混淆。

## 未验环境门与运行边界

- 真实 Word/WPS 人工视觉、Golden、实际预览引擎/字体/生产沙箱未验。
- 真实 MySQL/InnoDB、部署文件系统锁/FS-S3 和生产大文档容量未验；fake/SQLite/本地目录不代签。
- direct `phase3_entry_ready=false`，原 P1/P2 待办不因本任务收口而完成。
- 保持 preview disabled / production_ready=false；人工接受实现和残余边界不等于发布、部署或生产启用。

映射仍是可降级导航，不承诺像素级分页。坏可选导航不改主件或业务状态；原权限、内容、hash、公式图片报告和存储错误仍失败关闭。已产生新 marker 的产物不能直接退回 B0；须停写并保留 B1 兼容 reader、原证明 metadata 和历史 Artifact，不删除审计、不覆盖发布文件。

## 工作区保护与完成条件

本轮前原根 `/Users/sc/PycharmProjects/md2word` 的 1118 个受保护路径、Git status 和暂存条目已快照，见 closeout-protection.json。原根分支 `codex/preserve-rnd503-dirty-20261023`、HEAD `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9` 必须保持；不 stash、不删除或覆盖用户改动。

收口完成以工作提交、准确归档、manifest done、会话记录、本地 Git 范围和最终原根保护核对为准。不启动或归档父任务、RND-504 或下一任务，不 push、不合回、不删除工作树。完整提交号由归档阶段与会话日志记录。

## 收口静态核对说明

全量暂存diff的空白检查发现5行原始unittest verbose日志尾空格，均为历史输出，未为通过格式检查改写证据（g0-candidate-ir-dependencies.log、g0-candidate-t0-renderer-execution.log两行、g0-candidate-tr-con.log、g0-final-tr-con.log）。排除仅这些原始.log后的维护源码/文档检查通过；这不属于新增测试失败。业务源码与已接受指纹不变。本轮未重复运行测试。

## 实际工作提交与归档落点

工作提交：`850c0090c3dcb7c6c23aa3498066fe745fa8036d`，父提交`8fa11d9779ce05e9cba1cfb7afee34ecbd58a4cf`，已核对141个明确路径。归档路径：`.trellis/tasks/archive/2026-10/10-24-rnd-505-pdf-ir-word-page-mapping`。归档操作将当前task设为completed，manifest仅RND-505设done/implemented，其余44条与原根保护基线保持；业务/Spec源码没有后续修改。随后会话记录引用此工作提交，最终bookkeeping提交号见Git日志。
