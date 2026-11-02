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

### API 快照与前端动作契约

- 后端接口或响应模型变化时，使用 `scripts/ops/export_openapi.py` 同步 `docs/api/openapi.json`；快照检查必须比较当前生成结果，不能以历史部署快照替代或豁免差异。
- `DocumentJobActionId`、前端动作类型与 `check_release.py` 的静态契约检查应同步维护。`publish` 和 `new_generation` 在兼容旧响应时保持可选，缺失动作不能被前端默认启用，也不能由前端推算后端权限。
- 门禁回归需同时覆盖有效契约通过、过时快照失败、动作枚举遗漏失败，以及新增动作可选性丢失失败。同步类型不意味着增加可见操作入口。

### characterization 测试替身隔离

- `tests/runtime_direct_loaders.py` 的依赖替身只在直接加载期间生效，结束后恢复原有模块表及已有项目父包属性；返回的测试模块可以保留自己的局部替身绑定。
- 保留“先运行文本 characterization，再运行真实布局完整性校验”的顺序回归。后续校验必须读取真实 `docx.Document`，不能用调整测试顺序、重导入依赖或放松完整性断言掩盖全局替身泄漏。

### characterization 数学与配置夹具

- 输入适配器按共享 `mineru_content` 的当前合同保留 LaTeX 数学源，核对周围正文、题注分组与编号表注守恒；原生公式生成由正式 renderer 验证。不能为满足旧 HTML 断言恢复有损拍平，真实 HTML sub/sup 输入应单独保留语义回归。
- 共享 `TerminologyReplacer` 的加载测试使用真实临时 YAML 文件，实际验证优先级、作用域和大小写规则；不能用测试自身的 Python 文件加局部 `safe_load` 替身代替真实加载。无效 YAML 的解析拒绝必须保留，不能转成空规则成功。

### 复核状态与成功渲染夹具

- 区分未渲染任务的初始默认值与成功任务的已有质量证据。同一代、同一结果的复核和重置测试应先确认公式摘要符合夹具预期，再断言 `quality_status`、`quality_summary` 保持不变以及交付状态符合合同；不能把成功任务重新断言为 `quality_summary={}`。
- 成功回调路径需要可验证的 DOCX 和正式渲染报告。优先复用测试 runtime 已配置的 renderer；确需替身时应实现当前 `render_to_result` 结果合同，不能只返回 `b'fake-docx'`，也不能绕过质量检查。具体报告合同见 [Word 生成规则](./word-generation-rules.md#rnd-502公式报告与结果绑定的可执行合同)。

### DOCX 渲染验证

- 定向测试应同时断言稳定的结构证据和可见内容，不以单一高层库属性或“文件可打开”代替行为验证。
- 结构性输出变更必须按 [Word 生成规则](./word-generation-rules.md) 的规则 ID、冲突矩阵和样本分层执行专项回归；外部/人工结论要记录实际工具、版本、输入输出和当前代码版本。
- 无法运行真客户端或在线门禁时，说明替代检查和剩余风险，不把未观察到的结果写成已通过。

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
