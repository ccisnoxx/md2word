# RND-503 候选独立合同复核

2026-10-23，独立只读 critical_reviewer：`/root/rnd503_result_contract_review`。基于已形成的候选，重点审查持久化输入、三恢复入口、不可变结果及 B1；与另行进行的 Trellis check 分开记账。原 302 项暂存删除不属于候选，不作为实现删除审查。

## 已确认并交修正

1. **P2，跨 span 源序未被认证**：`image_evidence._verify_image_report` 在 span 内重置 previous_position，group 仅核对表是 body 子节点及 section。两合法图片行整表交换、每表 marker/图/注释均保持时，原报告仍被接受。主会话以 W400、x10/190、宽160、y80/300、高140 的4图两组独立重现，`build_renderer_evidence + ensure_renderer_integrity` 返回 accepted_group_count=2。要求按 plan 跨 span 验证实际 body 顺序，单图的消费边界涵盖完整注释；增加完整组及独立 single span 交换拒绝测试。当前状态：已交实施者，待修复与复验。
2. **表题空格去重兼容回归**：新 `caption_bookmark_inventory` 对 table 先去重再 strip，原 helper 先 strip 再去重。`['Table 1: Neutral', ' Table 1: Neutral ']` 新 inventory={}，原 `_unique_annotation_texts` 只有一个题注；writer 仍仅输出一条，唯一 bookmark/REF 因而被误抑制。主会话独立确认，要求保持原语义并加回归，不更改题注 owner。当前状态：已交实施者，待修复与复验。
3. **P2，资源/尺寸降级由报告自证**：合法 B1 单图文件的冻结策略改回 grouped/v1 并重算 inputs hash，reason 改 asset_unavailable 或 image_size_unfit，实际图均完整且 slot 可用，指定 expected_generation_policy=grouped/v1 仍被接受。主会话独立复现两种原因；要求 reader 从实际资产/源 slot 独立证明降级条件，不能仅相信 reason。真实缺图最终仍须完整性失败。
4. **P2，布局图片段允许未登记正文**：在图片 bookmark 内追加普通文本 run，图/注释/报告均保持，证据仍被接受。主会话独立复现；要求图片段仅含受控图片与必要锚点/排版结构，无额外可见或行为内容，防止布局表承载未登记正文。
5. **P2，快照校验异常可泄露私有值**：把冻结 caption_style.font_size 损坏为中性 PRIVATE_FORMAT_SENTINEL 并重算 inputs hash，Pydantic ValidationError 的字符串含该值，恢复异常可被写入 error/event。主会话独立确认；要求报告边界转成不带原输入的受控 ValueError，同时核对规则编译错误不会泄露 pattern/replacement，不改变原错误映射或吞掉意外错误。

## 已核查但不成立的疑点

恢复 validator 在严格报告校验前访问嵌套输入，畸形报告可能先抛 KeyError/TypeError；但 receipt 的 `_finish_prepared_result` 捕获并固定映射 uploading/oss_failed，legacy/explicit 外层 validating_legacy 同样映射。因此没有确认错误映射回归，不将该疑点列为阻断。开发错误文本可在实现范围内归一化，不能据此扩大门禁。

此记录不表示最终候选已通过。修复、实际测试和独立复验结论将在最终复核/validation记录中闭合；本轮不提交或 push。

## 最终状态补记

上列“待修复”是发现当时的历史状态，现均已关闭。后续还发现第六项非有限bbox报告经Pydantic JSON往返变null自损坏，主会话独立复现，writer/checker共用JSON安全投影后由同一审查者复验NaN/±Inf关闭。Trellis check另行关闭tcW单位及图片变换两类缺口；主会话实际LO裁切亦已对照修复。最终合同/B1证据核对无未关闭确认代码缺陷，详 `implementation-review-final.md`；Word/部署预览和Golden环境待验仍明确保留。
