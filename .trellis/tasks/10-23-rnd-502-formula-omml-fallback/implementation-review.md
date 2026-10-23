# RND-502 实现独立复核

## 结果接线专项

- Reviewer：全新 `/root/rnd502_receipt_review`，role=`critical_reviewer`，`fork_turns=none`，独立只读，不修改仓库。
- 范围：execution.py、result_state.py、formal_mineru_conversion.py 与相关三个任务结果/状态测试的实际 diff。
- 结论：无确认可行动问题；不代表公式/translator 整体、生产或视觉门通过。
- 核验：三恢复入口、历史明确指针跨代语义、文件原 IR 绑定、选定描述不可变、锁外 I/O、锁内最新质量摘要、CAS/取消/超时、三个 adapter 共用 owner、新代清槽、事件不含逐式报告/旧残留示例。
- 实际只读探针：两组 `python -B` 纯内存探针通过，覆盖质量单调/新代/非获胜身份、合法/缺损报告、跨租户 IR、同锚点改值、legacy 无新增读取、事件脱敏；定向 diff --check 通过。
- 主会话核实：真实新增 3 个 unittest 通过（包含多种质量状态、file/SQLite/fake MySQL、legacy/explicit/receipt 正常及同锚点改值）；详细输出见 `tests/tmp/rnd502/result-targeted.log`。80 个原相关回归通过，1 项旧“只有一次检查”断言因新增 receipt 复检调整后单项通过；其证据不替代全范围 check。

## 全范围 Trellis check

- Checker：全新 `/root/rnd502_full_check`，role=`trellis-check`，`fork_turns=none`；已加载当前任务与最小 context，接管冻结后的业务/测试修复权。
- 已确认并进入修复：脚本内 text 空格、未闭合 block 分隔符、裸花括号下标的扫描范围，以及超阈值表格的公式内容投影和长纯文本扫描成本。
- 主会话核实大表问题：既有 expanded 路径将 HtmlCell 压成 text，新报告按源 HTML 计数会新增完整性拒绝。这属于 v2“全部 table formula 使用共享入口”的必要接线缺口；最小修复保留既有阈值、展开/重复几何与 Word 原生表格，只收敛内容投影并保留原 HTML，由渲染和库存共用，不改变大表布局算法、不引入 CanonicalGrid、不放宽完整性对账。
- Spec 回归矩阵的 MATH 旧描述已同步，去除“tag 不显示编号”的过时陈述。
- 主会话提示并由 checker 确认：公式 receipt 完成分支不能用 patch 中陈旧 passed 覆盖锁内 pending/blocked。修复仅在带报告的选中 receipt 完成阶段基于当前 job.quality_status 派生，不改变独立质量 patch 或 legacy 更新语义；三 adapter 测试增加陈旧 passed 竞争输入。
- 核实并修复 table captions/footnotes 两组独立去重与源库存共用 seen 的偏差；同文不同入口仍按各次实际出现登记。image 保留其既有组合去重规则。
- 新增共享 `app/conversion/docx_rules/table_expansion.py` 只承接既有展开内容投影，保留原 HTML/source row/column；没有新表格布局流水线。
- 移除本任务产生的纯转发/无人调用私有文本准备 helper，Spec owner 同步实际 `_render_mixed_math/_render_inline_children`。
- 同一 critical_reviewer 扩展只读复审完整公式/翻译 diff，独立纯内存核实原嵌套 HTML 翻译 P1 在 12 条正文/表格路径闭合。
- 扩展复审新增 4 项有实证问题并交 checker 修复：P1 run 未投影可见/行为子节点（主会话纯内存追加 noBreakHyphen 独立复现哈希不变）；P1 `{a+b}^2` 等显式分组基底被拍平；P2 相同公式跨 caption/cell 的 source 来源交换；P2 强 semantic 数字公式被 dollar 纯数字排除条件漏判。修复必须保留输出闭合投影/实际位置上下文/数字与金额区分，不靠放宽校验。
- 首轮主会话 15 模块 301 项通过；release 202 项中一个旧“Note: E=mc 必须是连续 XML 字符串”的断言不适配 OMML，OpenAPI 当前。将按原目的维护该单 OOXML 语义用例，不削弱题注/表格/脚注顺序。
- 首轮门禁已改名保存为 `tests/tmp/rnd502/pre-security-fix-*`，不能冒作最终修复后的结果。
- 最终 checker focus：`tests/tmp/rnd502/trellis-check-focused.log`，120 项/1.512s/OK；受影响 compileall 和 diff --check 通过。仓库无独立 lint/typecheck 入口，不冒称工具通过。
- 最终 critical_reviewer 独立只读复验全部 5 项：3 mode×8 节点/属性的 24 次篡改拒绝；重排 block/caption/cell/note 的5个来源与实际锚点一致；numeric semantic 三入口 OMML/零残留与金额负例；3种完整 group/script；5种 semantic 包数学组合的10条零Provider路径。末轮 `\text{A B}^2` 与 `\mathit{x}^2` 完整基底/样式也独立确认。原 semantic 样式/畸形12路径另已核实。
- 最终结论：限定实际 diff 范围无剩余确认缺陷；解除本轮代码审查阻断。主会话冻结版本15模块306项、release202项/OpenAPI current、component1/1、direct矩阵5/5均通过，证据详 implementation-validation.md。未将离线检查升级为 Word/生产/真实数据库结论。
