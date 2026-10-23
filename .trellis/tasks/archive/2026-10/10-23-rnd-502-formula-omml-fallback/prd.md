# RND-502：公式 OMML 和降级规则

规划版本：2；日期：2026-10-23（Asia/Shanghai）；阶段：R5。根据独立 architect 审查的 P1/P2 修订；核实记录见 `planning-review.md`。
状态：planning，等待人工评审；本轮不修改业务代码、不执行 `task.py start`、不提交、不 push。

## 目标和业务结果

统一 inline、block、table formula 的解析、OMML 输出和受控降级。用户在 Word 中看到完整公式和原有上下文；支持的数学结构可编辑，不支持的原式有明显提示和可追溯质量信号，不通过删内容消除 LaTeX 残留。

## 准入和现有能力

- 唯一依赖 BAS-001：manifest=`done`；HEAD 归档任务=`completed`，记录人工接受实现、证据和风险；工作提交 `107624d7e87f8287c83020d9c751e9d54d23d855` 在当前 HEAD 可达。依赖门通过。
- 当前已有有限 TeX→OMML 和简单上下标渲染，但失败回普通文本归一化，没有逐公式降级回执。探针确认公式编号丢失、上标范围扩大、文本空格丢失、逻辑符号改值和表格 HTML 标签泄漏，证据及行号见 `research/current-state.md`。
- 本任务有实际增量，不建议 `skipped_existing`。RND-501 仍为独立 planning 任务，不是本任务依赖，不提前集成其 RenderPlan、CanonicalGrid 或其他任务业务。

## 范围和需求

| ID | 需求 |
|---|---|
| R1 | 明确数学边界内的 LaTeX、MinerU semantic formula 和已有上下标表达使用同一公式入口；普通正文、HTML 和公式保持原顺序。 |
| R2 | 已有可安全支持的分式、根式、上下标、符号及样式输出原生 OMML；简单语义上下标可保留原生 Word run。不得仅以“没有 TeX 残留”判断公式正确。 |
| R3 | 不支持、语法错误或无法证明保真的数学表达整体降级为原始公式文本，使用清晰的“公式降级，需复核”提示；原式不经过术语替换、HTML 解释或破坏性归一化。此次选择文本降级，不新增公式图片引擎。 |
| R4 | 每次公式出现都可定位、可审计，保留转换方式、稳定失败原因、源公式哈希和输出关联；普通事件只给脱敏汇总。显式受控降级与未登记的 LaTeX 残留区分。 |
| R5 | block、正文/列表/标题 inline、表格单元格及其 caption/context/note 的公式规则一致；表格仍为 Word 原生表格。 |
| R6 | 保持当前任务结果身份、generation、receipt、历史主件恢复和权限合同；新增公式诊断不得阻止内容完整的降级草稿内部下载，也不得自动批准或发布。 |
| R7 | Renderer 接受的数学边界必须在翻译准备时同样可识别。公式必须被现有 Codec 整体保护，或作为明确数学子树保留而不送给 Provider；不能完整保护的跨节点表达在外部调用前明确失败，不能让公式作为普通正文被翻译。 |

## 权限、质量和失败语义

- 精确保留原式的文本降级为 `formula_text_fallback` warning，需要人工复核；不默认新增图片降级，图片型公式能力留在范围外。
- 未登记的 LaTeX 继续报告 `docx_latex_residue:*`，不能因引入受控降级而屏蔽普通正文的残留。受控原式允许保留 TeX 字面内容，但必须同时有可见提示、逐公式证据和 warning。
- 不支持的命令是预期降级，不是执行异常。数学解析不能吞掉文件、XML、存储或内部程序错误；现有 `rendering/quality_checking → render_failed`、`uploading → oss_failed` 分类保持。
- 翻译准备与渲染失败分开：数学保护边界无法安全闭合时，在 Provider 调用前以稳定内部码 `translation_formula_boundary_unprotected` 和固定安全消息失败，顶层沿用 `translation_failed`；不修改 Codec 识别规则、不回退 direct、不生成混合语言主件，保留源 IR 和诊断。
- 源公式缺失、实际输出缺失或回执与实际 DOCX 不符仍失败关闭，不能降低已有完整性门禁。本任务不改变源缺失时的 `document_ir_failed` 行为。
- 公式摘要只追加到既有质量摘要，不用公式正常/降级来宣告整份文档质量通过：`pending` 保持 `pending`、`blocked` 保持 `blocked`；已有 `passed` 遇公式 warning 只能降为 `warning`，不能上调任何质量结论。
- 继续使用 owner/admin 授权和后端 available actions；`blocked` 和翻译 `unreviewed` 可内部下载但不得批准或发布。已有其他警告不因当前任务被清除。

## 必须保持的不变量

- 一次只实现 RND-502，不提前实现 backlog 中其他任务。
- 保持模块化单体，不引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；其他语言通过创建或克隆新任务获得。
- `direct_pdf_to_word` 不调用 AI Provider、不读取翻译 Prompt 或翻译术语集；符号/排版规则与翻译术语继续分离。
- MinerU 是唯一 PDF 解析入口，不增加 OCR 预检或多解析器路由。
- HTML 可解析时必须输出 Word 原生表格，不以截图作为默认简化或回滚方案。
- 前端不推断发布资格，只消费后端权威状态或 available actions。
- 不新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不为通过测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 公式内容不翻译、不改值；降级必须可见、可审计；不得因失败删除公式。

## 非目标

全功能数学排版引擎、matrix/cases/align 的完整排版、自定义宏执行、新数学依赖或外部服务、翻译 Token 规则变更、公式图片合成/裁图、第二套 Renderer、RND-501/503/504/505/506、通用质量/审核/发布系统、数据库 schema 迁移、前端编辑和额外主 DOCX。

## 验收条件

| ID | 可观察结果 |
|---|---|
| AC1 | 同一公式分别放在 block、inline、table cell、caption/context/note 后，支持结构一致；公式计数按出现次数，重复原式不能被去重丢失。 |
| AC2 | 支持的分式、根式、上下标、常用符号、overline/boxed/样式生成正确 OMML；`x^2+3` 的上标只含 `2`；`\text{A B}` 的空格保留；`\vee` 不得输出字母 V；现有矩阵中的合法简单 `\tag{7}` 保留数学主体 OMML 和可见编号，畸形/不支持编号写法整式降级。 |
| AC3 | 混合正文中的分式只转换数学片段；表格中的 `<b>/<sub>/<sup>` 保持原位置样式，不把 HTML 标签或整个自然语言段落写进 OMML。 |
| AC4 | 未知命令、未闭合参数、unsupported matrix/cases、空/异常数学表达不静默成功；非空原式在降级区域逐字保留，并有可见提示、`formula_text_fallback` 和稳定 reason；空源沿用现有输入完整性失败。 |
| AC5 | 每一条公式证据同时绑定源位置/哈希和写入前确定的预期输出投影；最终 DOCX 锚点范围的值、上下标属性和 OMML 结构必须与之相符。保持 anchor/mode/count 不变而改数字、移上下标或截断原式也必须被拒绝。未登记原始 LaTeX 仍被扫描，不能靠删除字符、删除整式或放宽正则实现“零残留”。 |
| AC6 | 符号规则不得改写已识别公式或其降级原式；普通正文规则继续工作，UNC/路径、金额、escaped dollar、HTML 比较符不被误判为公式。已有 semantic sub/sup 可编辑且数字/单位/运算符不变。 |
| AC7 | converter 富文本/annotation 与表格 DOM 公式边界在翻译准备前闭合；`<eq>\text{High Low}</eq>`、数学内样式交错和混合正文必须保持公式原值。主动改写数学内部的 fake 不能被接受：数学子树不发送 Provider，已有分隔符由 Codec 保护；边界不完整则调用前明确失败。非数学正文仍正常翻译，现有非公式 item ID/回填索引保持，Codec 规则和 direct 零翻译调用不变。 |
| AC8 | 内容完整的降级生成可内部下载主 DOCX；摘要携带 warning，pending/blocked 不被提升，unreviewed 不自动批准；owner/admin、blocked 批准拒绝、publish enabled/eligible 既有规则保持。 |
| AC9 | 并发复用 renderer 无诊断串扰；同代重投只使用已选 receipt，新代不继承旧摘要。分别覆盖 legacy 扫描、明确历史 result_file_id、已有 receipt 三入口：旧证据不被新默认字段破坏；明确历史主件允许原有跨代复用，不把旧报告导入新代质量；新报告损坏不得伪装成 legacy。已有翻译根计划不因新抽取规则被覆盖，来源不匹配按现有合同失败关闭。 |
| AC10 | 原生表格、标题/编号/字段、图片、布局、模板和源→IR/IR→DOCX 完整性回归通过；没有额外主 DOCX、外部 AI/TeX 调用或数据库结构变更。 |
| AC11 | 定向/组件/相关样本/发布检查及 Word 人工验收按 `implement.md` 留证；未运行的线上、专有样本、真 Word 检查明确标为未验证，不以 OOXML 通过替代。 |

## 规划停止条件

依赖失效；PRD/冻结决策/已接受 ADR 出现不可消解冲突；必须实施未批准的破坏性迁移、覆盖已发布件或删除历史审计；必须改变冻结任务模式、原生表格、下载或发布规则；必须使用缺少授权的专有样本、外部系统或人工安全授权且 fake/adapter 无法替代。实施前基线漂移、RND-501 同文件变更或实测方案不能满足上述合同，先修订规划并重新评审，不擅自扩大范围。
