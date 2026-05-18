---
doc_type: audit
slug: 2026-05-18-onboard-refresh
scope: 重新运行 cs-onboard 思路，对当前仓库 CodeStable 骨架、现有 Markdown、源码流程和架构文档一致性做一次刷新审计
summary: 仓库已具备 CodeStable 骨架；本次刷新了 tools/reference，共享流程文档已补齐，旧架构文档已从单文件描述更新为当前多 runtime 模块现状
status: current
last_reviewed: 2026-05-18
tags: [audit, onboard, codestable, architecture]
depends_on: [architecture-index]
implements: []
---

# 2026-05-18 Onboard 刷新审计

## 1. 扫描结论

- `.codestable/` 已存在，判断路径为“迁移/刷新”，不是空仓库初始化。
- 标准目录均已存在：`requirements`、`architecture`、`roadmap`、`features`、`issues`、`compound`、`tools`、`reference`。
- `.codestable/attention.md` 已存在，且记录了当前推荐运行环境 `/Users/sc/miniconda3/envs/md2word/bin/python` 和 LLM `.env` 配置约定。
- 根外 Markdown 仅发现 `prompt/translation_en2zh.md`，判断为运行时 prompt 资产，保留原位，未迁移。
- 当前目录不是 git 仓库，无法用 git 状态区分历史变更。

## 2. 文档映射结果

| 现有文件 | 推测内容类型 | 处理结果 | 置信度 |
|---|---|---|---|
| `.codestable/architecture/ARCHITECTURE.md` | 架构总入口 | 已更新为当前多 runtime 模块架构 | 高 |
| `.codestable/architecture/module-mineru-to-docx-internal.md` | 模块边界 | 已更新为当前运行时模块边界 | 高 |
| `prompt/translation_en2zh.md` | LLM 翻译 system prompt | 保留原位，不纳入 CodeStable 文档迁移 | 高 |
| `.codestable/tools/*` | CodeStable 共享脚本 | 已按技能包覆盖刷新 | 高 |
| `.codestable/reference/*` | CodeStable 共享参考 | 已按技能包覆盖刷新 | 高 |

## 3. 已执行动作

- 从 `/Users/sc/.agents/skills/cs-onboard/tools/` 覆盖刷新 `.codestable/tools/`。
- 从 `/Users/sc/.agents/skills/cs-onboard/reference/` 覆盖刷新 `.codestable/reference/`。
- 重写 `.codestable/architecture/ARCHITECTURE.md`，同步当前实际源码结构和主流程。
- 重写 `.codestable/architecture/module-mineru-to-docx-internal.md`，从“单文件内部模块”改为“运行时模块边界”。
- 新增 `.codestable/architecture/conversion-flow.md`，单独梳理启动、输入、修补、翻译、配置、渲染、输出流程。
- 新增本审计记录。

## 4. 未迁移 / 未处理项

- `prompt/translation_en2zh.md` 保留原位，因为代码通过 `llm_client.SYSTEM_PROMPT_PATH` 直接读取它，迁移会改变运行时资源位置。
- 未移动、删除或重命名任何项目源码、模板、配置、测试文件。
- 未修复 `translation_request_output` 帮助文案和实际行为不一致的问题；本次只作为架构注意点记录。

## 5. 验收状态

- `.codestable/attention.md`：存在。
- `.codestable/tools/`：已从技能包刷新。
- `.codestable/reference/`：已从技能包刷新。
- `.codestable/architecture/ARCHITECTURE.md`：已更新。
- `.codestable/architecture/conversion-flow.md`：已新增。
- 迁移路径中每个发现的 Markdown 都有处理结果：`.codestable` 文档更新，运行时 prompt 保留原位。

## 6. 后续建议

- 若继续走 CodeStable 工作流，下一步适合用 `cs-issue` 记录并修复 `translation_request_output` 行为/文案不一致。
- 若要继续拆模块，建议先用 `cs-refactor` 设计如何逐步移除 `bind_runtime` 反查耦合。
