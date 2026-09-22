<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

## PDF / DOCX 变更验证

按已证实的影响范围选择验证：

- 单一 owner 的局部修复，且不改变公共 API、schema、配置合同或跨模块数据流时，运行最小复现或一至三个定向测试及 `git diff --check`。
- 共享解析器、renderer、helper、完整性规则或多个已知调用路径变化，且不涉及下列结构性或发布合同，运行失败回归与受影响模块测试。
- 以下任一变化执行完整 closure：公共 API、DocumentIR/schema、模板配置或版本合同；section 分组/方向、column/分栏规划、pagination/分页与 break、table fallback、asset identity、内容阻断或完整性规则；Word/WPS 兼容性；发布、归档或里程碑候选。版式与完整性变化同时满足 [Word 生成规则](./.trellis/spec/backend/word-generation-rules.md) 的 `QUALITY-003` / `QUALITY-004`，并包含相应 Word/WPS 视觉或失败关闭证据。
- 先复用同一候选上已通过且仍相关的证据；只有相关代码、配置、环境或诊断发生变化时重跑门禁。正式 spec 只记录稳定通用合同和已确认规则。
