# B02 实施与定向验收计划（已授权）

## 当前授权与启动条件

2026-11-06 用户明确确认最新方案，允许在 hostdzire 独立临时目录和容器内修改任务范围依赖配置、生成锁、必要镜像拉取/构建与下列定向验收。禁止部署、CI、提交、推送及生产服务/卷/数据库变更。

- [x] 独立任务已创建，实施状态为 in_progress；本 worktree 复制任务材料，不修改 active task 指针。
- [x] 核实仓库、本机和远端目标，记录实际镜像身份、daemon/builder、离线源与包元数据。
- [x] 完成三件套和定向验收设计。
- [x] 用户审阅最新方案并批准实施。
- [x] 方案 A 的 hostdzire 任务目录、`md2word-b02-` 临时容器、固定工具准备、digest 拉取、A/B 安装、仅 A 四测试及一次候选构建均已授权。
- [x] 用户授权通过官方 PyPI JSON API 核实并仅补充 Pillow 12.2.0 目标兼容 wheel；原运行 wheel 与 pip 工具分开，生产 wheelhouse 不变。
- [x] 实施前复核来源及隔离条件；仅版本/来源/范围发生实质变化时更新方案并确认。

## 顺序与停止点

1. 复核 HEAD 为 828e1d9d656bf266cba7bba0ed23a62c550db15c 及 research 采样时间。记录 hostdzire 开始时磁盘空间、任务资源清单和 `md2word-p0-*` 状态/启动时间；在 `${B02_REMOTE_DIR}` 创建独立任务目录，若存在则加后缀。生产漂移只刷新有关事实，不覆盖原工作区 B03/夹具改动。不把线上镜像当成当前源码构建基线。
2. 先执行下述已授权 Pillow 单包补全：查询官方 PyPI JSON API 的固定版本文件列表/hash，唯一选定 CPython 3.11 / Linux x86_64 / 目标 glibc 兼容 manylinux wheel，仅下载此运行包到 `${B02_REMOTE_DIR}` 的独立 wheelhouse；与原 56 个运行 wheel 合并并核实 57 项集合，pip 单列，生产 `/opt/pub2-wheels` 不变。随后处理 provenance 报告：必须逐项取得官方制品/hash 对应；不可获取和不匹配分别记录。不得将不匹配解释为自动允许升级，也不得将已装包来源默认为可信。复用已核实的 MySQL/Redis 官方 digest 与目标 Python 3.11.18-slim-trixie manifest；缓存 Python 是 3.11.15，禁止误用。当前应用历史父镜像链未完整还原，使用新候选而非声称重现其全部系统层。此门未过，不写最终可信锁、不拉镜像。
3. 固定生成器（候选 uv 0.11.19）与安装器，在与 CPython 3.11.18 / Debian 13 / amd64 匹配的 `${B02_REMOTE_DIR}` 与 `md2word-b02-` 前缀临时容器中准备同一经过核对的 wheel 集合。不得在生产容器安装工具，不启动 API、Worker、MySQL/Redis 服务，不挂载生产卷。
4. 将现有 PyMySQL 声明补 rsa extra；用目标 57 项运行候选的已核实版本约束生成完整 hash 锁。根声明仍为 15 项，额外三包由 rsa extra 引入，不将 pip/setuptools/wheel 混为业务根依赖。实际闭包与候选集合差异必须解释。
5. 固定相同输入和独立解析缓存做 A/B 两次解析，比较规范化包名/版本/marker/hash；排除生成时间与路径注释。A/B 各自独立干净环境严格安装、保存报告并 pip check，比较运行闭包版本集合。只在 A 中运行 DOCX 定向测试，B 不重复业务测试。
6. 接入 dev/prod Dockerfile 的标准锁与离线 wheelhouse 输入，消除无版本 pip 升级；固定经核实镜像引用。只构建候选一次，API/Worker 使用同一产物身份。检查非 root、密码、回环绑定、healthcheck、Poppler 等配置合同保持。MySQL/Redis 不启动，仅检查引用/manifest。
7. 更新对应部署/runbook/quality-guidelines 描述；检查最终精确差异与既有改动 hash，独立只读复核实际发布输入变更的剩余风险。汇总 AC01–AC06、AC-R1/AC-R2，记录结束时目录/容器/镜像/空间清单并比较 `md2word-p0-*` 状态/启动时间；扫描新增改动文件的敏感标识，保留未验证项；不部署、不提交、不推送。

## 解析/安装命令模板

实施前将下列任务专用变量写入执行记录：B02_UV 是固定生成器绝对路径；B02_PYTHON 是干净目标解释器；B02_WHEELS 是已核实的只读 wheelhouse；B02_CONSTRAINTS 是从已审阅目标版本生成的任务约束；B02_LOCK/B02_REPORT/B02_CACHE 是本次 A 或 B 的独立输出路径。所有任务输出和缓存位于 `${B02_REMOTE_DIR}` 或前缀临时容器；变量具体值与执行结果由执行记录确认。仓库文档不记录远端实际绝对路径。

```bash
"$B02_UV" --no-config --cache-dir "$B02_CACHE" pip compile requirements.txt \
  --constraints "$B02_CONSTRAINTS" --python "$B02_PYTHON" \
  --no-index --find-links "$B02_WHEELS" --no-build --generate-hashes \
  --output-file "$B02_LOCK"
"$B02_PYTHON" -m pip --isolated install --no-index --find-links "$B02_WHEELS" \
  --require-hashes --only-binary=:all: --report "$B02_REPORT" -r "$B02_LOCK"
"$B02_PYTHON" -m pip check
```

执行前清除/核对会改变解析的 UV_*、PIP_* 配置；不能只因 --no-config 就假设环境变量不生效。不在当前 venv 执行同步/卸载。不使用 --no-deps 掩盖闭包遗漏，不启用 sdist 自动构建。来源可用性、hash 校验或候选依赖冲突失败时先诊断，禁止无变更反复重试。

## 定向测试（已授权，仅隔离目标 A 执行）

```bash
"$B02_PYTHON" -m unittest \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_preserves_html_table_spans_and_annotations \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_fraction_omml_in_formula_and_table_cells \
  tests.test_document_ir_word_renderer_layout.DocumentIRWordRendererLayoutTests.test_render_to_bytes_writes_heading_list_and_formula_ooxml_semantics \
  tests.test_formal_mineru_render_evidence.FormalMinerURenderEvidenceTests.test_formal_conversion_returns_bound_v2_evidence
```

四个用例分别覆盖合并表格/表注、OMML、标题列表与公式、正式内容和同次产物锚点/证据绑定，使用真实 python-docx。测试入口此前仅通过 AST 静态定位，是否通过以本次执行证据为准。假对象 characterization 不充当兼容证明。

rsa extra 的最小检查是已安装 PyMySQL 元数据声明、cryptography/cffi/pycparser 三包及 hash 与候选对应，外加 pip check；不以此宣称真实 MySQL RSA 握手通过，也不为此扩张到数据库服务启动。根声明守卫解析支持 extras 已静态确认；若守卫实际逻辑不变，不为单行 extras 另写实现镜像式测试。

若实际 Python/python-docx/lxml 或其他渲染依赖版本必须变化，先审批版本差异，再对上述固定样本补前后规范化 XML 语义投影：文本/段落顺序、gridSpan/vMerge、OMML、书签名称/关系及每次自身证据绑定；不比较跨次 ZIP 原始 hash。保持同次 DOCX hash 与证据严格相等。无版本变化时复用既有预期断言，不新增通用比较框架。

## 任务文档检查

仅执行 task.py validate、JSON/JSONL/引用存在、测试名称 AST 定位、文档空白、Git 范围和起始改动 hash 对账。这些只验证任务材料；四项应用测试及候选验收按以上授权范围另行记录，不能与文档检查混同。

禁止 unittest discover、check_release、run_p2_online_gate、完整前端测试/构建、服务启动和供应商调用。相关输入未变时复用有效成功证据，不因收尾或切换 worktree 重跑。失败仅修本次直接问题，历史夹具问题单列。

## 历史停止记录（恢复授权前）

实施前只读复核发现：离线目录位于 `md2word-p0-api-1` 容器内，宿主未发现同路径目录；57 个 wheel 包含工具 pip 26.2.2，却缺少运行必需的 Pillow 12.2.0。候选运行集合为 54 项闭包加 rsa 三项，共 57 项，因此文件数相同不能证明运行闭包完整。历史 57/57 文件与官方 PyPI hash 匹配事实仍有效，当前问题是缺少所需制品，并非已存在制品来源不匹配。

当时在来源/完整性门停止：截至该停止点，尚无远端写入、任务目录创建、临时容器、镜像拉取、解析安装、应用测试或候选构建。任务保持 in_progress，当时执行状态为 blocked。此段为历史记录；当前恢复授权见下节，实际执行结果以 `research/execution-preflight.json` 与 `research/execution-report.md` 等新证据为准，不得将历史元数据观察当作本轮执行通过。

## Pillow 单包恢复授权（已执行）

用户已授权解除上述缺失制品阻塞：通过官方 PyPI JSON API 获取 Pillow 12.2.0 发布文件列表与 SHA-256，唯一选择兼容 CPython 3.11、Linux x86_64 和目标 glibc 的 manylinux wheel，只补充下载这一个运行包。在 hostdzire 新任务目录 `${B02_REMOTE_DIR}` 的独立 wheelhouse 中，将该制品与原有 56 个运行 wheel 组合为 57 项运行集合；pip 工具单列，不修改生产容器内的 `/opt/pub2-wheels`。

恢复状态为 in_progress，表示已获准执行补全流程，不表示 Pillow 已下载或来源/完整性门已通过。先核实官方文件身份、目标兼容性、实际下载 hash 及完整运行集合，再继续原方案 A 的 A/B 独立解析安装、仅 A 四项定向 DOCX 测试和一次候选构建。其他缺失、来源/hash/版本不一致或不能唯一确定兼容制品时仍停止，不扩大运行包下载范围，不切换来源或升级版本。隔离、生产保护、禁止部署/CI/提交/推送及 AC-R1/AC-R2 继续适用。

## 本次执行结果

Pillow 官方单包补齐、57 项运行依赖的 A/B 独立解析安装与 pip check、仅 A 的四个 DOCX 用例、一次候选构建及 API/Worker 产物身份核对均已完成。远端任务资源保留，生产容器状态及原始 wheelhouse 未变；没有部署、提交或推送。详见 [执行报告](research/execution-report.md) 与 [验收记录](research/acceptance.json)，这些是执行方报告，不代替任务设计方验收。
