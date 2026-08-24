# 生产基线与重置目标

核验时间：2026-08-24（Asia/Shanghai）

## 运行状态

- SSH alias：`hostdzire`
- 当前后端 release：`/root/md2word-releases/d8b8196`
- API、Worker 正常，ready 为 `status=ok`、`version=d8b8196`、无 blockers。
- 普通发布不修改 `dmit`。

## 当前 Template Version

| 版本 | 状态 | 默认 |
|---|---|---:|
| `default@1` | `published` | 否 |
| `default@2` | `published` | 是 |
| `default@3` | `draft` | 否 |
| `default@4` | `draft` | 否 |

- `resource_version_sequences(template, default).next_version = 5`。
- `jobs` 表为 0，没有历史或运行中任务引用任何旧模板版本。
- 用户明确把环境视为开发阶段，要求删除旧版本并以当前本地基础资产重新从 V1开始。

## 运行时版本资产

- `/app/var/config/templates/default/v3/datasheet_template.docx`
- `/app/var/config/templates/default/v3/layout_config.yaml`
- `/app/var/config/templates/default/v4/datasheet_template.docx`
- `/app/var/config/templates/default/v4/layout_config.yaml`

V1/V2 使用旧 release 中的 bundled 资源，不在共享版本目录生成文件。

## 旧模板审计事件

- `default@2 / template.set_default`：1 条
- `default@3 / template.layout_config_version_create`：1 条
- `default@4 / template.layout_config_version_create`：1 条

这些审计事件保留，不参与版本解析或默认指针。不得删除其他审计事件。

## 本地新基线

- 基础 DOCX：`resources/templates/default/datasheet_template.docx`
- 基础 DOCX SHA-256：`b21448dbc10e7c7d5028490ddc079d784eb12a0360b35be2345fa0218aa12cfb`
- 基础 YAML：`resources/template_configs/datasheet_template.yaml`
- 当前 YAML SHA-256：`dff3ac75d99f440cb80d84e6960f3341bb7bc902810d099aaabb253583b41e7f`
- YAML 页脚尚未启用且没有左右文字，实施后 hash 会变化。
- 本地 V2/V3 YAML 已删除；manifest、Settings、runtime helpers、脚本和部分测试仍指向旧 V2/V3 路径。

## 精确重置范围

需要删除：

- `resource_versions` 的 `template/default@1-4`
- `resource_default_versions` 的 `template/default`
- `resource_version_sequences` 的 `template/default`
- 共享运行时 `default/v3`、`default/v4` 目录

不得删除：

- 整个 jobs/audit/其他资源数据库
- MySQL、Redis 或共享 volume
- 其他模板、术语或翻译配置版本
- 旧 release 目录（短期保留用于部署回滚）

## 重置后预期

- 新 manifest 登记基础 DOCX/YAML 为 `default@1`。
- 新 release 启动 bootstrap 后只存在新的 V1 published/default。
- 版本序列初始为空，首次新 draft 分配 V2。
- 真实 direct 任务固化新 `default@1` 并验证页脚。
