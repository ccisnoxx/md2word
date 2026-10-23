# RND-504 独立实现复核

## 首轮 fresh 只读复核

2026-10-17，使用 fresh `critical_reviewer`，隔离上下文，检查独立工作区的真实 diff、新增代码及测试。复核前后主会话对 1188 个 tracked/non-ignored 文件作字节核对，变化为 0；复核者没有持久化文件写入。工作区与基线见 `validation.md`。

首轮确认 3 项问题，阻断该候选的人工验收；不能把首轮“复核交付已接受”理解为业务候选通过。主会话已接受发现并授权在 RND-504 内修正，随后需要另一 fresh 复核。

| ID / 严重性 | 修正前位置与触发 | 影响与安全方向 | 当前状态 |
|---|---|---|---|
| IR1 / P1 | `preview.py:137` 捕获 PDF/page metadata insert 失败后落失败 manifest，并返回 preview_finished=true；真实文件服务先写对象后 insert metadata。 | 可能留下无 metadata 对象且执行 succeeded，违反 metadata 不可确认不得完成。预览登记失败须传播原存储失败；先创建可追踪 pending 候选再写对象，确认前不选入 manifest，保持既有过期/删除边界。 | 已修正；定向测试及最终 fresh 复核确认闭合 |
| IR2 / P2 | `preview_state.py:123` 在已有成功 run 时复用新 key B，却不登记 fingerprint；B 异参也 reused。 | 违反同 ID 异参 conflict。锁内登记 key→成功 run 的不可变关联，保留 current、provider/attempt 预算并约束账本上限，重启后继续检查。 | 已修正；定向测试及最终 fresh 复核确认闭合 |
| IR3 / P2 | `models.py:109` 按原始字节/名称查宏；UTF-16 ContentType + `word/custom.bin` 的 vbaProject relationship 被接受。 | 宏输入拒绝合同被绕过；没有执行宏，也不表示突破批准 sandbox。复用解析 XML 检查内容类型/关系语义，补 UTF-16/重命名 part 的拒绝反例并保留正常超链接。 | 已修正；定向测试及最终 fresh 复核确认闭合 |

复核反例均用现有 venv、`PYTHONDONTWRITEBYTECODE=1` 和内存对象/真实纯规则执行，无外部调用、服务启动或文件修改。IR1 观察到 `preview_finished=True / run_status=failed / quality=blocked / unregistered_written_objects=1 / manifest_saved=True`；IR2 观察到首次和异参均 `reused`、saved_keys 仅 A；IR3 观察到 `validate_docx()` 接受上述 UTF-16 包。

首轮已核对 receipt 后完成、三 adapter CAS、质量合成顺序、当前 manifest 授权、本地 Token、S3 TTL、detail/incident、私有状态投影及新增测试。未确认旧执行终态拒绝被放宽、A 历史重放移动 current、预览成功清其他 blocker 或私有 ledger/lease/reason 泄漏。真实 MySQL/部署 FS、真实 S3、实际 engine/validator/font/sandbox、线上 Golden 和 Microsoft Word 视觉继续 pending，不要求本轮启用。

## 修正与复核出口

实现 worker 在原业务/测试所有权内完成三项修正、旧行为失败反例及直接影响测试；主会话同步 Spec/文档，保留原目录 dirty。修正及最终 fresh 复核完成后仅将 manifest 标 review，Trellis 保持 in_progress，不标 done，不部署、不提交、不 push。

## 修正后候选

三项均已修正：preview metadata-first pending 登记与失败传播；成功复用 key 原子关联/冲突/上限；解析 XML 语义拒绝 UTF-16 与重命名活动内容、DTD。实现改动 9 个业务/测试文件，由主会话实际 diff/所有权核对；不放宽主件 receipt 物化，不新增 SQL/schema 或 HTTP 路由。

最小回归在修正前按预期失败（3 selectors、22 个失败子场景），修正后通过。新三模块完整 40 项 / 16.335s 通过；artifact_retention/result_persistence 22 项及单个 retention API selector 通过。初次回归命令多写 s 导致一个 loader error，定位后仅重跑正确单项通过，未把错误命令称为通过。compileall/diff check 通过。

主会话针对共享文件登记/生命周期接线，在此稳定候选再次运行最终 release：202 项 / 5.684s 通过，OpenAPI 未变（164 paths/322 schemas），前端合同与 smoke mock 通过。component renderer 输入未变，复用 1/1 证据。

## 最终 fresh 只读复核

2026-10-17，另一 fresh `critical_reviewer` 对实际 9 个修正文件、关联调用、三份规划及现行 Spec 复核，确认 IR1/IR2/IR3 闭合，未确认新的发布阻断问题，可进入 review。主会话在复核结束、更新本记录前核对 1189 个 tracked/non-ignored 文件，变化为 0；复核者未写文件、启动服务或重复已成功整套门。

复核者独立执行仅内存的反例检查，使用现有 venv 与 `PYTHONDONTWRITEBYTECODE=1`：

- insert、对象写入、最终确认各自操作前失败及操作后响应丢失，共六类登记故障；异常均传播，已写对象保有 metadata。最终确认已提交但响应丢失时仍向调用方失败，不能误报任务完成。
- 严格整数 marker、三类 preview 到期、普通 source pending、generated_word 物化、preview 禁止进入 receipt 物化、内部候选代理上传在对象写入前拒绝。
- alias 的 actor/reason、JSON 重载、异参冲突、上限、唯一实际 run/attempt；UTF-8/UTF-16LE/UTF-16BE 下含字符引用的宏 relationship/DTD 均拒绝，普通超链接接受。

另构造 pending 到期并被 retention 标 deleted 后、对象迟到写入的交错：uploaded 确认正确拒绝，但二进制可能存在且后续 retention 跳过 deleted 墓碑。复核者核对 `033cb61` 的 database-guidelines 既有 CON-102 限制后撤回临时 P2 判断，该现象作为继承的残余边界保留，不能声称所有迟到二进制已物理回收。当前 manifest 不引用该候选、应用不签发下载，metadata 不复活。

此结论不是人工验收或生产启用。真实 MySQL/InnoDB、部署 FS、真实 S3、engine/validator/fonts/sandbox、线上 Golden 与 Microsoft Word 人工视觉仍未验证；adapter_contract_ready=true，production_ready=false，backend=disabled。

四阶段委派审计已生成并通过 finalize/verify，audit_id 为 `20261016T162019Z-rnd-504-implementation-a6c51176`；4/4 计划、4/4 子任务交付接受，独立复核 2 次，无残留活跃 worker 或审计异常。“子任务交付接受”统计包括首轮正确发现问题的复核报告，不能替代候选验收。
