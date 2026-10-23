# RND-504：WordPreviewProvider

## 目标与业务结果

为用户主 DOCX 提供可替换、只读的 PDF 预览能力，支持可选页面 PNG，并将结果登记为受控 Artifact。让后续页映射、页级检查和审核发布取得绑定具体 DOCX 的证据；预览失败仍可内部下载主件，但不能批准或发布。

修订 2 的三份规划及 RND-504 实现均已由用户审核接受，2026-10-17 明确授权按三笔计划提交、归档本子任务并记录会话。实现工作区为 `/Users/sc/.codex/worktrees/rnd504-implementation/md2word`，分支 `md2word/RND-504`，基线 `033cb61` 包含已验收 CON-103；已执行 start、实现与复核，现已归档为 completed。仅实现 RND-504，生产 backend 保持 disabled，不部署、不 push、不开始其他任务；归档路径及提交证据见 validation.md。

## 规划调查基线与事实

- 阶段 R5；依赖 CON-103 的 manifest 为 `done`，归档任务为 `completed`，人工接受实现提交 `bd828da4e3a3025856afd758e0b0a686ff6ccb72`。
- 规划根目录 HEAD 为 `4c40e6c52bde072a7ad3afab67eb425f757bd33c`，分支 `md2word/TAB-306`，不含 CON-103。只读业务调查以包含该依赖的 `033cb61e3f6ac91f5d324790eb1a8ea920b783de` 为准；实现前必须准备正确基线。
- 开发文档已有 soffice→PDF→PNG 流程，正式业务链没有任务级 PreviewProvider、预览 Artifact 或失败重试合同，不能建议 `skipped_existing`。
- 已验收基线有质量/复核/交付状态、主结果 receipt、generation/CAS 和受权下载；现有质量证据主要来自 OOXML 与内容完整性，不能证明真实分页。
- 事实定位和权威文档清单见 `research/preview-baseline.md`；技术方案见 `design.md`，执行与验证见 `implement.md`。

## 范围内需求

| ID | 需求 |
|---|---|
| P1 | 定义不依赖 DocumentIR、任务仓储或翻译语义的 WordPreviewProvider port、输入/输出/错误合同、测试 fake 和可执行的生产 adapter 边界；本任务维护版本化进程协议与适配代码，不能仅靠永久 unavailable 交付。 |
| P2 | 成功至少提供有效非空 PDF 和正页数；PNG 可选，启用时页序、数量、尺寸、MIME 和大小必须有效。空输出或必需页面无效不得成功。 |
| P3 | 输入、输出、页数、像素、时长、尝试次数和临时空间有上限。生产调用隔离文件、网络、宏和子进程，超时终止整个进程组并清理本次临时目录。 |
| P4 | 绑定当前选定 DOCX 的 file ID、SHA-256、generation 和 profile，不扫描“最新文件”猜测身份，不重新生成主 DOCX。 |
| P5 | 支持有界自动重试、Worker 重投恢复和内部应用服务的预览单独重试；不增加 DocumentJob generation，不再调用 MinerU、翻译或 renderer。首次 claim 原子保存历史 request ID 去重记录，跨 run/重启重放不能获得新预算；旧租约和旧代不能覆盖新证据。 |
| P6 | PDF、页面和 manifest 登记为 document_files，保留来源/hash/provider/version/profile/attempt/时间。只有当前提交 manifest 的受权文件可作为有效预览。 |
| P7 | 预览失败写结构化阻断证据并保留主件/审计；已生成主件可完成为 `succeeded + blocked + internal_draft`。现有确定性内容丢失、渲染和存储失败合同不能降级。 |
| P8 | 本任务负责预览 blocker 的增加、替换及解除。成功重试只撤销可证明归属本预览的贡献：基础 pending/warning/passed 恢复为其可证明状态，其他/未知/并发新增阻断保留；不单凭预览把未检查质量置 passed，不恢复旧批准或晋升交付，不依赖后续任务才能解除自身阻断。 |
| P9 | 默认 backend 为 disabled；新任务固化非敏感策略快照，历史任务不自动回填/重跑。禁用且非必需为 unavailable/未检查；必需但不可用或实际生成失败均阻断质量。 |

## 非目标

- RND-505 的页面映射/anchor 同步；RND-506 的裁切、溢出、空白、重叠、密度规则和 QualityRun 聚合。
- QA-602 的预览/复核查询和公开重试 API、预览 UI、三栏审核及下载提示 UI；本任务只提供内部应用入口和现有文件通道。
- CON-104 的完整 available actions 协议、QA-605 的 PublicationRecord/发布 API；不提前实现后续任务。
- 外部 SaaS 选择/采购、安装生产 Office/PDF 引擎、引用本机插件缓存作生产依赖。
- OCR 重新解析 Word、自动修文档、字体/模板重排和视觉合格判定。

## 不变量

1. 一次只实现当前任务；保持模块化单体，不引入微服务、Kafka、向量库或第二套转换流水线。
2. 一个 DocumentJob 只有一个用户主 DOCX；其他语言创建或克隆任务，预览为内部 Artifact。
3. `direct_pdf_to_word` 不调用 AI Provider、翻译 Prompt 或翻译术语集；MinerU 是唯一 PDF 解析入口，不增加 OCR 预检或多解析器路由。
4. HTML 可解析时必须输出 Word 原生表格，不能用截图默认替代；预览不修改 DOCX/DocumentIR。
5. 质量 blocked、翻译 unreviewed 均可内部下载，但不得发布；blocked 不得批准。前端消费后端权威状态/available actions。
6. 不新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
7. 不削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全；Provider 不进入 DocumentIR 语义，不执行不受控 shell/宏，不提供匿名文件服务。
8. 正式视觉验收以公司实际 Microsoft Word 为主；fake、PDF 可打开、LibreOffice 或像素相似度不能单独证明交付质量。

## 权限与失败语义

- 内部读取、重试及文件授权复用 tenant/company 与 owner/Admin 范围。应用下载入口校验当前引用，本地 HMAC Token 在读取时重校验；S3 直连沿用签发时授权和有限 TTL，不承诺旧 URL 在引用变化后立即撤销，不借此扩张存储代理或放宽授权。
- backend 只接收运维配置，不接收上传内容、任务参数或文件名传入的命令、URL、路径和环境变量；fake 只通过测试注入。
- 超时和明确暂态按上限重试；损坏 DOCX、非法输出、资源超限、沙箱/profile 不可用显式失败。耗尽后写 preview 局部错误，执行成功任务的顶层 error_code 不伪造为转换失败。
- 未知异常形成诊断，不能吞掉后成功；元数据无法持久化时禁止完成/晋升并等待恢复，不删除主件。
- 取消、总任务超时、归档、删除、换代或 published 后，迟到结果不能改写任务；published 不允许原地预览重跑。

## 验收条件

| AC | 可观察结果与证据 |
|---|---|
| AC1 | fake 组件测试消费正式 renderer 生成的最小 DOCX，登记绑定主件的 PDF、manifest、正页数；PNG 开关两种路径正确。（P1/P2/P6） |
| AC2 | 空/损坏 DOCX、超时、空 PDF、非法页数、PNG 数量/尺寸错误、超限及非零退出均不能产生有效预览。（P2/P3） |
| AC3 | 预览失败后 DOCX file ID/hash/receipt/下载字节不变，quality blocked、review 不得 approved、delivery internal_draft；确定性内容丢失仍按旧合同失败。（P4/P7） |
| AC4 | 暂态重试可成功，永久失败不盲重试，重投不重置预算；A→B→重启→A 的延迟重放不增加 run/attempt/provider 调用，同 ID 不同参数冲突，历史上限拒绝新 run 而非淘汰去重记录；单独重试不调用 MinerU/LLM/renderer。（P5） |
| AC5 | 并发 claim、过期租约接管、旧 attempt、取消/删除/归档、换代和 published 负例在三 adapter 上保持合同；真实 MySQL/部署 FS 缺口独立披露。（P4/P5/P7） |
| AC6 | 应用入口拒绝跨范围用户、篡改/过期 Token、落选/部分/旧代文件；本地已签 Token 在引用变化后拒绝，S3 不再签发旧引用但已签 URL 只保证有限 TTL。blocked/unreviewed DOCX 下载继续可用。（P6/P7） |
| AC7 | disabled/required、旧 payload、profile 快照、retry/clone 明确；仅预览阻断在成功重试后恢复原 pending/warning/passed，其他/未知/并发阻断仍 blocked，review/delivery 不自动晋升；无新增 public preview/publish 路由。（P8/P9） |
| AC8 | adapter 默认关闭；生产 adapter 路径必须通过正式 word-preview-exec/v1 子进程协议完成请求、成功结果、错误映射、hash/profile 校验及终止清理测试，仅 readiness 拒绝不算交付。真实引擎、字体、沙箱和 DOCX→PDF 证据仍为生产启用门。（P1/P3/P9） |
| AC9 | receipt/CAS、状态、权限、direct 零 AI、原生表格和样本门禁无回归；API 快照 current、文档/Spec 同步，未执行项如实记录。 |

## 停止条件与规划出口

依赖不满足、冻结 PRD/ADR 冲突、必须破坏性迁移/覆盖发布件/删除审计、必须改变冻结规则，或缺失必要授权且无法用 port/fake 完成本范围时停止并标记 blocked。生产引擎未选择不阻断本轮规划及 port/fake/配置边界交付，但阻断生产启用，不能声称真实预览已验收。

规划独立审查及修正见 `planning-review.md`；旧版 P8 的永久 blocked、未定义进程协议及仅当前 request ID 方案已被本版取代。首次实现授权不包含部署、外部调用或提交；后续三笔本地收口提交已单独获用户确认，部署及生产外部调用仍未获授权。最终实现与验证证据记录在本任务 `validation.md`，未观察到的生产能力不得标为通过。
