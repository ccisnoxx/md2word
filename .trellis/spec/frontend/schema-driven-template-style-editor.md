# Schema 驱动的模板样式编辑器合同

## Scenario：Admin Word 样式配置工作台

### 1. Scope / Trigger

- 触发：修改 Word 样式页、模板样式 API types、管理入口、预览、字段校验或 draft 验证跳转。
- 页面只消费后端 `field_schema`；不得在 Vue 中再维护 18 个分组或字段范围的第二真相。

### 2. Signatures

- `templatesApi.getLayoutConfig(templateId, version?)` 返回值、预览样例和有序 schema。
- `templatesApi.createLayoutConfigVersion(templateId, payload)` 只提交 dirty editable changes 与 CAS 字段。
- 路由 `/settings/word-page-styles/:templateId` 必须同时受 admin route guard、入口过滤和后端权限保护。

### 3. Contracts

- `field_schema.categories` 决定一级导航顺序，`group_meta` 提供中文名称/说明，`groups` 决定控件、范围、单位、选项和只读状态。
- 前端只维护控件类型映射：`boolean`、`number`、`alignment`、`color`、`text`。
- baseline 包含 exact version/hash/active id；保存成功后必须加载新 draft 作为 baseline，不能回跳旧 published 值。
- 浏览器预览读取当前表单与 `preview_samples`，必须显示“非 Word 权威结果”提示。
- draft 页面提供“创建验证任务”跳转，发布、设默认和历史版本仍复用模板版本页状态机。

### 4. Validation & Error Matrix

| 条件 | 页面行为 |
|---|---|
| 422 `field_errors` | 保留输入，按 path 标红并切到对应分组 |
| 409 | 保留输入，提示刷新/重新应用，不自动合并 |
| 403 | 路由拒绝且普通用户看不到配置入口 |
| 503 | 保留输入并显示后端不可用信息 |
| 未保存切模板、刷新、离页 | 显式确认丢弃 |
| 过期异步响应 | request sequence 丢弃，不覆盖新模板状态 |

### 5. Good / Base / Bad Cases

- Good：修改一级标题字号，只发送 `changes.heading1.font_size`，保存后显示 draft 状态和验证入口。
- Base：撤销恢复当前加载版本 baseline，不创建版本。
- Bad：前端硬编码字段范围、提交完整 config、编辑只读元信息或把浏览器预览当发布证据。

### 6. Tests Required

- Typecheck：API types 与页面 schema 消费无隐式字段。
- Unit：dirty patch、字段范围/颜色/选项校验和错误 path 映射。
- Playwright：admin 保存 draft、operator 路由拒绝、近似预览提示、验证任务入口。
- 响应式：`375/768/1024/1440px` 无横向溢出；至少检查键盘焦点与深色主题。

### 7. Wrong vs Correct

#### Wrong

```ts
const groups = [{ id: "heading1", label: "一级标题", fields: ["font_size"] }];
await api.save({ config: form });
```

#### Correct

```ts
const groups = response.field_schema.categories;
await api.createLayoutConfigVersion(templateId, {
  base_template_version_id: response.template_version_id,
  expected_config_sha256: response.config_sha256,
  expected_active_template_version_id: response.active_template_version_id,
  changes: buildDirtyChanges(response.field_schema.groups),
});
```
