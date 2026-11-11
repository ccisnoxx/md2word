# B1 文档实施与核验记录

日期：2026-11-10。批准依据：本任务 design revision 1；本批仅迁移 10 份既有维护文档，另新增治理说明。主会话维护清单和任务三件套，本记录不修改其内容。

## 核验边界

- 核验时 HEAD：`d45e46e1233c3f173fa1d738cf75b3ef7a393eb9`；它仅为 Git 定位，不代表整个脏工作区。
- B1 原文均与建项清单和实施前只读副本逐字节一致；在此基础上追加字段和精确正文差异。
- 全文阅读不等于每项能力验收：本批只核对下表列出的源码、配置、导航和报告声明，未重新验证历史运行制品、Word、Provider、数据库、队列或线上状态。
- 未确认维护责任人，所有 owner 使用 null；admin 签字角色及任务 assignee 不转成文档 owner。
- Docker README 与 P0 部署说明只对已提交的构建/编排输入做静态核对，填写该提交及局部范围；依赖未提交源码的 gap 使用 null 和下列工作区身份。导航、规则和历史报告不冒称完成代码核验，核验 SHA 保持 null。
- 未执行应用测试、lint/typecheck、build、CI、发布聚合器、Docker、生产访问、依赖安装、暂存、提交、push、archive 或 add_session。

## 逐份用途与事实范围

| 文档 | 生命周期 | 本批正文核验与处理 | 未验证边界 |
|---|---|---|---|
| `README.md` | active | 导航、目标/现状/验收边界；Golden 入口标明历史版本 | 不核验整条 API、P1/P2 或发布命令运行结果 |
| `DOCUMENTATION-MANIFEST.md` | active | 原权威关系、治理说明入口及历史资料用途 | 不据目录宣称能力已实现 |
| `docs/README.md` | active | 导航、文档生命周期与目标/现状关系 | 不逐项认证所有链接文档的正文 |
| `docker/README.md` | active | 对照两个 Dockerfile 和 Compose 修正锁/wheelhouse 与共用镜像说明 | 不 build/pull/up，不核实在线 digest 或镜像身份 |
| `docs/deploy/p0-docker-deployment.md` | active | 构建输入、pip 安装参数、Compose 镜像/平台声明；链接适用的生产方式 | 线上轮换、工具版本/制品来源声明及验收未重跑 |
| `docs/deploy/hostdzire-dmit-md2word.md` | active | 仓库 Compose 与正文中的分层 override 记录有别；历史日期/范围保留 | 2026-11-06/09 线上结论仅为既有记录，本批未读取线上配置 |
| `docs/deploy/online-first-validation-workflow.md` | active | 对照维护入口标明旧构建/回滚步骤边界；静态核对脚本参数 | SSH/服务/发布未执行；历史主机环境和任务回填位置不视为当前观察 |
| `docs/implementation/codex-task-manifest.yaml` | active | 仅追加顶层文档字段和注释；任务对象按实施前全文保持 | 45 项 AC 对账留待 B2，CON-102/TR-404 不改状态 |
| `docs/implementation/current-gap-analysis.md` | historical | 原历史基线和 2026-11-06 局部结论保留；补扩展阶段、table context 与当前翻译入口静态事实 | 其余旧判断未全面复核；静态接入不证明启用、质量、AC 或人工验收 |
| `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` | historical | 2026-06-29 release/run/四样本/签字为报告声明；2026-06-02/03/24 分别标明历史范围 | 未核看原 run_dir、签字原件或重新运行；不能推断当前 HEAD/线上通过 |
| `docs/engineering/documentation-governance.md` | active | 按批准合同解释字段、四种生命周期、五类事实及维护方法 | 元数据不代替代码/运行验收，不另建任务执行状态 |

## 本批确认的事实

1. **当前静态说明漂移**：两套 Dockerfile 都 COPY 运行锁和 wheelhouse，使用离线/hash/binary-only pip 参数；原 Docker README “Python 依赖只来自 requirements.txt”不准确。requirements.txt 仍是直接声明入口。
2. **当前静态实现**：models.py 包含 translating、translation_validating、quality_checking 等阶段；仅证明类型存在，不能把 CON-102 整项判为 done。
3. **当前静态实现**：DocumentIRTranslationService 将 TableContextBuilder 产生的上下文放入 table_contexts；配置默认关闭，app/main.py 传入开关。没有观察线上启用和语义质量，TR-404 状态不变。
4. **当前工作区静态调用**：批次 Provider 准备/validate 和 fan-in validate_persisted 已在未提交的 translation_execution.py；旧说明仅指 execution.py 已不足定位该范围。
5. **历史报告声明**：Golden 报告记录 release 20d496e、commit 20d496ed1df0c1d3eee94c0e6dfac0c0e6653ed3、deployment hostdzire-20260629T070215Z-20d496e、run 20260629T070506Z、4/4 与 admin final_signoff。保留原数据与结果，不把引用转成新核验 SHA。
6. **维护流程的历史边界**：online-first 中 latest 与旧 build/回滚流程已被 P0 部署说明的 B02 输入及 hostdzire 的分层 override 记录限定；标清入口，不声称本批复核了真实生产编排。

## 读取的源码与配置内容身份

下表 SHA-256 对应本批实际读取字节；“与 HEAD 相同”只比较该文件，不外推未读取依赖或运行环境。

| 相对路径 | SHA-256 | 与 HEAD 的关系 | 读取用途 |
|---|---|---|---|
| `docker/dev/Dockerfile` | `5d1605d04ecca5f06c5ac58b31febd19a4b8dd071de956222104ec001814fe55` | 相同 | 开发镜像锁、wheelhouse、pip 参数与基础镜像常量 |
| `docker/prod/Dockerfile` | `f6b81b5356d484bf5ae7567523a66c9c92b00a509bdd0580ee98e38adf712ca0` | 相同 | 生产镜像锁、wheelhouse、pip 参数与代码复制范围 |
| `docker/dev/docker-compose.yml` | `97a7b4d3805675a711cb48042f60603497b46d271bfef32bdd485eb6e0a7348f` | 相同 | 开发 API/Worker 镜像与 linux/amd64 声明 |
| `docker/prod/docker-compose.yml` | `d413ff481b02da9cb46352a9a8a546a6dab98999345d973ad7efeec52f63b098` | 相同 | 生产 API/Worker 共用镜像、服务、volume 与账号挂载 |
| `requirements.txt` | `fb15812d47bbaa988d1b7007906eec453bae37aba4871f9160c4faa5d2db2540` | 相同 | 直接依赖声明职责 |
| `requirements/locks/cp311-linux-amd64.txt` | `09676451b4382e8e443668a34be93e456345d39db2e06117205aa1056e623526` | 相同 | 运行依赖版本/hash 锁文件身份；未重新解析或安装 |
| `app/domains/document_jobs/models.py` | `98e3fcb618f402f40472b7bdba94edd677d915f11c0055e1407f3edc0e7323ca` | 相同 | DocumentJobStage 中扩展阶段的静态类型定义 |
| `app/domains/translation/document_ir_translator.py` | `8874aab75f3d63134af339e6ace06447e1360e35627b02438f95d209064aff69` | 相同 | table context 开关、build_provider_request、prepare/validate 调用 |
| `app/domains/translation/table_context.py` | `9195fb0b948cf0e9a44edda71e7367b1059dbbcab6b4c438ddbb11c1c19f7e80` | 相同 | TableContextBuilder 读取既有网格的输入上下文构造 |
| `app/core/config.py` | `db98b9432df1366491d57c94e3d3167f044c147a1ae9195d4b5f446aef38d5a8` | 相同 | translation_table_context_enabled 默认 False |
| `app/main.py` | `39511744c95c4a70aaccf3e4e65214499b346374739ab1bef269a85f4d28379a` | 已有未提交差异 | 配置向 DocumentIRTranslationService 的开关传递 |
| `app/domains/document_jobs/execution.py` | `8d662da91d0ebad7b5f403c8a21f09551cf1323c028b04c178e9679eb3b6f27a` | 已有未提交差异 | 翻译执行协作者的组合入口 |
| `app/domains/document_jobs/translation_execution.py` | `dcdedf56816beb42b281a3828ed61d385819b65fde8f608e67a44572bd153865` | 未跟踪 | 当前工作区批次准备、validate 与 fan-in validate_persisted 调用 |
| `scripts/ops/check_release.py` | `31c96e03808c7542a526430188e546de0e7836e90329fb4e1dbb84c2419273f0` | 相同 | 静态核对 runtime/preflight 参数入口；没有执行 |
| `scripts/ops/run_golden_sample_regression.py` | `e7f40687fc80d04153883cdbadc24b8ecd0de3437bae228a412c335091d41621` | 相同 | 静态核对签字参数及 p0_release_ready 计算入口；没有执行 |
| `scripts/ops/run_p1_translation_regression.py` | `b90f1bd0eaa4f8a1b1892b24d4133136b01a42cbaae8e6ea8441ef3c0d39b7c8` | 相同 | 静态核对 formal 与签字参数入口；没有执行 |
| `scripts/ops/run_p2_online_gate.py` | `eb3f6d030f6d10c6ebd52c5dc1397cfe0b31aa0dc0943a74738a28dd2f845ba8` | 相同 | 静态核对 sync-acceptance 参数入口；没有执行 |

## B1 文档实施前内容身份

| 相对路径 | SHA-256 |
|---|---|
| `DOCUMENTATION-MANIFEST.md` | `0ed1cdb46f16bb90b47cb58f4f0c8266f5ca59ce1fdcffefc1cb39374ef0b0af` |
| `README.md` | `a19626a1912481c75ccd31ee624fd158d5efa339b3002ddf667b9f9abd49a28d` |
| `docker/README.md` | `9094a9d26e6ebb4de5126d1bce81819d03f55f2fa4bb2d39ce83a23cbc4d7091` |
| `docs/README.md` | `bffc01f46dff8ad76fcfdc15ff2e2f56b61f4dcddd4a8f838f3a72b92f984b5f` |
| `docs/deploy/hostdzire-dmit-md2word.md` | `c7aae9f31265a7b86ba3bb13e1767915cdf7ea55ba222a6445321f191c2534ca` |
| `docs/deploy/online-first-validation-workflow.md` | `675d8423485d6c80069d956ceea0d4e0478c2740d99b65fbb2917af3076d7fb2` |
| `docs/deploy/p0-docker-deployment.md` | `2e9fcdfdfa78a9ee44d2b3f7ebc0a0d96bf89d374ceb45d1a2293f664f7ea96d` |
| `docs/implementation/codex-task-manifest.yaml` | `4330b8ad42b2f8911c67a787aac667614d11f8a17b8709639960987b73d5e300` |
| `docs/implementation/current-gap-analysis.md` | `923c0ff2d18d08ad4fd4c344492c7615fa1aac575d337311e54a47da48a0a78d` |
| `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` | `40899129a42a094543f506189a6c0f466d41215c2b6602c212c95e17fe26baeb` |

## 文档检查

| 检查 | 实际结果 |
|---|---|
| 一次性文档检查器 | 复用主会话提供的 `validate_docs.py --batch B1`，通过；检查 11 份，active=9、historical=2，errors=[]，既有断链=[]。 |
| YAML/frontmatter 与旧字段 | 重复键、字段类型/枚举、完整提交解析、原 frontmatter 字段值检查通过；未刷新旧 status/baseline_commit/last_reviewed。 |
| Manifest 保持 | 原 YAML 全部业务结构比较通过，包括 45 个 tasks 对象、rules、status_values；另确认新文件以实施前原始字节完整结尾，仅新增前缀字段和说明。 |
| 链接与锚点 | 所有受影响 Markdown 的相对链接与新增标题锚点检查通过；未发现本批既有断链。 |
| 精确 diff | 已阅读 10 份原文相对实施前副本的完整差异与新增治理说明；9 份原 Markdown 有获准正文变更，Manifest 原业务正文逐字节保留。 |
| 文本格式 | `git diff --check` 对本批跟踪路径通过；检查器覆盖新增治理说明的行尾空白。 |
| 文件卫生 | 既有检查器 `--files` 只检查 11 份维护文档和本记录，共 12 份，内容跳过 0、规则命中 0；未启动历史扫描或修改扫描规则。 |
| 输入身份 | 本批读取的 17 份源码/配置/脚本字节在检查时均仍匹配上表 SHA-256。 |
| 工作区保护 | 建项前 245 条 dirty 记录中 241 条内容身份不变；其余 4 条仅为获准修改的 hostdzire、online-first、产品 Manifest、Golden 报告。范围外已有 dirty 变化为 0。 |
| 暂存区 | `git ls-files --stage -z` 摘要仍为 `1552991ae88d79c5b5fbc5c839b62cc3ea57eb7f7c800c455dea435c64344e31`，与建项前相同。 |

本批无已发现的文档检查阻塞。未运行应用/生产验收；这些结果只证明上述文档性质。独立 Trellis check 由主会话另行派发，尚不能据本实施记录宣称已完成。

## 本批交接与未决项

- 本实施代理仅修改 11 份维护文档和本记录；清单、三件套和 task.json 归主会话维护。新增治理说明需由主会话补入清单，不在此自行改写快照。
- B2 继续对账 45 个任务；本批不把 CON-102、TR-404 或其他任务推进到 done，也不处理历史测试。
- gap 引用当前未提交翻译协作者的内容身份；其源文件后续变化时，需要刷新相应局部证据，不能仅沿用当前 HEAD。
- 生产拓扑、分层 override 和原 Golden run/签字仍是既有记录；本批未实际观察。没有已确认的文档责任人，owner=null 保留待确认。
- 未修改业务 Python，因此没有新增或改写 Python 注释/docstring/运行输出；新增文档和 YAML 说明均使用中文。

## 交接时维护文档内容身份

下表固定本批候选字节，供主会话独立检查；本记录本身不生成自引用 hash。

| 相对路径 | SHA-256 |
|---|---|
| `DOCUMENTATION-MANIFEST.md` | `440414f945dab789db7f17f038afc1c7fb42b5a5f7ee26a57e4900bea2b9a5a0` |
| `README.md` | `bc375525922ff6dcb41d7fa5dba060b35aa5a62d20dbab423c0a30d0bf06044b` |
| `docker/README.md` | `c757cd91954d1a9bfa7a7c7745cac99427f7a806a731ce6445df8ca4d8c42026` |
| `docs/README.md` | `8d1c3247587b275529a9d5304bcc8cfe03f17b429c0a4f4616df9977c41e177c` |
| `docs/deploy/hostdzire-dmit-md2word.md` | `e378247f6699b22510698bb166b432bd576d2348a92e938380cd733aa9167a0b` |
| `docs/deploy/online-first-validation-workflow.md` | `04c8d01d49221e3db8e30c714cdbe7c91563f6966c2d20110928a071b6adda92` |
| `docs/deploy/p0-docker-deployment.md` | `e29a2e56974f67a3fd78bbc23404399f21e96c3a77a15ae6259d8049376ced9b` |
| `docs/implementation/codex-task-manifest.yaml` | `62bbde5feb197ed99e5ccfa14d4d7e56cc5088399a4fa9347c88ae3874a64b7f` |
| `docs/implementation/current-gap-analysis.md` | `734bb2e8457b624ffdf0d0620f8d0c1d9f7ee763cefc4f00d26dc95dc79e433b` |
| `docs/testing/pdf-to-word-golden-sample-acceptance-report.md` | `93ec454873a56a46c4870676e01efda02dcaaf04866a11e533a5986395f20389` |
| `docs/engineering/documentation-governance.md` | `17f91184382cb4a00f82db1b58e7c4c04ddac1123547f0f54a84d97bcc5faed9` |
