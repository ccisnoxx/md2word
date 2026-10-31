# 公式字面转义与正体函数最小适配

## 目标与授权

按用户已经审查的三文件方案补齐公式子集，使两个转义及六个函数命令在原有数学边界内生成原生 OMML，并使已认证字面下划线不被误报为 TeX 残留。

实施轮用户明确要求“按已审查的三文件最小方案……创建最小 Trellis 任务，完成规划并实施……仅允许运行新增的独立直接回归”。该授权承接前一轮最终审查报告及实施顺序，不增加新的产品、兼容或验收决策。本任务文档按同一范围落地后进入实施，不重复询问已经给出的创建、实施和新增回归授权。

## 已确认事实

- 实施基线 main 为 `b3657cb711cbae0aa23ce74767eb9f2024b5eb21`；来源快照为 `c9b1e6a9642d23d932bcd98c107e8bc66fb3c361`，只借鉴有限行为，不搬整份 parser。
- 基线 `app/conversion/docx_rules/formula.py:493` 在反斜杠后先扫描字母；`\,`、`\_` 会降级为 invalid_syntax，六个函数名缺少分支而降级为 unsupported_command。
- 基线 `formula.py:691` 已为基础 run 写 p；text/roman wrappers、显式 b/i、内部空格及受控降级已经存在。
- 基线 `app/services/renderer/docx_quality.py:125` 拼接 w:t/m:t 并扫描残留；报告验证后只精确排除 text_fallback。原生 `Noise_RMS` 会触发 `_RMS` 模式，必须同批适配。
- 固定审查报告位于 `/Users/sc/.codex/worktrees/mineru-root-heading-20261031-xtefthlw/evidence/formula-minimal-review-20261031/review-and-minimal-plan.md`。

## 需求与验收

| 编号 | 可观察行为 | 断言范围 |
| --- | --- | --- |
| AC1 | `\,` 产生 U+2009，`\_` 产生 U+005F，不把字面下划线变成 sSub；六个函数 ln/log/exp/sin/cos/tan 保留为 p 数学文字 | 真实共享 parser 与精确字符/结构 |
| AC2 | ENOB 代表式在 formula block、inline 和 HTML 表格入口形成原生 OMML，报告 mode、源字段/hash 与输出绑定正确 | 最小独立 IR、正式 render_to_result 及质量/报告校验 |
| AC3 | 只有已通过现有报告和字节绑定校验的 OMML 字面下划线得到窄处理；普通文字、无报告、未登记对象及其他 TeX 残留不获得全局豁免 | 有效/缺失/损坏报告、原始反斜杠/美元残留、重复文本的范围反例 |
| AC4 | 原有 p/b/i、text 空格、脚本原子、数学边界与普通路径/标识符保持 | 直接受本次命令分支和残留处理影响的反例 |
| AC5 | 未知命令、非法结构与错误仍按原 reason、提示及原式降级；篡改实际字符/样式仍被绑定拒绝 | 代表性失败、字节修改和旧 text_fallback 产物 |
| AC6 | 六个原有工作区、索引及未提交内容不变；历史11测试与2文档维护不纳入；实施轮只运行新增回归，提交轮不再运行测试 | 外部保留基线、最终 diff/status、真实执行日志 |

## 文件与边界

产品及直接回归仅三文件：

- `app/conversion/docx_rules/formula.py`
- `app/services/renderer/docx_quality.py`
- 新增 `tests/test_formula_literal_support.py`

必要文档仅本任务记录与 `.trellis/spec/backend/word-generation-rules.md` 的 MATH-002/MATH-003。不修改原有测试或搬入历史文档同步。

必须保留 main v2 数学输入、源对账、有限 tag/结构拒绝、四种 FormulaParseError reason、逐字受控降级、formula-render/v1 与 formula-output/v1、预期 hash 写入前冻结、历史请求幂等与已存结果验证。

## 不在范围内

不增加 Sigma/pi/tau 别名、WPS/字体上下文、默认变量样式、普通文本命令表或裸数学扫描规则。不改翻译、持久化、API、模板、依赖或部署；无报告/坏报告不获得新的残留豁免。

实施轮仅允许新增模块的直接回归；不运行旧测试、全仓、lint、类型检查、构建、CI 或发布脚本。本提交轮仅授权将本批源码、独立回归、必要Spec及任务记录保存为一个本地提交，不再运行测试；不推送、合并或删除分支。

## 收敛结论

产品范围及验收与前次最终审查一致，无阻塞的用户决策。PRD 已按最终结构收敛；设计与执行清单记录技术实现边界，按现有明确授权继续实施。

## 后续本地提交授权

用户已明确授权本批一个本地提交。源码与独立回归复用最终19/19通过的版本，不再测试；其他工作区及历史测试、文档维护不纳入。本地提交不包含推送、合并、分支删除或自动归档授权。
