# 深化 Word 模板样式配置管理

## Goal

把现有 admin Word 页面样式配置雏形完善为安全、可验证、可发布、可回滚的内部治理工具。管理员无需编辑原始 YAML，即可按 `datasheet_template.yaml` 的一级分组调整样式；配置保存为 draft，经真实 Word 验证、发布并设为默认后，仅影响后续新建任务。

## Background

- 现有 `WordPageStyleListPage`、`WordPageStyleDetailPage`、layout-config API、Resource Version 和 Word renderer 已覆盖基础链路，本任务不重复建设平行页面或 API。
- 真实 seed YAML 当前无法完成 GET -> POST round-trip：`page_setup.page_width_cm/page_height_cm` 不在编辑白名单，而白名单要求 seed 中不存在的 `table_style.header_fill`。现有目标测试实际返回 `400` 而非 `201`。
- 当前 resolver 未限制普通用户使用 draft version，版本号分配依赖目录 `max+1`，配置缺失时 renderer 可能静默使用默认值，均属于 P0 风险。

## Requirements

### R1. 产品与权限边界

- 页面和 API 仅 admin 可用；operator 不得看到侧栏、配置中心卡片或管理入口，直达路由和管理 API 必须被拒绝。
- 普通 document job 只能使用 published 版本；只有 admin 的显式验证流程可以使用 draft。
- 继续支持所有绑定 `template-config/v1` layout config 的模板，不硬编码 `default`。
- 不提供原始 YAML 编辑、任意 YAML 上传、DOCX/Logo 编辑或浏览器直接修改仓库资源。

### R2. 配置合同

- 后端拥有唯一白名单 schema，统一负责严格模型、中文分组/字段标签、顺序、控件类型、单位、枚举、编辑性和范围。
- seed YAML、GET 响应、保存校验、持久化 YAML 和 renderer 必须使用同一合同，未知字段不得被静默忽略。
- 18 个 YAML 一级分组都必须可达并显示约定中文名称。
- `schema_version`、`template_name`、`output_filename` 只读；`sample_content` 只供预览；`header.logo_path` 不可编辑。
- P0 锁定 A4，`page_width_cm/page_height_cm` 只读并在保存时无损保留。

### R3. 编辑与预览

- 表单按 schema 选择 text、number、boolean、color、alignment 或 enum 控件。
- 支持 dirty 计数、变更摘要、字段错误、首错定位、刷新/切换/离开确认和撤销本次修改。
- 保存按钮明确命名为“保存为草稿版本”，保存成功后以新 draft 为编辑基线，并提供创建验证任务和查看版本入口。
- P0 提供浏览器近似效果示意，覆盖 A4 边距、文本、表格、页眉页脚；必须明确最终以真实 Word 验证任务为准。
- “撤销本次修改”只恢复当前加载基线；生产回滚通过历史 published 版本重新设为默认完成。

### R4. 版本、持久化与生效

- 保存每次创建不可变 draft，不覆盖历史版本、seed YAML 或当前生产默认。
- draft 必须引用明确的 base version 和 config hash；客户端只提交 editable 叶子字段变更，服务端从 base 深合并只读/隐藏字段。
- 版本号由 MySQL 原子序列分配；并发请求不得写入同一版本目录或覆盖数据库记录。
- DOCX/YAML 在 staging 目录写入、校验并原子发布；失败不得产生可消费的半版本。
- MySQL 模式下，Resource Version 默认指针是版本唯一权威来源；manifest 只负责注册和 seed bootstrap，`template_state.json` 只负责默认 template id。
- 当前 manifest 版本缺少资源记录时，应幂等登记为 published/default，且不得覆盖已有数据库默认指针。
- 发布必须引用同版本且 succeeded 的验证任务；设默认后只有后续新任务使用新版本，既有任务保持原 `template_version_id`。

### R5. 故障关闭、审计与运维

- 已声明的版本化配置缺失、损坏、schema 不支持或 hash 不匹配时必须明确失败，不得静默回退样式。
- 所有管理动作记录 actor、凭据来源、trace ID、base/new version、hash 和原因；不得记录完整配置或敏感绝对路径。
- P0 继续保留 legacy `X-Admin-Token` 运维兼容，浏览器仅使用 admin JWT。
- 生产版本治理保持 MySQL-only；file/sqlite 不提供伪成功或静默降级。

## Validation Rules

- 数字必须有限且不能是 boolean。
- `font_size` 为 `1..200 pt`；段前段后为 `0..500 pt`；行距为 `0.5..5`。
- 页边距和页眉页脚距离为 `0..10 cm`；Logo 高度为 `0.1..10 cm`；缩进为 `-500..500 pt`。
- 固定 A4 下剩余正文宽高必须为正。
- 颜色规范化为 `#RRGGBB`；alignment 使用字段自身枚举。
- 字体名限制 `1..128` 字符；页眉标题限制 `0..500` 字符。
- `table_style.style_name` 必须存在于 base DOCX，不能依赖 renderer 静默回退。

## Acceptance Criteria

- [ ] 真实 `datasheet_template.yaml` 无修改 round-trip 成功，现有目标测试由 `400 != 201` 转绿，且所有 renderer 有效字段无丢失。
- [ ] 18 个一级分组、中文标签、字段控件、单位和只读状态均由后端 schema 驱动。
- [ ] admin 可读写；operator 无入口、路由被拒、管理 API 被拒，并且不能通过 job API 使用 draft/disabled/superseded 版本。
- [ ] 保存只创建完整 draft；published 未设默认不生效；设默认后新任务使用新配置，旧任务不变。
- [ ] 并发保存不覆盖；stale active/hash 返回 409；文件、数据库和 hash 一一对应。
- [ ] 配置缺失、损坏、schema 不支持或 hash 不符时明确失败，不静默 fallback。
- [ ] 近似预览随表单更新并显示非权威提示；真实验证任务仍是发布门禁。
- [ ] 历史 published 版本可重新设为默认，且不修改历史 YAML/DOCX。
- [ ] `python-docx` 验证页边距、文本、表格和页眉页脚至少一组真实属性变化。
- [ ] 后端相关测试、前端 unit/build、核心 smoke 和 `scripts/ops/check_release.py` 通过。

## Out Of Scope

- 像素级 Word WYSIWYG、PDF 页面缩略图、多级审批和模板市场。
- P0 的 file/sqlite Resource Version 写入支持。
- P0 编辑纸张宽高、任意资源路径、`sample_content` 或语言 override。
- 模板间批量复制、样式预设和任意 schema 插件。
