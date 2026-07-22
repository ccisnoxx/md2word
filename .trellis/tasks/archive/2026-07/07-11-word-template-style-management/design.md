# 技术设计

## 1. 最小可行架构

沿用现有 `templates` 领域、Resource Version 状态机和 document job 渲染链路，不新增平行管理服务。新增一个后端配置合同模块作为样式配置唯一 owner；前端只消费该模块导出的 API schema。

数据流：

```text
seed/历史版本 YAML
  -> 严格配置模型 + 编辑元数据
  -> admin GET（完整值、编辑 schema、预览样例）
  -> 前端仅提交 dirty editable changes
  -> base version + hash 校验并受控深合并
  -> staging DOCX/YAML + hash 复验
  -> 原子版本号 + Resource Version draft
  -> admin 验证任务
  -> publish
  -> set-default
  -> 后续 job 固化 template_version_id
  -> Worker 严格加载同版本 DOCX/YAML
```

## 2. 配置合同边界

新增 `app/domains/templates/layout_config_schema.py`：

- 定义 `template-config/v1` 完整严格模型，包含 meta、18 个运行时分组、隐藏 renderer 字段和只读 preview sample。
- 使用 `extra="forbid"`，缺失/未知 schema version 直接失败。
- 字段声明同时携带 label、type、unit、editable、min/max/step、options、help 和 order。
- 导出有序 categories/groups/fields API schema；前端不再维护分组标题和字段范围的第二份真相。
- 提供从完整配置生成 editable projection、应用变更 patch、输出规范化 YAML 的领域操作。

Renderer 的 `TemplateConfigPackage` 复用该模块的分组模型或接收其规范化结果。`language_overrides`、`word_style_name`、`header_bold` 等当前未开放字段仍在完整模型中保留，但不进入 editable patch。

## 3. API 合同

### 读取

`GET /api/v1/templates/{template_id}/layout-config?version={version}`

- 无 version：读取该 template 的 active published default；若尚未 bootstrap，则读取 manifest seed。
- 指定 version：admin 可读取 draft/published/disabled 版本用于审核和分支编辑。
- 返回 template/version/status/default、active version、config hash、只读 meta、完整规范化 config、preview samples 和有序 field schema。
- 不返回服务器绝对路径。

### 保存

`POST /api/v1/templates/{template_id}/layout-config/versions`

```json
{
  "base_template_version_id": "default@1",
  "expected_config_sha256": "sha256:...",
  "expected_active_template_version_id": "default@1",
  "changes": {"normal": {"font_size": 11}},
  "change_note": "调整正文字号"
}
```

- 仅允许 editable 叶子字段；空 patch、未知/只读字段返回 422。
- active version 或 base hash 变化返回 409，不自动合并。
- 从 exact base 完整配置合并 patch，重新执行完整模型和跨字段校验。
- 成功返回新 draft 及 base/hash 元数据。

既有 publish、set-default、disable API 保留。回滚通过对历史 published version 执行 set-default，不新增同义 API。

## 4. 权限与版本解析

- layout config GET/POST、版本列表、publish、set-default、disable 均为 admin 管理边界。
- 普通模板列表仍可用于 job 创建，但只暴露 published/default 信息。
- 将版本解析拆成明确意图：生产 job resolver 只接受 published；admin verification resolver 可接受 draft；Worker 只消费 job 已固化且状态合法的版本。
- 禁止普通用户通过 create/clone/retry payload 注入 draft、disabled 或 superseded version。

## 5. 版本与文件一致性

- 新增 `resource_version_sequences`，由 MySQL 事务原子分配整数版本，允许空洞但不复用。
- staging 目录与目标版本目录必须在同一文件系统；复制 DOCX、写 YAML、fsync、重新读取校验并计算 hash 后执行原子 rename。
- Resource Version draft 创建使用 create-only 语义，禁止现有 `ON DUPLICATE KEY UPDATE` 覆盖同版本。
- DB 写入失败时仅清理本次新建目录；清理失败记录健康告警和结构化日志。
- 审计失败但 draft 已持久化时返回明确 503，刷新可发现该 draft，不声称保存成功。

## 6. 默认版本唯一来源与迁移

- MySQL 模式下 `resource_default_versions` 是版本默认指针唯一来源。
- manifest 仅注册 template id、seed DOCX/YAML 和初始元数据，不再随 set-default 被改写。
- `template_state.json` 只保存默认 template id，并使用临时文件 + 原子替换。
- 启动时幂等 bootstrap 当前 manifest 版本：若资源记录不存在则按真实文件/hash 登记 published；仅在 DB 没有 default 时设为 default。
- API、config summary 和 job resolver 都从同一 DB default owner 派生状态。

## 7. 前端状态与预览

- 页面状态包含 selected template/version、active version、baseline values/hash、draft values、dirty paths、field errors 和 request sequence。
- 保存成功后使用响应的新 draft 重新加载为 baseline，不回跳旧 published 配置。
- 近似预览读取响应中的只读 preview samples，根据当前表单渲染 A4 边距、文本、表格和页眉页脚；不新增 P0 预览后端任务。
- 未知控件类型或 schema/config 不一致时阻止编辑和保存。
- 409/422/403/503 保留表单输入；字段错误按 path 聚焦。

## 8. 故障与错误

- 422：结构化 `[{path, code, message}]` 字段错误。
- 409：stale active/hash 或版本状态冲突，返回当前 active version/hash。
- 404：模板、版本、配置或验证任务不存在。
- 503：Resource Version 服务、共享文件持久化或原子写入不可用。
- 已声明配置缺失、损坏或 hash mismatch 必须 fail closed；只有明确没有 layout config 绑定的模板才可使用 renderer 默认值。

## 9. Rollout 与回滚

- 后端与前端 API 合同协调发布，不保留旧 full-config 保存兼容层。
- 上线前备份 Resource Version/default 记录和运行时模板目录，执行 bootstrap dry check。
- canary 只调整一个低风险字段，完成 draft、真实验证、publish、set-default、新任务检查。
- 业务回滚优先切回已验证的历史 published 版本，再决定是否回滚应用。
