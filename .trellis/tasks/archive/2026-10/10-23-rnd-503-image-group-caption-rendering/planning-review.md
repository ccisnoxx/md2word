# RND-503 独立规划审查与修订（2026-10-23）

## 审查身份和范围

用户明确要求一个全新的architect子代理独立只读审查prd/design/implement，重点为依赖集成、分组阈值、caption绑定及历史恢复。主会话用原生协作工具派出 `/root/rnd503_architect_review`（昵称Hume，角色architect），fork_turns=none，不继承主会话推论；仅此一个审查代理，不派实现代理。

审查者独立读取v1三件套、真实代码/测试/Spec/产品合同和最终IR-204 Git对象。完整结论为**2项P2规划阻断项，无确认P1/P3**；模块划分、保守归组、IR-204 uncertainty/evidence-only消费边界基本合理。主会话逐项查源码、执行合成内存探针并修订到v2，本记录不表示业务实现或运行验收。

v1原文件已在本轮开始前保存在系统临时审查快照；下面行号均指代理实际审阅的v1，不冒充v2位置。原SHA-256：

- prd.md：`2a1095d101cb027b3946a6c5bdd4220c270f3b98716e4d1cba15db8c76351340`
- design.md：`350cb92be459aef24d059b51bd592a41a4cf594af8c0bafae0e0e52e79007e60`
- implement.md：`76d739e171ba9ef937368e8a82f006dca652b3daa1655193b1c42e88ff59a225`

## P2-1：非IR渲染输入绑定缺失

**审查发现。**v1 design.md:80只列规则/源/预期hash和实际尺寸，:86/88却要求独立源重验，:106–112要求三恢复入口重验。没有说明生成时模板、有效页面/栏几何、符号替换和投影版本如何固定。相同IR用模板/规则A生成，再由当前配置B恢复，要么误拒绝合法旧件，要么只能信报告中的expected，无法闭合源重建合同。

**主会话核实。**word_renderer.py:195–211加载语言模板及subscript_config_path，:227–269应用模板页面/边距；text_renderer.py:396开始还会归一化并应用格式替换。execution.py:3310–3332的当前恢复输入只有原IR、DOCX和公式报告。用现有renderer、MINIMAL_PNG_BYTES、同一合成IR及临时合法配置进行了只读探针：

| 项目 | 配置A | 配置B |
|---|---|---|
| 模板页宽/左右边距 | 21cm / 1cm | 18cm / 2cm |
| 合成格式规则 | DemoToken→RenderedA | DemoToken→RenderedB |
| 实际caption | Figure 1: RenderedA | Figure 1: RenderedB |
| 实际有效宽度EMU | 6840220 | 5039995 |
| 实际图片宽EMU | 2736088 | 2015998 |

两次IR SHA均为`9aa93d84041700848c54fce41f683f4b89bd92ac4d408cac82dd4a32fb14ac32`。临时输入在TemporaryDirectory退出时删除，没有业务文件或输出DOCX落盘。首轮探针配置漏必填schema_version，被现有校验明确拒绝；补齐template-config/v1后取得上述真实差异，不将夹具错误算业务缺陷。

**v2修订。**design的“生成时输入与投影版本绑定”定义私有image-render-inputs/v1：原模板/config/格式输入身份与hash、最小有效值/规则快照、语言/文本投影版本、各span写前几何，并绑定原文件与同一不可变candidate/receipt。第一次从实际加载值固定输入；恢复使用原文件IR+冻结输入，不读取当前模板指针或运行时路径。expected由源+冻结规则重算，actual从OOXML独立提取；必要输入缺失/未知版本/hash或身份错误明确失败，不降级legacy。已有格式owner只增最小冻结/重放入口，不重构资源版本系统。PRD R6/AC8与implement步骤、文件清单、配置变化/版本损坏测试及隐私边界同步。

**主会话结论：确认P2，已在规划层修订闭合。**未执行新报告代码，因此不宣称实现测试通过。

## P2-2：开发基线与可部署回退版本混用

**审查发现。**v1 implement.md:109把依赖集成后的实施前HEAD当回滚点，:110又允许回退writer→证据/接线diff，同时要求活跃worker理解新报告；design.md:135同样没有明确保留reader。已有新布局表格候选/receipt/历史指针后，实施前旧checker将全部DOCX表格数与IR内容表格数等值对账，会拒绝完整文件。排空当前队列不能消除未来历史复用。

**主会话核实。**evidence.py:75–105的计数与blocking flag、execution.py:3275–3283和:3329的重验/错误映射与该推论一致。v1现状调查中已成功执行的同HEAD内存反例证明：图片数不变，追加1×2布局表后，旧evidence给出ir_docx_integrity:table_count_mismatch。本轮复用该未变输入/源码的证据，没有重复造一遍相同探针。该事实不是已有B1的运行验证。

**v2修订。**将B0限定为开发差异基线，新增明确的B1兼容回退构建合同：保留新报告/冻结输入/marker/分类/投影版本及三入口reader、公式和receipt接线，生成侧只用原有单图writer。正常grouped/v1与回退single-only/v1是代码构建策略身份，随原文件冻结，非运行时配置/前端任务参数，不新增第二条流水线。产生新件后不能卸载reader或退回B0；上线新生成侧前须记录实际B1构建/hash及其恢复新报告的三入口、跨代历史指针、旧公式报告和损坏拒绝证据。PRD AC8、implement有序步骤/回归/完成定义同步。

**主会话结论：确认P2，已在规划层修订闭合。**B1尚未实现，不声称部署回滚已就绪。

## 其它重点与未列为缺陷的风险

- 依赖事实：manifest IR-204=done、归档completed/人工接受成立，最终业务提交17cde1f不在当前1835263祖先中。现有实施前集成硬门是正确的，当前仍未就绪，不能因为审查完成而start。
- 分组阈值：代理确认源连续run、明确阈值/等号、连通分量后全组复核及竞争分量整体拒绝可执行，未发现确认缺陷；v2保持数值不变，不为提高覆盖率调宽。
- caption：最终IR-204的evidence-only仍保留独立paragraph；v1对uncertainty/共享竞争/external paragraph的并排否决与接受合同一致。v2不改变语义归属或搬动段落。
- metadata新增键：接受IR-204固定输出mineru_validation/mineru_validation_input，默认None；当前恢复比较使用record.metadata.get(key)，缺键与None相等，不会只因新增键失败。主会话已核对None/非空两类比较，**不把新增键本身计为确认缺陷**。原IR非空但旧reader忽略等形态列为集成验收输入；本轮没有取得对应实际生产记录。
- 额外文字澄清：slot已含半间隔，v2明确所有slot宽相加等于表宽，margin在slot内承载间隔，避免重复计入；不新增布局算法或验收范围。

## 复核状态

同一architect随后完整只读复核v2三件套及本记录，结论为：**两项P2均在规划层闭合，无新增确认P1/P2/P3，无剩余规划阻断项**。已核对真实单次加载输入、原文件expected重算、B0/B1分离、两种冻结构建策略及双向恢复测试；未发现新增通用层、配置产品或隐私矛盾。主会话复核这些结论与v2内容一致，未再改变三件套行为合同。

分组阈值、源序、caption语义保持原结论；IR-204实际集成硬门仍未就绪，尚未取得人工规划批准。独立复核只证明规划缺口闭合，不证明新报告/B1已实现或运行验证通过，也不代表可start。最终task validate和工作区检查见planning-validation.md。业务代码、测试、脚本、Spec保持原字节，不start、不提交/push、不归档。
