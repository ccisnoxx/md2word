# Word 模板样式配置合同

## Scenario：Admin 可视化编辑并版本化发布 Word 样式

### 1. Scope / Trigger

- 触发：修改 `template-config/v1`、样式编辑 API、Template Version 默认指针、DOCX/YAML 绑定或验证任务权限。
- 唯一结构 owner：`app/domains/templates/layout_config_schema.py`；renderer 和管理 API 必须复用其中模型，不得各自维护字段集合。

### 2. Signatures

- `GET /api/v1/templates/{template_id}/layout-config?version={int}`：admin-only 读取默认或指定版本。
- `POST /api/v1/templates/{template_id}/layout-config/versions`：admin-only 创建不可变 draft。
- `ResourceVersionRepositoryProtocol.create_resource_version(record)`：只插入，不覆盖。
- `ResourceVersionRepositoryProtocol.allocate_next_version(type, id, minimum_next)`：MySQL 事务内分配不复用整数。
- DB：`resource_version_sequences(resource_type, resource_id, next_version, updated_at)`，联合主键为 `(resource_type, resource_id)`。

### 3. Contracts

保存请求必须包含：

```json
{
  "base_template_version_id": "default@1",
  "expected_config_sha256": "sha256:...",
  "expected_active_template_version_id": "default@1",
  "changes": {"normal": {"font_size": 11}},
  "change_note": "调整正文字号"
}
```

- `changes` 只能出现编辑 schema 中 `readonly=false` 的叶子字段，服务从 exact base 合并后做完整模型校验。
- `schema_version`、`template_name`、`output_filename`、`sample_content`、隐藏 renderer 字段和页面宽高不允许修改。
- 保存只创建 draft；只有真实验证任务成功后才能 publish，只有 published 才能 set-default。
- MySQL 模式下 `resource_default_versions` 是版本默认指针唯一来源；manifest 只登记 seed，`template_state.json` 只登记默认 template id。
- Job 创建时固化 Template Version；普通用户只能选 published，admin 可显式创建 draft 验证任务，Worker 只消费已固化版本。

### 4. Validation & Error Matrix

| 条件 | 状态 | 合同 |
|---|---:|---|
| 非 admin 读取、列版本或保存 | 403 | 前后端同时隐藏/拒绝 |
| 模板或版本不存在 | 404 | 不 fallback 到其他 YAML |
| active version 或 base hash 变化 | 409 | 返回当前 active version 与 config hash |
| 未知、只读、类型、范围、边距或 Word 表格样式错误 | 422 | `field_errors[].path/code/message` |
| MySQL 版本服务或原子文件写入不可用 | 503 | 不声明保存成功 |
| 版本 YAML 缺失、损坏或 hash 不匹配 | 失败关闭 | 禁止 renderer/Job 静默换用 seed |

### 5. Good / Base / Bad Cases

- Good：从 `default@1` 只提交 `normal.font_size`，生成 `default@2` draft，seed YAML 与默认指针不变。
- Base：历史 published 版本通过 set-default 回滚，只移动 DB 指针，不改历史内容。
- Bad：提交完整 YAML、`sample_content`、页面宽度、未知字段或不存在的 Word table style。
- Bad：普通用户通过 create/clone/retry 注入 draft version。

### 6. Tests Required

- Schema 单测：真实 seed 完整校验、renderer 复用、只读/未知/NaN/范围/跨字段拒绝。
- API 集成：403、指定 draft 读取、dirty patch、409 CAS、结构化 422、seed 不变。
- 持久化：create-only 冲突、整数序列单调、DB 失败清理 staging/目标目录。
- Job：operator 拒绝 draft，admin 验证任务快照状态为 draft，Worker 使用同版本 DOCX/YAML。
- Renderer：真实配置渲染后的段落、表格、页眉页脚属性断言。

### 7. Wrong vs Correct

#### Wrong

```python
# 用页面提交的完整 dict 覆盖 YAML，并在缺字段时回退 seed。
write_yaml(request.config)
```

#### Correct

```python
validated = apply_layout_changes(exact_base, request.changes)
stage_and_validate_docx_yaml(validated)
resource_version_service.create_draft(...)
```

