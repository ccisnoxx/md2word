# DOC-001：合入文档包和索引

## 授权与目标

2026-10-12 本轮用户授权实现，仅交付 R0 文档包与索引。此前父子任务不存在，manifest 为 blocked；本文件依本轮明确需求补建，不代表找到了此前获批文件。
让开发者、产品和审核人员从根 README 导航到统一产品、架构、设计、实施和任务入口，并区分目标合同与运行事实。
父任务：`10-12-datasheet-docx-delivery-quality`；无依赖任务。实际分支 `docs/datasheet-delivery-baseline` 是本次等效文档分支。

## 范围与非目标

纳入已有文档包，核对目录和文件、补齐索引与权威关系、验证相对链接。
不重写产品/架构正文，不覆盖或删除既有事实文档，不重写 README 运行说明；不修改业务代码、测试行为、数据库、API、前端、配置或发布脚本；不实施 BAS-001 及其他后续任务。

## 不变量

- 一次只实现当前任务；保持模块化单体，不引入微服务、Kafka、向量库或第二套转换流水线。
- 一个 DocumentJob 只有一个用户主 DOCX；其他语言须创建或克隆任务。
- direct_pdf_to_word 不调用 AI Provider、翻译 Prompt 或翻译术语集。
- MinerU 是唯一 PDF 解析入口，不增加 OCR 预检或多解析器路由。
- HTML 可解析时输出 Word 原生表格，不以截图作为默认简化方案。
- 质量 blocked、翻译 unreviewed 均可内部下载，但不得批准或发布。
- 前端消费后端权威状态或 available actions，不自行推断发布资格。
- 不新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
- 不削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全边界。
- 文档目标不得被标注为已经上线；当前实现差距由后续任务验证，不能在 DOC-001 偷改业务。

## 验收条件

- AC1：七类文档目录齐全；清单声明的文件、45 个任务 prompt 和 bootstrap 文件均存在。
- AC2：根 README 提供产品、架构、实施计划和任务入口；原正文及运行说明逐字保留。
- AC3：PRD/冻结决策、已接受 ADR、实施计划、backlog、manifest、API 事实和 Trellis spec 的权威关系明确。
- AC4：根 README、文档包、既有 docs、bootstrap 及本轮 Trellis Markdown 的全部实际相对链接有效；报告失效列表和检查边界。
- AC5：docs/api、docs/dev、docs/testing、docs/runbooks、docs/deploy 全部既有文件保留且内容不变；业务代码、测试、配置及既有 .gitignore 改动不被覆盖。
- AC6：git diff --check 通过；未跟踪文档单独检查空白；task.py validate 通过。
- AC7（实现阶段交付）：manifest 仅 DOC-001 变更，最终 review；子任务 in_progress，父任务 planning；不提交、不 push、不 archive，交付 commit plan。

## 权限、失败与停止语义

仅本地文档及任务元数据写入；没有生产、凭据、专有样本或外部服务授权，也不需要它们。
缺文件、坏链接或验证失败应列明并在当前文档范围内修复，不伪称通过。
依赖未 done/人工接受 skipped_existing、不可消解的 PRD/冻结决策/ADR 冲突、未批准破坏性迁移或覆盖发布件/删除审计、必须改变冻结模式/表格/下载/发布规则、必要样本/外部系统/安全授权缺失且不能 adapter/fake 时，标 blocked 并停止。
完成仅表示实现待评审，done/skipped_existing 必须人工验收。

## 人工验收与收尾授权

2026-10-12：用户已人工接受 DOC-001 的实现、测试证据和残余风险，并确认当前 commit plan。AC1–AC6 保持；AC7 的 review/in_progress/不提交不归档是实现阶段交付门，已达到。此后依据本次授权将 manifest 改 done、子任务归档 completed，并提交精确清单，不 push 或启动后续任务。实际新增了文档入口并修复 46 个坏链接，不采用 skipped_existing。
