# RND-503 旧图片报告 IR 绑定兼容

## 目标

恢复 RND-503 旧图片报告对原始 IR 的认证。范围限现行 IR 模型补入四个默认字段造成的绑定失配及定向回归。

## 已确认事实

规划基线为 `main@c75a44eed59ef0421ae961c01e821c288229ac34`。旧样本的原始 JSON 未声明 `metadata.degraded_pages=[]`、`metadata.logical_table_groups_version=null`、`metadata.logical_table_groups=[]`、`metadata.logical_table_group_counts={}`。模型序列化补入这四项，当前历史投影保留它们，重算哈希与旧报告的 `source_ir_sha256` 失配。原件文件哈希与归档一致。图片报告认证入口为 `image_evidence.py:218`，v1 plan／trace 绑定也使用历史 IR 投影（`render_plan.py:38`、`render_evidence_validation.py:139`）。

## 验收标准

- [ ] **AC1 旧报告认证。** 使用归档清单中的 `actual-B1` 单图和 `large-indent-table` 正常分组两套原始 DOCX、IR 和报告。核对原件文件哈希后，走现行历史图片报告读回，确认完整认证通过、单图与分组结果正确、三件套字节一致。
- [ ] **AC2 篡改仍拒绝。** IR 实质变更、报告源 IR 绑定失配和 DOCX 实物篡改均被拒绝。显式声明的四个字段仍参与绑定，包括显式的默认值。已匹配现行历史投影的报告和当前内容合同沿用既有认证。
- [ ] **AC3 v1 渲染证据。** `render-plan/v1` 与 `block-render-evidence/v1` 的既有匹配组合仍通过；IR 身份或 trace 与同次计划的绑定失配仍被拒绝。

## 范围外

完整历史恢复仍缺原始登记和成功预览样本，B1 回退仍待验证，生产回退演练另行验收。本轮只规划，保留 `en2zh-runtime-evidence.md` 原样及其他 worktree、历史 PR 的现状，实施、应用测试与部署均留待另行授权。
