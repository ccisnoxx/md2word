# 重新初始化默认 Word 模板

## Goal

把当前本地 `resources/templates/default/datasheet_template.docx` 和 `resources/template_configs/datasheet_template.yaml` 直接作为一套全新的初始默认模板部署到 `hostdzire`；删除旧的本地 V2/V3 资产和线上 `default@1-4` 版本状态，不创建 V5，也不保留旧 V1/V2 的发布合同。

## 已确认现状与决定

- 用户明确要求按开发阶段“从头来”，不把修改稿另存为 V5，也不恢复旧 V1/V2 资产。
- 当前本地基础 DOCX SHA-256 为 `b21448dbc10e7c7d5028490ddc079d784eb12a0360b35be2345fa0218aa12cfb`。
- 当前本地基础 YAML SHA-256 为 `dff3ac75d99f440cb80d84e6960f3341bb7bc902810d099aaabb253583b41e7f`；实施时还需启用页脚并加入左右文字，因此最终 hash 会变化。
- 本地 `datasheet_template_v2.yaml`、`datasheet_template_v3.yaml` 已删除；manifest 和若干 runtime/dev/test 路径仍指向 V2，需要统一回到基础 YAML。
- 线上当前有 `default@1-2` published、`default@3-4` draft，默认指针为 V2，版本序列下一号为 5。
- 线上 `jobs` 表当前为 0，没有历史或运行中任务引用旧模板版本，可以重置版本号而不造成任务快照串号。
- 线上有 3 条旧模板审计事件；保留为历史日志，不参与当前版本解析和列表，不删除其他审计数据。

## Requirements

### R1. 本地只保留一套初始默认资产

- 当前基础 DOCX 保持在 `resources/templates/default/datasheet_template.docx`，不得复制为 V5 文件。
- 当前基础 YAML 保持在 `resources/template_configs/datasheet_template.yaml`，不得复制为 V5 文件。
- 删除 `datasheet_template_v2.yaml`、`datasheet_template_v3.yaml`，不得恢复旧字节。
- `templates_manifest.yaml` 改为登记 `default@1`，DOCX/YAML 分别指向上述基础路径。
- `Settings`、正式本地 runtime helper、开发脚本和直接消费“当前内置配置”的文档/测试统一指向基础 YAML；不得保留 V2 fallback 或双路径探测。
- 只修改真正代表当前 bundled seed 的引用；测试中用于构造任意版本治理场景的 `default@2` 不做机械替换。

### R2. 新初始配置的页脚

- 基础 YAML 必须启用页脚覆盖并设置：
  - 左侧：`v1.0`
  - 右侧：`info@ichelps.com`
- 保留当前 `show_page_number: true`，中部使用原生 `PAGE` 字段。
- 其他配置继续使用用户当前本地修改值。

### R3. 重置线上 Template Version 状态

- 在生产写操作前停止 API、Worker，确认 `jobs` 仍为 0，避免重置窗口内创建或执行任务。
- 物理删除 `resource_versions` 中 `template/default` 的 V1、V2、V3、V4。
- 删除 `resource_default_versions` 中 `template/default` 的默认指针。
- 删除 `resource_version_sequences` 中 `template/default` 的序列行，使新的初始 seed 从 V1 开始；本次明确允许重置编号。
- 删除运行时 `/app/var/config/templates/default/v3`、`v4` 目录；不得删除 MySQL、Redis 或整个共享 volume。
- 保留旧模板审计事件和旧 release 目录，分别作为历史日志与短期部署回滚点；它们不是当前可用 Template Version。

### R4. 新 V1 初始化与验证

- 新 release 的 manifest seed 由现有 `bootstrap_manifest_versions()` 初始化为 `default@1`、`published` 且默认。
- 不新增草稿、发布或删除 API，不创建第二套版本体系。
- bundled seed 首次初始化沿用现有 bootstrap 合同，不要求先有 succeeded 任务；启动后必须立即创建真实任务验证新默认 V1。
- 验证任务使用 direct 模式并固化 `template_version_id=default@1`。
- 生成 DOCX 必须通过 OOXML 检查，并在 WPS/Word 中确认页脚左侧 `v1.0`、中部页码、右侧邮箱及正文无重叠。

### R5. 部署边界

- 只部署到 `hostdzire`，不得修改 `dmit`。
- 使用现有 Git archive release、前端原子 symlink、健康门禁和旧 release rebuild 回滚流程。
- 当前工作区中此前按用户要求完成的页面样式/模板版本生命周期入口作为独立提交纳入同一次 release；不得混入其他未识别改动。
- 提交前展示精确 commit 计划并取得确认；不得自动 push。

## Acceptance Criteria

- [x] 仓库只保留基础 DOCX/YAML 作为当前 bundled seed；没有 V2、V3 或 V5 模板配置/文档资产。
- [x] manifest 为 `default@1`，所有当前内置配置 owner 指向 `datasheet_template.yaml`，不存在 V2 fallback。
- [x] 新基础 YAML schema 有效，页脚为左 `v1.0`、中原生页码、右 `info@ichelps.com`。
- [x] 旧的 V1-V4 resource version、旧默认指针、旧序列行和 V3/V4 运行时目录已删除。
- [x] 新 release 启动后只存在新的 `default@1`，状态为 `published` 且为默认；版本序列在首次新草稿前可不存在，下一次分配应为 V2。
- [x] 新默认 V1 的 DOCX/YAML hash 与目标 commit 中基础文件一致。
- [x] 真实验证任务为 `succeeded` 且固化 `default@1`；生成 DOCX 通过 OOXML 和 WPS/Word 页脚验收。
- [ ] 页面样式页显示 V1“当前默认”，模板版本总览只显示新的 V1；线上 API 数据已核对，浏览器因扩展浮层阻断而未完成登录后视觉复核。
- [x] API/Worker、内外网 live/ready/metrics、runtime release check、Golden Sample preflight 和前端公网入口通过。
- [x] 部署审计记录重置前后状态与实际删除范围，不包含凭据。

## Out of Scope

- 新增模板版本删除 API或前端删除按钮。
- 保留或迁移旧 V1/V2 的不可变发布合同。
- 创建 V5 文件或 V5 线上版本。
- 删除整个数据库、其他资源版本、其他审计事件、旧 release 或共享 volume。
- 修改 `dmit`。

## Confirmed Reset Semantics

- 本次是一次开发阶段基线重置：旧 V1-V4 版本状态和序列被删除，新本地基础资产重新成为 `default@1`。
