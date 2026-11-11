# 文档状态与实现证据治理设计

修订：1。状态：2026-11-10 用户已批准，按四批顺序实施。字段合同与范围未改变。

## 1. 边界与权威关系

沿用 `DOCUMENTATION-MANIFEST.md` 的职责划分。新增 `docs/engineering/documentation-governance.md` 解释文档生命周期、核验字段及维护方法；根 README、docs README 和权威关系清单链接到该说明，不建立第二套目录或任务执行状态。

纳入 134 份现有资料：docs 下 Markdown/YAML、根 README 和 DOCUMENTATION-MANIFEST、Docker README、trellis-bootstrap Markdown、tests/fixtures 的说明与验收模板。包括既有未跟踪的 `docs/dev/repository-hygiene.md`；追加字段前复核其最新内容和现有变更，保留其正文。另新增治理说明一份。

运行时 Prompt、模板/样本 Manifest、Docker Compose 和 OpenAPI JSON 属于运行输入或生成产物，不能注入本文字段。AGENTS、Skills、平台配置、Trellis Specs、任务历史和会话记录已有各自生命周期，本任务只引用，不批量改写。

## 2. 元数据合同

Markdown 在已有 YAML frontmatter 中追加字段；没有 frontmatter 的文档新增一个 frontmatter。两个 docs YAML Manifest 直接追加同名顶层字段，不插入 Markdown 分隔符，不改 schema_version、entries、tasks 等既有结构。实施前复核消费方；如果发现未知字段会被拒绝，先回到设计处理，不绕过合同。

```yaml
doc_status: active
last_verified_commit: null
owner: null
verification_scope: null
```

| 字段 | 合同 |
|---|---|
| doc_status | active、historical、superseded、draft 四选一；表示文档用途与维护阶段。保留原有 status，不混用其目标／任务含义。 |
| last_verified_commit | 完整 40 位提交 SHA 或 null；只能标识实际核验所依据的代码。文档最近编辑提交、当前 HEAD 和被引用的历史 release 都不能自动填入。 |
| owner | 已确认的责任团队／维护者标识字符串或 null；任务 assignee 不是所有文档的默认 owner。 |
| verification_scope | 非空说明字符串或 null；说明核验章节、事实种类、依据和未核验边界。非空 SHA 必须配非空范围；没有核验时两个核验字段均为 null。 |

既有 `doc_type`、`status`、`baseline_commit`、`last_reviewed`、`last_scanned`、slug、tags、component 等全部保持原始语义。不能把 baseline_commit 直接改名为 last_verified_commit；不能因追加元数据就刷新整个文档的复核日期。

## 3. 生命周期与证据

| 生命周期 | 用途 |
|---|---|
| active | 仍受维护和引用的说明、规范或目标设计；并不代表功能已实现。 |
| historical | 保留当时问题、调查或验收结论；正文指出时间、版本和适用范围。 |
| superseded | 已有明确替代文档；正文给出实际替代路径，保留历史引用入口。 |
| draft | 未冻结的设计、待确认方案或尚不能作为维护依据的草案。 |

逐份判断，不能用“文档较旧”“在 implementation 目录”“有目标能力”作自动迁移规则。已冻结且仍有效的目标设计可以是 active，原 status: target 或 scope-frozen 保留。

五类事实通过正文表格／说明与引用区分，不再新增一套全局功能状态字段：

1. 当前代码实现：指向真实 owner、调用入口和提交或工作区内容身份；静态存在不证明环境开关启用。
2. 文档声明通过：给出报告、原版本、环境、样本与实际验收范围；没有核看原始证据时明确为报告声明。
3. 计划能力：保留目标、任务 AC 与依赖；不当作当前 API／行为事实。
4. 历史问题：保留原判断基线；后来可能已修复，不能直接重做。
5. 当前仍存在的问题：有本次对应基线的差异、失败或反例；纯静态说明漂移可凭源文件对比成立，运行时缺陷须另有相应证据。

核验操作形成的事实先写入任务研究记录，再更新文档范围说明。未逐项核验的旧章节继续标注原历史基线。元数据只记录证据，不让一行 active 或 SHA 替代验收。

## 4. 版本与工作区

本次 HEAD 为 `d45e46e1233c3f173fa1d738cf75b3ef7a393eb9`，分支有大量既有变更。研究清单保存读取时每个文档的 SHA-256；建项前工作区基线在本地存档，保留当时未提交文件的内容身份和 index 条目摘要。该 SHA 不是候选内容全部已提交的证明。

若核验依赖的源码或配置不同于提交内容，last_verified_commit 保持 null，verification_scope 指向任务中使用相对路径和内容身份记录的工作区证据。不能用源码提交已知但依赖／配置未知的方式外推整链通过。纯静态文案对账不触发运行测试，也不填写运行验收通过。

## 5. 四批迁移

批次与路径的完整映射由 `research/document-inventory.json` 保存。四批共享同一字段合同与全量验收，不拆成重复任务；每批验证后复用不变输入的通过结果。

| 批次 | 现有数量 | 处理内容 |
|---|---:|---|
| B1 | 10 | 三个导航、Docker README、gap、产品任务 Manifest、Golden 验收报告、三份部署说明；另新增治理说明。先形成读者可见边界，修正已确认漂移。 |
| B2 | 21 | 产品、架构、合同、详细设计、工程策略、ADR 和剩余总计划；区分目标与现状。对 45 个产品任务形成只读 AC／实现／历史／验收对账表，保存在本任务研究目录。 |
| B3 | 51 | API 清单与说明、开发资料、runbook、剩余测试记录、夹具说明与验收模板；标明当前合同、历史报告和模板用途，逐份核验仍维护的命令。 |
| B4 | 52 | 独立任务提示词、合并阅读版及父任务模板；元数据和导语明确为执行辅助或模板，不替代 Manifest 和 AC。 |

B1 中的准确处理：

- Docker README 对照 dev/prod 两个 Dockerfile 更新直接声明、运行锁与 wheelhouse 的职责，不声明整镜像逐字节可复现或生产构建通过。
- Gap 保留 `e51e6ccd…` 原基线和 2026-11-06 局部复核；扩展阶段和 table context 只更新已核实的静态事实。其余条目明确是旧调查或未复核，不批量写成仍存在。
- Golden 报告定位为历史验收记录，保留 release 20d496e、run、样本和签字结论；执行步骤的当前入口链接到维护中的部署／验证说明，不将旧步骤认证为当前流程。
- 产品 Manifest 仅追加文档元数据与记录边界提示。tasks 中 status、依赖、路径和历史 notes 不在治理实施中自动改动；已发现的 CON-102／TR-404 差异先进入对账表。
- 部署文档只核对仓库内配置与文字；未读取线上真实配置，不能认定在线设置已生效。

## 6. 既有工作与协作

B01 已有局部修正文案；卫生任务已有路径治理；B06 表格上下文默认关闭；当前翻译批次提取仍会修改执行器。这些记录各自保留其验证边界。实施前重新检查相关路径和内容身份，协调重叠 owner；出现变化先更新核验范围，不回滚他人修改。

未来实施按 Trellis 派发单个 implement 子代理顺序处理当前批次，赋予该批次文档所有权；检查子代理只读复核候选差异及必要证据。主会话负责授权边界、任务记录、跨批验收和最终状态，不并行让多个代理修改导航／Manifest。不使用完成消息代替实际验证。

## 7. 取舍、失败与回退

不统一替换原 status，避免破坏现有目标和任务语义；不引入新依赖、生成站点或常驻脚本。owner 与未核验 SHA 可为 null，比补造团队／提交更准确。缺证据时明确留空及记录范围，不强行完成技术验收。

文件变动超出本批范围、历史报告原结论丢失、JSON/YAML 不可解析、字段消费者拒绝或任务状态被意外修改时，停止该批迁移并修正。仅反向应用本任务拥有的精确差异；对原本脏文件不能以整个文件覆盖回退，不使用 reset、checkout 或 broad clean。归档、会话记账和提交不在本轮授权中。
