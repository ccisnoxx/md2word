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
- 质量门禁固定区分两级：可证明的源内容缺失、重复、资产错配或不可见 payload 必须进入 `blocking_quality_flags` 并失败关闭；栏归属、分页、字体安装、客户端字段更新或版式证据不足时必须保留内容并安全降级，以非阻断质量信号交由 Word/WPS 验收。
- IR→DOCX 阻断证据必须来自确定性包内关系：规范化可见文本、语义表格 cell、明确 TOC source/anchor/field/cache、drawing asset marker→relationship→media checksum，以及可解析 OMML 的可见数学文本；自然重复文字、仍可见的 LaTeX residue 和客户端排版不得仅凭启发式升级为阻断。
- 正式本地与线上渲染必须把同一最终 `TemplateConfigPackage` 和 `LayoutPlan` 同时交给 renderer/evidence，并在最终 DOCX 发布或上传前执行同一 `ensure_renderer_integrity()`；不得维护第二套调用方门禁。
- 新 converter 产物必须为每个主源块记录唯一语义裁决；旧 IR 不得伪造不存在的历史证据，但仍需执行其可证明的 IR→layout→DOCX 对账。

### 已发布模板 seed 不可变性

- manifest 已登记并进入生产的模板版本，其版本号、资源路径和文件字节不可原地修改；新增可选 schema 字段应依靠模型默认值兼容旧 YAML，需要新的非默认内容时创建新版本。
- 历史 `default@1` DOCX SHA-256 固定为 `b21448dbc10e7c7d5028490ddc079d784eb12a0360b35be2345fa0218aa12cfb`；当前 manifest 的 `default@2` DOCX SHA-256 固定为 `b43f0515d707d2b86c3b15813fb655980b4153fcbfd0140bc2199f535760138d`，V1 文件原字节保留。两版共用的 YAML SHA-256 固定为 `e83a1e9f722074ecb69bbc66d7f19b21db4da284daa38688ec3fd0e7f8fa49a3`。
- 2026-08-27 用户明确授权一次性原位覆盖开发环境 V1，现有任务引用不阻断重置。生产必须停 API、Worker，删除本轮 V2 草稿及 V1、默认指针、版本序列，再由新 release bootstrap V1；不得直接改旧 payload/hash，也不得扩大删除范围。
- 本次授权不是修改 published seed 的通用先例；完成后再次改变 DOCX/YAML 内容必须创建新版本。hash 不匹配仍须失败关闭，不得放松读取校验或增加备用路径。

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
