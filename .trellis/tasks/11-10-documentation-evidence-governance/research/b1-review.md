# B1 独立文档复核

日期：2026-11-10。依据：本任务 PRD、design revision 1、implement.md、check.jsonl 及其引用。复核范围为清单 `proposed_batch=B1` 的 10 份原文与新增的 `docs/engineering/documentation-governance.md`。

结论：**B1 文档候选通过独立复核，未发现需要修改的缺陷。** 本结论只覆盖下述文档合同和静态证据，不是产品、生产或历史运行结果的重新验收。

## Findings (fixed)

无。本复核未修改维护文档、业务源码或已有任务资料；仅新增本报告。

## Findings (not fixed)

无已确认而留待修复的问题。以下是按设计保留的证据边界，不属于本批缺陷：

- 45 项产品任务的 AC、实现、集成与人工接受对账属于 B2；B1 没有推进执行状态。
- Golden 原 run_dir、签字制品、真实 Word/Provider 和线上配置没有在本批读取或重跑；报告明确将其保留为历史声明。
- 文档责任人未确认，`owner: null` 符合合同。
- gap 的翻译执行协作者尚未提交，`last_verified_commit: null` 并指向工作区字节证据符合合同；相关源码变化后应刷新这部分证据。

## 独立复核依据与结果

| 检查维度 | 核对内容与结论 |
|---|---|
| 精确候选范围 | 阅读 10 份原文相对主会话实施前只读副本的完整差异与新增治理说明，不使用混有预存 dirty 的 HEAD 差异作为任务差异。11 份候选 SHA-256 均与实施交接表相同，复用检查的输入未变。 |
| 字段合同 | 四个字段、四种生命周期和五类事实与批准设计一致；导航和历史报告没有借当前 HEAD 或原 release 填写代码核验 SHA。所有未知 owner 保持 null。旧 frontmatter 字段只保留原值，不以追加元数据刷新日期或重定义原 status。 |
| Manifest | 精确差异仅在文件开头增加文档字段与说明，原业务正文保留；复用已通过的全对象比较结果，45 个 tasks、rules、status_values 与原有其他业务结构未变。未新增第二套任务状态或绕过依赖门。 |
| Docker 安装链 | 实际读取 dev/prod Dockerfile 与两份 Compose。两个 Dockerfile 均复制锁和 wheelhouse，使用 isolated/no-index/find-links/require-hashes/binary-only 参数。开发 API 构建与 API/Worker 运行固定 linux/amd64；API/Worker 的镜像引用符合开发默认值、生产必填的区别。文档没有把这些静态配置当作构建、拉取或线上生效证明。 |
| 非空核验提交 | `d45e46e1233c3f173fa1d738cf75b3ef7a393eb9` 可解析为完整 commit。Docker README 与 P0 部署说明引用的 Dockerfile/Compose 字节与该提交相同，核验范围明确限定静态输入。未外推未复核的制品来源、工具版本和运行环境。 |
| gap 历史范围 | 原 `e51e6ccd129f59d1b372dfc6907def1fd6bb5cd8`、2026-10-03 与 2026-11-06 局部复核均保留；其余条目的“当前/缺失”有统一历史边界。新增 CON-102 事实只说明阶段类型存在，未认定整项完成。 |
| table context | 实际读取 TableContextBuilder、DocumentIRTranslationService、config 与 main 接线。请求的 table_contexts 有实现入口，配置默认 False；候选同时写明默认关闭和未验证运行效果，TR-404 状态未改。 |
| 翻译调用位置 | execution.py 组合 TranslationBatchExecution；当前未跟踪的 translation_execution.py 调用 build_provider_request、validator.validate 和 fan-in validate_persisted。候选准确标记未提交工作区，不用源码符号存在替代真实翻译或语义验收。 |
| 历史 Golden 报告 | release `20d496e`、完整 commit、deployment、run `20260629T070506Z`、4 样本、admin/final_signoff 与原结果表保留。2026-06-02/03/24 的历史范围单列；0/4 人工质量与后续 4/4 的通过声明没有相互覆盖。新增当前流程链接与旧命令的历史适用边界一致。另用只读 Git 历史确认文末 layout facts 描述在 2026-06-03 已存在，日期标注有历史依据。 |
| 部署记录边界 | 三份部署文档区分仓库 Compose 配方、B02 前旧构建示例及 hostdzire 既有分层 override 记录；要求按实际文件清单核对，未把 2026-11-06/09 观察写成此次线上观察。 |
| 源证据身份 | 独立计算实施记录列出的 17 份源码/配置/脚本 SHA-256，全部匹配；与 HEAD 相同、已有未提交差异和未跟踪三类关系也与记录相符。静态查看脚本参数，没有执行发布或验收脚本。 |
| 消费方与 Spec | 定向搜索 scripts、.trellis/scripts、tests 未发现产品 Manifest 新顶层文档字段的业务消费方；这不证明仓库外没有消费者。本批遵循既有质量 Spec 的依赖说明与卫生边界，没有产生必须改写 Spec 的产品合同或实现变化。 |

## Verification

- 文档结构、重复键、字段类型/枚举、旧字段、Manifest 全对象、链接及锚点：**通过，复用实施记录中的 B1 定向检查**。selected=11、active=9、historical=2、errors=[]、既有断链=[]；已独立确认 11 份候选内容身份未变。
- 本批 12 文件卫生检查、跟踪文档 diff 检查和新增文档行尾检查：**通过，复用实施记录**，不重复运行。
- 已有 dirty/index 保护：**复用实施记录**，241 条既有 dirty 字节不变，另 4 条为获准文档变更；index 摘要保持。复核方没有修改这些输入。
- 本复核报告：**通过**，仅对报告自身检查行尾、链接和文件卫生；未扩大到全仓历史扫描。
- Lint：**不适用，未运行**；本批没有业务代码变化，任务明确只做文档检查。
- TypeCheck：**不适用，未运行**。
- Tests：**不适用，未运行应用测试**；未执行 build、CI、发布聚合器、Docker 或生产访问。
- Python 注释/docstring/运行输出：没有 Python 变更；本报告与新增文档说明使用中文。

本批完成后停止；后续批次由主会话另行派发。
