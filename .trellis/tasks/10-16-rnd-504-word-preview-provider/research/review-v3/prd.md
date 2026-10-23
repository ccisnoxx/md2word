# RND-504：WordPreviewProvider（修订 3，当前基线复用规划）

日期：2026-10-23。阶段：R5（DOCX、模板和预览）。状态：planning，等待人工评审。

## 目标和业务结果

为当前用户主 DOCX 提供可替换的只读 PDF 预览和可选页面 PNG，将输出登记为有授权、可追溯的 Artifact。预览失败保留主 DOCX，允许内部检查下载，同时阻断质量、批准和发布。

本次仅调查与规划。不得修改业务代码、执行 `task.py start`、提交或 push；后续实现须另获对本修订三件套的明确批准。

## 已确认背景与任务复用

- 唯一依赖 CON-103：当前 manifest 为 done；Git `28a2239` 中归档任务为 completed，保存人工接受 `bd828da` / `80b82db` 的证据。当前代码具备四字段状态、复核 CAS 和三存储投影；当前 22 项相关基线测试通过。原提交不在当前 HEAD 祖先链，不把功能整合误写为原提交已合入。
- 当前基线为 `01e6c1add86f1ba7f24abc120629fa2fe6bd5ed9`，实际分支 `md2word/RND-503`。当前没有 `app/services/preview/`、预览状态、预览 Artifact 类型及专用测试。
- 已接受实现 `931d2f65738f7592a5b3e2dd4c528f9e1b2a0e19` 与归档 `48818e9` 存在于本地 Git 历史。源实现的三个预览模块在独立临时快照复跑 40 项通过；这不证明当前基线已经具有预览能力，也不证明真实生产引擎或沙箱通过。
- 复用原任务 ID/slug 和原日期路径 `10-16-rnd-504-word-preview-provider`。历史原件保存在 `research/history/`，当前三件套描述当前规划，不继承历史实现/提交授权，不创建第二个子任务。
- 当前目标有真实集成差距，结论为“核验并最小集成既有实现”，无需重新设计第二套 Provider。当前不能建议 skipped_existing；如果后续指定的验收基线已完整包含等效能力，则改为仅验证并收口，经人工接受后建议 skipped_existing，禁止再造代码。

## 范围内需求

| ID | 要求 |
|---|---|
| P1 | 复用已接受的 WordPreviewProvider port、测试 fake、生产进程 adapter 和版本化执行协议；Provider 只接收 DOCX bytes 与非敏感策略，不理解 DocumentIR、翻译或业务仓储。 |
| P2 | 成功必须有有效非空 PDF 和正页数；页面 PNG 可选，启用时页数、零基页序、大小、实际尺寸及像素预算一致。错误、空输出和不完整输出不得成为成功预览。 |
| P3 | 输入包、输出、页数、像素、CPU、内存、磁盘、进程数、单次 timeout、run deadline、尝试数及历史请求数有界；生产必须证明隔离、无网络及宏不执行。 |
| P4 | 只消费当前已选 receipt 描述的主 DOCX，绑定 tenant/company/job、generation、file ID、size/SHA-256、profile。生成预览和单独重试均不得重新生成 DOCX。 |
| P5 | 保留有界自动重试、Worker 重投/过期租约恢复和受权内部单独重试；首次 claim 前持久化请求去重及预算，同 key 异参冲突，历史重放不移动 current、不增加预算。 |
| P6 | 追加登记 preview PDF、可选 pages 和 manifest；只有当前已提交 manifest 所指文件可作为当前预览。部分、落选、旧代、过期和删除文件不能获得下载授权。 |
| P7 | 普通预览失败已可靠留证后，可完成为 succeeded + blocked + internal_draft；主 DOCX、receipt、hash 和历史审计保持。主件或 metadata 存储不可确认仍按原错误合同失败，不能以失败预览掩盖后宣称执行成功。 |
| P8 | 预览拥有自身质量贡献；成功重试只解除自身 blocker，保留未知、其他及并发新增 blocker。原 pending 不自动变 passed，原公式 fallback 的 warning 不能丢失；旧批准和交付资格不自动恢复。 |
| P9 | 默认 backend=disabled、required=false；fake 仅测试注入。新任务冻结策略，历史任务不回填不重跑。disabled 且非必需表示未检查；required 不可用或实际生成失败必须阻断。 |
| P10 | 在当前基线上增量适配，保留 CON-104 的下载分类/警告、publish.eligible 与 enabled 分离，保留 TR-406 批次 CAS、RND-502/503 结果认证与共享生成件独立物理身份。 |

## 非目标

- RND-505 页面映射、block anchor、PDF/IR/Word 同步定位；RND-506 裁切/溢出/空白/重叠等页级规则。
- QA-601/602/603/605 的统一 ReviewRecord、QualityRun、公开 preview/retry/publish API、三栏 UI 或 PublicationRecord；现有文件通道和内部应用入口足够本项验收。
- 选择或采购外部 SaaS；安装、部署或启用新生产 Office/PDF/沙箱依赖；直接采用本机 LibreOffice 或插件缓存作生产依赖。
- 新 OCR/解析器、自动编辑或修表、模板/字体重排、第二套 renderer、批量/知识库及其他 backlog 功能。

## 冻结不变量

1. 一次只实现当前任务；保持模块化单体，不引入微服务、Kafka、向量库或第二套转换流水线。
2. 一个 DocumentJob 只有一个用户主 DOCX；其他语言创建或克隆任务，preview 只是内部 Artifact。
3. `direct_pdf_to_word` 不调用 AI Provider、翻译 Prompt 或翻译术语集。
4. MinerU 是唯一 PDF 解析入口，不增加 OCR 预检或多解析器路由。
5. HTML 可解析时必须输出 Word 原生表格；截图不能成为默认简化或回滚策略。
6. 质量 blocked 和翻译 unreviewed 均可内部下载；blocked 不得批准，blocked/unreviewed 不得发布。
7. 前端消费后端权威状态或 available actions，不自行推断发布资格。
8. 不新增中文转中文 Prompt、双语 DOCX、在线 Word 编辑、在线修表、批量任务或知识库。
9. 不为测试削弱权限、审计、不可变发布、技术 Token、内容完整性或路径安全。
10. Provider 不进入 DocumentIR 语义；不执行不受控 shell/宏；不提供匿名文件服务器。
11. 正式视觉验收以公司 Microsoft Word 为主；fake、协议符合性、LibreOffice 输出和文件可打开均不等于 Word 交付质量已通过。

## 权限与失败语义

现有 `get_job` 的 tenant/company、owner/Admin 和认证边界继续有效。预览重试为内部应用服务，需用户身份、原因及 UUID request ID；不新增匿名路由、命令/URL/路径输入或绕开配额的重试入口。已发布任务禁止原地重跑/覆盖；归档、删除、取消、失败及旧 generation 的迟到返回不得推进状态。

预览错误使用稳定局部码，只有 timeout 和明确暂态引擎故障可有界重试；输入、输出、安全、profile、资源和配置错误不盲重试。顶层执行错误继续沿用原 render_failed/oss_failed/document_job_timeout 等合同；不能将对象/metadata 失败降级为成功草稿。内部错误、原始 stderr、绝对路径、客户正文和租约不进入公共响应。

本地 HMAC 下载 Token 在读取时复查当前引用。S3 直连只保证签发时授权及有限 TTL，不能承诺撤销已签 URL；新 URL TTL 不超过主件、预览件和既有签发上限。

## 验收条件

| AC | 可观察结果 |
|---|---|
| AC1 | 当前基线正式 renderer 生成的最小 DOCX 经 fake 登记 PDF/manifest，PNG 开关正确；source file ID/hash/generation/profile 全部绑定，始终只有一份主 DOCX。（P1/P2/P4/P6） |
| AC2 | 生产 adapter 真实启动 tests-only 子进程，通过 word-preview-exec/v1 的 describe/render 成功和失败路径；损坏包、宏/DTD 各编码、非零退出、非法 PDF/PNG、路径/符号链接、超时终止/清理和预算负例拒绝。（P1/P2/P3） |
| AC3 | 普通预览失败后主 DOCX/receipt/字节不变且可内部下载，quality blocked、禁止批准和发布；metadata 插入、对象写入、确认及响应丢失不误完成。（P4/P6/P7） |
| AC4 | 自动重试、进程重启、A→B→重启→A、成功复用新 key 及同 key 异参均满足持久预算和幂等；单独重试不调用 MinerU/AI/renderer，也不增加 generation。（P5） |
| AC5 | 三 adapter 的 claim/finish 竞争、旧 lease/attempt/generation、取消/超时/归档/删除/published 拒绝；真实 file/SQLite 竞争与 fake MySQL 的证据明确区分。（P4/P5/P10） |
| AC6 | 跨租户/公司/owner、篡改或过期 Token、旧 manifest、部分/旧代文件拒绝；当前合法文件可下载，S3 TTL 测试不冒充实时撤销。（P6/P10） |
| AC7 | pending/warning/passed 基础质量经历失败→成功后分别恢复，未知或并发 blocker 保留；公式 fallback 与预览先后完成均不丢 warning，不把自身 blocked 误捕获为永久基础 blocker；不恢复批准/ready。（P8/P10） |
| AC8 | disabled、required、策略快照、clone/retry、历史无字段、legacy 无 receipt 兼容正确；默认不开生产，不改公开状态枚举、发布执行资格和前端推断规则。（P9/P10） |
| AC9 | 当前 direct 零 AI、原生表格、公式/图片认证、唯一 receipt、翻译批次、独立对象键和下载合同回归通过；OpenAPI 无意外漂移。（P10/全部不变量） |
| AC10 | 文档逐项区分目标集成、历史源测试、协议 adapter 可用与 production_ready；当前目标验证证据和生产待验项独立记录。（P1/P3/P10） |

## 规划结论和停止条件

已接受的 port/fake/生产 adapter 可完成范围内设计和离线验证，不需要本轮选择引擎或批准新系统依赖；生产启用另设门禁。当前无无法消解的产品/ADR 冲突，规划可评审，实施尚未授权。

出现以下任一情况停止：CON-103 状态或人工验收撤回；PRD/冻结决策/ADR 冲突；需要未批准的破坏性迁移、覆盖发布件或删除审计；必须改变模式、原生表格、下载/批准/发布规则；必要样本/外部系统/安全授权缺失且 fake/adapter 无法替代；必须新增未批准系统依赖且 port/fake 不能完成；为移植旧实现必须覆盖较新合同或引入后续任务。先修订规划评审，不以兼容兜底偷偷扩围。
