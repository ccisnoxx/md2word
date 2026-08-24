# 技术设计

## 1. 设计结论

把当前基础 DOCX/YAML 直接定义为新的 bundled `default@1`，删除旧 V2/V3 文件和线上所有旧模板版本状态。现有 Template Version 仍是唯一版本体系；区别只是明确执行一次开发阶段基线重置，不走增量 V5 发布。

```text
当前本地基础 DOCX/YAML
  -> 启用新页脚
  -> manifest / Settings / runtime owner 统一为 default@1 + 基础 YAML
  -> 本地门禁、提交、推送
  -> hostdzire 构建新 release
  -> 停止 API/Worker
  -> 删除旧 default@1-4 + 默认指针 + 版本序列 + v3/v4 运行时目录
  -> 启动新 release
  -> bootstrap 新 default@1 published/default
  -> 真实 default@1 任务 + OOXML/WPS 验收
```

## 2. 本地 bundled seed 重定义

### 2.1 唯一资产

- DOCX：`resources/templates/default/datasheet_template.docx`
- YAML：`resources/template_configs/datasheet_template.yaml`
- manifest：`version: 1`，同时指向上述两个基础路径。
- 删除 `datasheet_template_v2.yaml`、`datasheet_template_v3.yaml`；不新增 V5 文件。

基础 YAML 保留用户当前修改值，仅补齐页脚：

```yaml
footer:
  enabled: true
  left_text: v1.0
  right_text: info@ichelps.com
  show_page_number: true
```

页脚最终为左侧版本号、中部原生 `PAGE` 字段、右侧邮箱。

### 2.2 路径 owner 收敛

以下代表“当前内置配置”的 owner 必须改回基础 YAML：

- `app/core/config.py::Settings.layout_config_path`
- `app/conversion/runtime_helpers.py` 的候选默认路径
- `scripts/dev/run_local_mineru_quality_matrix.py`
- `scripts/dev/local_mineru_debug*_config.json`
- `docs/dev/local-conversion-sandbox.md`
- `resources/template_configs/md2docx.yaml` 的兼容说明
- 直接加载当前 seed 的 schema/renderer/API 测试

不得增加 V2 fallback。测试内显式构造“第二版本”以验证版本治理的场景不属于路径 owner，可继续使用 `default@2`。

### 2.3 Spec 与 hash 合同

- 旧 V1/V2 固定 hash 和 V3 候选合同全部退役。
- 新 `default@1` 的基础 YAML 与 DOCX hash 成为当前唯一 bundled seed 回归。
- Spec 明确这是用户授权的开发阶段重置，不是生产中原地修改 published seed 的通用先例。
- 未来再改当前新 V1 后，仍须恢复正常不可变合同并创建 V2；本任务不削弱后续版本规则。

## 3. 线上重置事务

### 3.1 已验证前提

- `jobs` 表为 0，没有历史或运行中任务引用旧版本。
- 当前资源状态为：V1/V2 published、V3/V4 draft、默认 V2、`next_version=5`。
- 运行时版本资产只存在 V3/V4 的四个文件。
- 旧模板相关审计事件只有三条：V2 set-default、V3/V4 layout draft create。

### 3.2 并发边界

重置不能在 API/Worker 运行时执行，否则 bootstrap、任务创建或 Worker 解析可能观察到中间状态。流程为：

1. 新 release 镜像和前端静态 release 先准备完毕。
2. 再次确认 `jobs=0`、目标记录与文件集合未变化。
3. 停止 API、Worker，不停止 MySQL/Redis，不删除 volume。
4. 执行数据库事务与精确目录删除。
5. 启动新 release 的 API、Worker，由 bootstrap 初始化新 V1。

### 3.3 数据库事务

同一 MySQL 事务内：

1. 锁定 `template/default` 的全部 resource versions、默认指针和序列行。
2. 断言版本集合严格为 `{1,2,3,4}`，默认为 2，序列为 5，`jobs=0`。
3. 删除 `resource_versions` 的四行，断言影响行数为 4。
4. 删除 `resource_default_versions` 的一行，断言影响行数为 1。
5. 删除 `resource_version_sequences` 的一行，断言影响行数为 1。
6. 提交；任一断言不符则回滚并恢复旧 API/Worker。

不删除 `audit_events`。旧审计记录继续描述已经发生过的开发操作，但不再是当前版本状态来源。

事务提交后删除精确目录：

- `/app/var/config/templates/default/v3`
- `/app/var/config/templates/default/v4`

## 4. 新 V1 初始化

新 release 启动时，`bootstrap_manifest_versions()` 观察到空的 `template/default` 资源状态：

1. 从 manifest 读取新的基础 DOCX/YAML。
2. 创建 `default@1` published 记录及严格 DOCX/YAML hash。
3. 因默认指针为空，把新 V1 设为默认。
4. bootstrap 不创建版本序列；首次新 draft 时 `_next_template_version()` 以 manifest/DB 最大版本 1 为基线，原子分配 V2。

这是 bundled seed 的现有初始化合同，不新增绕过逻辑。由于用户明确将环境视为开发阶段，本次允许 seed 在真实任务前先初始化为默认；上线后立即完成真实验证。

## 5. 验证设计

### 5.1 本地

- YAML strict schema 与字段集合。
- manifest 只登记新 `default@1`。
- 新 YAML/DOCX 固定 hash。
- 不存在任何运行时 owner 仍指向 v2/v3 文件。
- renderer 的 table minimum、页脚左右文字、原生 PAGE 字段和字体槽位回归。
- bootstrap 空库测试证明只创建并默认新 V1；下一 draft 分配为 V2。
- 既有前端生命周期 unit/build/targeted smoke。
- release check、`git diff --check`。

### 5.2 线上

- 重置后数据库只存在新的 `default@1`，默认 V1，旧 V2-V4 不存在。
- 新 V1 payload 的 DOCX/YAML hash 与目标 commit 一致。
- 使用 `OPA228_P1.pdf` 创建 direct 任务，不显式选历史版本，让默认解析固化为 `default@1`。
- 任务必须 succeeded；下载 DOCX 验证 OOXML 中左右文字、原生 PAGE field 和 positional tab。
- 使用 WPS/Word 实际确认左/中/右视觉位置与正文无重叠。
- 页面样式页显示 V1“当前默认”，模板总览只显示 V1。
- 内外网健康、runtime release gate、Golden Sample preflight 和公网静态资源通过。

## 6. 前端交付

此前已完成的 `TemplateVersionLifecycleActions` 和两个页面接入继续作为本次 release 的独立前端提交：

- 页面样式页直接显示当前 Template Version 状态与验证/发布/设默认操作。
- 模板文档页复用同一组件并保留版本总览。
- 新初始化完成后，两处都只显示新的 V1 为“当前默认”。

## 7. 回滚

- 停服务前失败：生产状态不变，不执行重置。
- 数据库事务失败：事务回滚，重新启动旧 API/Worker。
- 数据库已重置但新 release 启动失败：停止新服务，删除可能部分创建的新 V1状态，切回旧 release；旧 release 的 V2 manifest 会从其自身旧资产重新 bootstrap V2，恢复服务可用性。之后需重新规划再次重置。
- 新 V1 已初始化但在线验证失败：保持服务可观测，优先修复候选并重新部署；若必须紧急回滚，先删除新 V1状态，再切旧 release bootstrap V2，避免旧 release 用不同字节解析新 V1 payload。
- 前端失败：恢复旧 symlink，后端新 V1 可继续运行。
- 不执行 `down -v`，不删除数据库、共享 volume、旧 release 或其他资源。

## 8. 明确不做

- 不创建 V5 文件或 V5 resource version。
- 不恢复旧 V1/V2 仓库资产。
- 不新增版本删除 API、兼容 fallback 或第二版本体系。
- 不删除其他资源、审计数据或整库。
- 不修改 `dmit`。
