# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

### Word 输出专项合同

- 正式 MinerU→DocumentIR→Word 的输入、分页、分栏、表格、图片、字段、公式、样式优先级和专项质量门禁只由 [Word 生成规则](./word-generation-rules.md) 定义；本文不复制具体输出行为。
- 修改该链路时，先按规则 ID 核对唯一 owner、冲突矩阵、自动测试和样本证据，再应用本文件的通用测试与评审纪律。

### 已发布模板 seed 不可变性

- manifest 已登记并进入生产的模板版本，其版本号、资源路径和文件字节不可原地修改；新增可选 schema 字段应依靠模型默认值兼容旧 YAML，需要新的非默认内容时创建新版本。
- 每个 published bundled seed 都必须有固定 SHA-256 回归；当前 `default@2` 的 `datasheet_template_v2.yaml` 固定为 `132d0bb76e71c807912031199e894dfc0e3d50bd7534180f8ceaba7a5fa20b4d`。发布门禁不得只锁定 v1 而遗漏当前默认版本。
- hash 不匹配必须继续失败关闭；不得更新生产数据库 hash、放松读取校验或增加备用路径来掩盖 seed 被改写。

---

## Testing Requirements

### DOCX 渲染验证

- 定向测试应同时断言稳定的结构证据和可见内容，不以单一高层库属性或“文件可打开”代替行为验证。
- 结构性输出变更必须按 [Word 生成规则](./word-generation-rules.md) 的规则 ID、冲突矩阵和样本分层执行专项回归；外部/人工结论要记录实际工具、版本、输入输出和当前代码版本。
- 无法运行真客户端或在线门禁时，说明替代检查和剩余风险，不把未观察到的结果写成已通过。

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
