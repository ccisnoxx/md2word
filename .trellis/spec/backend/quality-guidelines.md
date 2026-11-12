# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

### Word 输出专项合同

- 正式 MinerU→DocumentIR→Word 的输入、分页、分栏、表格、图片、字段、公式、样式优先级和专项质量门禁只由 [Word 生成规则](./word-generation-rules.md) 定义；本文不复制具体输出行为。
- 修改该链路时，先按规则 ID 核对唯一 owner、冲突矩阵、自动测试和样本证据，再应用本文件的通用测试与评审纪律。

### Datasheet 指标复算

- `scripts/ops/datasheet_quality_metrics.py` 以 `datasheet-quality-observations/v1` 的固定计划项计算七组指标。原生表格采集按 Word 实物一对一计分，源 Grid 差异留在原始观测中供定位。缺产物的计划项仍进入已标注的比率分母。
- `datasheet-quality-baseline/v1` 指定独立运行及各自的原始观测，输出报告逐份保留指纹和原版计算结果。人工回填使用独立文件，按计划项、成功且可打开的首次 DOCX 与审核轮次的产物指纹校验，原观测保留。单次历史复算继续使用原格式。
- `scripts/ops/run_golden_sample_regression.py` 从同一份 manifest 字节固定计划并计算指纹，在本次目录写 `observations.json` 和 `metrics.json`。成功指标以终态、对应主 DOCX 的授权和下载、实际打开为据。成功延迟结束于授权时点，失败和超时按失败观测时点。费用凭据与已验证的任务 ID、代次匹配才纳入，缺失或无效费用留缺测原因。
- 指标定义、版本字段和复算入口见[任务指标合同](../../tasks/11-11-datasheet-quality-baseline-contracts/metrics-implementation.md)。

### 已发布模板 seed 不可变性

- manifest 已登记并进入生产的模板版本，其版本号、资源路径和文件字节不可原地修改；新增可选 schema 字段应依靠模型默认值兼容旧 YAML，需要新的非默认内容时创建新版本。
- 每个 published bundled seed 都必须有固定 SHA-256 回归；当前 `default@2` 的 `datasheet_template_v2.yaml` 固定为 `132d0bb76e71c807912031199e894dfc0e3d50bd7534180f8ceaba7a5fa20b4d`。发布门禁不得只锁定 v1 而遗漏当前默认版本。
- hash 不匹配必须继续失败关闭；不得更新生产数据库 hash、放松读取校验或增加备用路径来掩盖 seed 被改写。

### 运行时依赖声明

- `requirements.txt` 是直接依赖声明入口；`app/` 中任何第三方导入（含函数内延迟导入）必须在其中直接声明，不能依赖本地 venv 里被其他包间接带入的版本。`tests/test_runtime_dependency_declarations.py` 是该合同的守卫，传递依赖或有意可选依赖只能进入其白名单并写明父依赖或降级行为。
- dev/prod 镜像共同消费 `requirements/locks/cp311-linux-amd64.txt` 完整版本/hash 锁与经官方 PyPI 文件身份对账的 `requirements/wheels/`，仅覆盖 CPython 3.11.18 / Debian 13 trixie / linux/amd64。根声明或目标版本变更须同步重新解析并核对闭包与制品来源；锁内的传递依赖不能替代根声明。首版保留 57 项运行依赖及 `PyMySQL[rsa]` 能力，不隐含升级或降级。
- 安装须显式 `--isolated --no-index --find-links --require-hashes --only-binary=:all:`，缺 wheel、来源/hash 不符或解析冲突时停止；不得自动回退索引或 sdist。A/B 干净 venv 只有 pip 24.0、setuptools 79.0.1，未安装 wheel；候选镜像保留固定 Python digest 自带的全局工具 pip 24.0、setuptools 79.0.1、wheel 0.46.3。两种环境均使用 pip 24.0 安装，工具不计入运行锁，不执行无版本 pip 升级。来源与构建准备见 [Docker 部署说明](../../../docs/deploy/p0-docker-deployment.md#依赖锁与构建输入)。
- API/Worker 共用 `MD2WORD_IMAGE`：生产必填，开发默认 `md2word-dev:local` 并允许同名变量覆盖；构建一次后复用并核对实际 image ID。开发 API 构建与 API/Worker 运行均固定 `linux/amd64`，Apple Silicon 使用仿真，不扩展锁的平台范围。Python/MySQL/Redis 使用已核实的官方 digest。apt/Poppler 系统包未锁快照，依赖锁与镜像身份不等于整镜像逐字节可复现，也不能替代真实 Word 客户端或生产验收。
- 系统工具（当前为 Poppler `pdfinfo`/`pdftoppm`）由 `docker/prod`、`docker/dev` Dockerfile 安装，并在 readiness 中暴露可用性（`pdf_crop_tools_available`，缺失为非阻断 warning `pdf_crop_tools_missing`）。
- 线上 hostdzire 镜像经仓库外固定发布包增量构建，不能作为仓库依赖完整的证据；验证仓库可复现性须用仓库 Dockerfile 构建。

---

## Testing Requirements

### 仓库卫生与原生 Git 提交检查

#### 1. 范围与触发

修改仓库卫生规则、Git 钩子、个人环境路径或扫描例外时应用本合同。使用方法和精确例外理由见 [仓库卫生说明](../../../docs/dev/repository-hygiene.md)，规则实现由 `scripts/ops/check_repository_hygiene.py` 与 `.gitleaks.toml` 各自维护。

#### 2. 命令入口

- `python3 scripts/ops/check_repository_hygiene.py --staged` 检查准备提交的路径和完整 index 内容。
- `python3 scripts/ops/check_repository_hygiene.py --tracked` 检查当前跟踪工作树；新增候选文件通过同一检查器的显式文件入口检查。
- `.githooks/pre-commit` 串行运行卫生检查与固定版本 Gitleaks 的暂存扫描；当前仓库使用 `git config --local core.hooksPath .githooks` 激活。

#### 3. 数据与隐私合同

Git 路径用 NUL 分隔，暂存内容按 index 对象读取；不得用工作树替代暂存区，也不得 stash、自动暂存或改变用户文件。检查器不得依赖业务 runtime。拒绝 `.tmp`、真实用户目录绝对路径、未声明 RFC1918 地址和新 secrets；输出只保留相对定位、规则和中文修复提示，不回显敏感原值。

合法部署地址的卫生例外必须限定精确文件、规则、内容指纹和用途；secrets 误报仅允许已核实文件中的特定校验和条目形状，不得豁免整个任务/工具目录或所有十六进制值。脱敏历史日志时保留运行结论，明确标注路径已改写，不将其作为未修改的原始字节证据。

#### 4. 验证与错误矩阵

| 输入或状态 | 结果 |
|---|---|
| 暂存违规、工作树已修复 | 必须拒绝提交。 |
| 暂存干净、工作树有额外违规 | 只按暂存内容判断，不改工作树。 |
| 初始提交、删除或路径含空格 | 按 Git index 真实语义处理。 |
| Git 读取失败、Gitleaks 缺失或版本不符 | 明确非零退出，不能作为空命中通过。 |
| 已确认校验和例外文件新增 credential 字段 | 必须继续拒绝。 |

#### 5. 正常、基线与拒绝案例

- 正常：使用 `${PROJECT_ROOT}` 等明确变量，暂存文件不携带本机路径；必要部署配置按精确例外保留。
- 基线：历史扫描是独立证据，不能在每次提交时重跑，也不能将未确认历史凭证标记为安全。
- 拒绝：仅修改工作树来隐藏仍在 index 中的凭证，或因为缺扫描器而跳过检测。

#### 6. 必要测试

`tests.test_repository_hygiene` 用独立临时 Git 仓库验证规则、部分暂存、初始提交、删除、重命名、空格路径、index 不变、错误脱敏及精确例外边界。沙盒默认路径变更只运行直接配置测试与受影响的既有审计/迁移测试；不因此扩展为全仓回归或发布门禁。

#### 7. 错误与正确做法

错误：对 `git diff --cached --name-only` 的路径直接读取工作树文件；部分暂存时会检查错误版本。

正确：用 NUL 接口枚举 index 路径并按对象读取完整暂存 blob，检查结束后保持 index 与工作树不变。安全扫描完整跟踪树时不得依赖 `git archive`，因为 `export-ignore` 会排除任务与工具目录；使用完整 Git 对象或显式跟踪文件快照。

### API 快照与前端动作契约

- 后端接口或响应模型变化时，使用 `scripts/ops/export_openapi.py` 同步 `docs/api/openapi.json`；快照检查必须比较当前生成结果，不能以历史部署快照替代或豁免差异。
- `DocumentJobActionId`、前端动作类型与 `check_release.py` 的静态契约检查应同步维护。`publish` 和 `new_generation` 在兼容旧响应时保持可选，缺失动作不能被前端默认启用，也不能由前端推算后端权限。
- 门禁回归需同时覆盖有效契约通过、过时快照失败、动作枚举遗漏失败，以及新增动作可选性丢失失败。同步类型不意味着增加可见操作入口。

### 共享解析与渲染测试

旧转换运行时专属 characterization 与直接加载替身已随实现删除。共享 `docx_rules`、表格解析和正式 DocumentIR/renderer 的必要回归继续保留；不能以旧实现测试替代正式输出合同。真实 DOCX 校验应读取实际 `docx.Document`，不得使用污染全局模块表的替身掩盖失败。

### 复核状态与成功渲染夹具

- 区分未渲染任务的初始默认值与成功任务的已有质量证据。同一代、同一结果的复核和重置测试应先确认公式摘要符合夹具预期，再断言 `quality_status`、`quality_summary` 保持不变以及交付状态符合合同；不能把成功任务重新断言为 `quality_summary={}`。
- 成功回调路径需要可验证的 DOCX 和正式渲染报告。优先复用测试 runtime 已配置的 renderer；确需替身时应实现当前 `render_to_result` 结果合同，不能只返回 `b'fake-docx'`，也不能绕过质量检查。具体报告合同见 [Word 生成规则](./word-generation-rules.md#rnd-502公式报告与结果绑定的可执行合同)。

### DOCX 渲染验证

- 定向测试应同时断言稳定的结构证据和可见内容，不以单一高层库属性或“文件可打开”代替行为验证。
- 结构性输出变更必须按 [Word 生成规则](./word-generation-rules.md) 的规则 ID、冲突矩阵和样本分层执行专项回归；外部/人工结论要记录实际工具、版本、输入输出和当前代码版本。
- 无法运行真客户端或在线门禁时，说明替代检查和剩余风险，不把未观察到的结果写成已通过。

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)
