# 实施计划

## 前置门禁

- 用户审核并明确批准本 PRD、设计和实施计划后，才运行 `task.py start`。
- 实施只编辑 `.trellis/spec/` 与本任务研究/上下文文件；发现产品缺陷时记录，不修改产品代码或测试。
- 规范结论以当前正式代码和测试为最终实现证据；历史会话和旧 runtime 只能补充来源与差异。

## 实施步骤

1. **建立规则证据清单**
   - 从正式入口开始追踪 `formal_mineru_conversion`、`MinerUToDocumentIRService`、`build_layout_plan`、`DocumentIRWordRenderer` 和 `docx_quality`。
   - 完整读取每个正式 owner 的相关函数、调用者和对应定向测试；记录文件、符号、测试方法和行为证据。
   - 复核当前 specs、`32edca58` parity 资料、两个 08-18 归档任务和相关 git diff，确认规则取代关系。

2. **盘点样本与验收证据**
   - 读取 Golden Sample、component PDF manifest、回归治理文档及可用验收记录。
   - 将 OPA228 committed fixtures 与 SC2167/CM4112/TPL51200/BL0942/RS2G04 外部证据分开标记。
   - 不把本地临时 DOCX、PNG、PDF 或历史哈希写成当前可运行门禁。

3. **起草正式规则目录**
   - 新建 `.trellis/spec/backend/word-generation-rules.md`。
   - 写入正式链路、术语、状态枚举、规则 ID 约定和权威边界。
   - 按 `PIPE/INPUT/IR/PAGE/FLOW/COL/TEXT/TABLE/IMAGE/FIELD/MATH/STYLE/QUALITY` 分类整理规则。

4. **逐条绑定实现与验证**
   - 每条规则填写输入信号、正式 owner、预期输出、冲突/例外、禁止模式、自动测试、真样本、状态和来源/取代关系。
   - “已实现”必须同时有当前代码证据；“已测试”必须有当前自动测试；缺任一证据则降为 `implemented-gap` 或 `planned`。
   - 只在有明确证据时写具体测试方法名，避免凭模块名推断覆盖。

5. **建立冲突和回归矩阵**
   - 汇总分页/长表、分页/内容组、分栏/图片、模板/源装饰、公式/正文等冲突优先级。
   - 建立规则→owner→自动测试→committed fixture/external evidence→人工工具矩阵。
   - 对缺少长期样本、WPS/Word 复核或整文档门禁的项显式标记缺口。

6. **整理历史差异附录**
   - 记录旧 runtime 的历史行为、当前正式链路状态、取代规则和待迁移证据。
   - 明确 legacy characterization tests 不能证明正式 DocumentIR renderer 行为。
   - 删除或避免任何把两条链路描述为共同规范对象的措辞。

7. **消除规范重复并接入索引**
   - 更新 `.trellis/spec/backend/index.md`，在修改 MinerU/DocumentIR/renderer/DOCX 规则前强制读取主规范。
   - 将 `quality-guidelines.md` 中重复的 Word 输出行为迁入主规范或替换为链接，保留通用验证职责。
   - `template-layout-configuration.md` 只在需要时增加主规范回链，继续独立拥有 API/schema/version 合同。

8. **执行文档一致性验证**
   - 检查规则 ID 唯一、必填字段齐全、矩阵只引用已定义 ID。
   - 检查仓库内文件路径、测试模块和明确符号存在；外部/历史证据均有标识。
   - 检查 Markdown 相对链接可解析、规范之间没有重复或矛盾的输出合同。
   - 运行 `git diff --check` 并完整通读 diff，确认没有产品代码、测试和无关文档改动。

9. **独立质量复核**
   - 运行 Trellis full-scope check，重点查找：把当前 bug 固化、旧 runtime 污染、虚假测试覆盖、遗漏冲突规则、两份权威规范和不可复现样本声明。
   - 发现问题只修正文档与矩阵；任何需要产品改动的发现进入后续任务建议。

## 验证命令

实施时先按实际规则 ID 和文档结构校对命令，不为一次性检查新增仓库脚本。

```bash
git diff --check

rg -n '^### [A-Z]+-[0-9]{3} ' .trellis/spec/backend/word-generation-rules.md
rg -n 'app/|tests\.|tests/' .trellis/spec/backend/word-generation-rules.md
rg -n 'runtime/|historical|superseded|implemented-gap|planned' \
  .trellis/spec/backend/word-generation-rules.md
```

使用一个只读 Python heredoc/临时命令验证：

- 规则 ID 无重复；
- 回归矩阵规则 ID 全部已定义；
- 主规范中的仓库相对 Markdown 链接存在；
- 每条规则包含统一字段。

不运行产品单元测试或 DOCX 转换，原因是本任务不修改产品行为。若 diff 出现 `app/`、`tests/`、`resources/` 或 `frontend/` 路径，质量检查应直接失败并回到范围确认。

## 交付文件

- `.trellis/spec/backend/word-generation-rules.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/quality-guidelines.md`
- 可选回链：`.trellis/spec/backend/template-layout-configuration.md`
- 任务内研究与上下文：`research/rule-source-audit.md`、`implement.jsonl`、`check.jsonl`

## 风险与回滚点

- 主规则文件：规则状态、冲突优先级或 owner 证据错误时独立修正该条目。
- backend index：链接或触发范围过宽时回退索引项，不影响产品。
- quality guidelines：迁移时不得丢失通用 DOCX 验证要求；diff 中逐条核对迁移去向。
- template contract：只允许回链，不重写既有字段/version 合同。

全部改动为 Markdown/JSONL，可按文件恢复；禁止使用破坏性 Git 命令。
