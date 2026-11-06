# B02 依赖解析与镜像来源基线

## 目标与阶段

为 hostdzire 的实际部署平台建立可追溯的 Python 依赖解析、安装与镜像身份基线，避免重建隐含升级或丢失现有依赖能力。来源为总整改计划 B02（A09/A16，P1）；本任务独立验收，不启动其他整改批次。

2026-11-06 用户批准创建任务及只读核查 hostdzire。初轮为只读规划。用户随后明确确认本方案，授权在 hostdzire 独立临时目录和容器生成锁、必要镜像拉取/构建及定向验收；不部署、不引入 CI、不提交或推送。当前进入实施方案 A：hostdzire 的独立任务目录记作 `${B02_REMOTE_DIR}`（沿用已授权目录，若已存在则加后缀）；仅使用 `md2word-b02-` 前缀临时容器与候选资源，按 digest 拉取官方镜像，A/B 独立解析安装，仅 A 执行四个定向 DOCX 测试，构建一次候选。

## 实施前已确认事实

- 实施基线为独立 worktree 的 828e1d9d656bf266cba7bba0ed23a62c550db15c；原工作区既有 B03/夹具改动不纳入本任务。research 保留先前只读采样，不能当作此基线执行结果。
- requirements.txt 有 15 项宽范围直接依赖，未跟踪 Python 完整锁；前端已有 package-lock。两个 Dockerfile 均使用 python:3.11-slim、不固定 pip 升级及 apt 安装；compose 使用 mysql:8.4、redis:7-alpine。
- 目标实测为 Linux amd64、容器 Debian 13 trixie、CPython 3.11.18；宿主 Debian 12 不等于容器 OS。本机 macOS arm64 / Python 3.11.15 只作参考。
- 生产 API/Worker 使用相同 image ID，已安装的 60 项包名/版本集合相同。当前部署来自多层 release override，不能等同于当前仓库 Dockerfile 构建结果。
- 生产启用 PIP_NO_INDEX=1、PIP_FIND_LINKS=/opt/pub2-wheels；该目录含 57 个 wheel，已记录文件 SHA-256，没有历史来源清单；本轮已对账官方 PyPI 元数据，57/57 文件名和 SHA-256 匹配。
- 按已安装 Requires-Dist 与 Linux/CPython markers 静态追踪：现有 15 项根依赖得到 54 项闭包，无发现版本约束冲突；另有 cryptography/cffi/pycparser 三项和 pip/setuptools/wheel 工具三项。此结果不是 pip check 或安装成功证明。
- Docker daemon 29.4.1 的 active mirrors 为空、HTTP/HTTPS proxy 未设置；活动 builder 是 docker driver、BuildKit v0.29.0。没有镜像拉取结果。

完整元数据、镜像摘要、具体版本及证据边界见 research/baseline.md 和关联 JSON。

## 需求

| ID | 范围 |
|---|---|
| R1 | 首个受验收目标限定 CPython 3.11.18 / Debian 13 / linux/amd64，记录工具、源、版本和平台。 |
| R2 | 保留 requirements.txt 的直接依赖声明职责，新增含精确版本和 hash 的运行依赖完整锁，覆盖 python-docx/lxml。 |
| R3 | 首版以目标已装版本对账；不隐含升级/降级，不静默丢掉现有 cryptography/RSA 能力；新增、删除、冲突或安全问题逐项处理。 |
| R4 | 核对制品与可信上游的来源关系，固定 Python/MySQL/Redis 镜像身份，API/Worker 共用同一产物。保留现有运行保护。 |
| R5 | 以两次受控安装和最小真实 DOCX 用例验收；清楚区分依赖可复现、镜像身份和整镜像字节可复现。 |

## 验收标准（由后续执行证据逐项判定）

| ID | 可观察结果 |
|---|---|
| AC01 | 基线写全目标、工具、输入 hash、根依赖/闭包及来源；57 个运行候选 wheel（原 56 项运行制品加本次获批 Pillow）的官方文件身份与 hash 可对账，不把本地 hash 独立当可信来源证明。缺失或不一致即停止。 |
| AC02 | 相同目标、工具、输入和候选版本约束两次受控解析得到一致规范化包名/版本/markers/hash；两个独立干净环境严格安装后的运行包集合一致，均通过 pip check，实际制品来源/hash 与锁一致。第二次只验证可复现性，不重复业务测试。 |
| AC03 | 初版运行依赖与目标 57 项候选集合一致或差异经逐项批准；工具三项单列。必要 extras 声明有实际能力依据，无隐含依赖升级或删除。 |
| AC04 | dev/prod 的目标构建消费同一锁和 Python 基础身份；API/Worker 共用一个候选产物，核对 image ID。Python/MySQL/Redis 的记录包含官方引用、目标平台及经核实 digest；仅有缓存标签不算官方 registry 验证。 |
| AC05 | implement.md 所列真实 Renderer 用例通过：正文/标题、表格合并、OMML、同次产物与锚点证据绑定无非预期变化。版本确实变化时追加固定样本 XML 语义对照；跨次 ZIP 字节不要求相等，同次产物 hash 必须真实匹配。 |
| AC06 | apt/Poppler/系统包及构建时间戳等剩余漂移明确记录；不宣称整镜像逐字节可复现、真实 Word 客户端效果或生产验收通过。 |
| AC-R1 | 远端任务写入仅限 `${B02_REMOTE_DIR}` 与 `md2word-b02-` 前缀资源（官方 digest 拉取所需 Docker 镜像层/构建缓存为已授权工具产物）；报告新增目录、容器、候选镜像及磁盘空间清单，前后 `md2word-p0-*` 状态和启动时间一致。 |
| AC-R2 | 仓库本任务新增/修改文件不含主机 IP、端口、账户名、凭据或个人本地绝对路径；远端只称 hostdzire，任务路径用 `${B02_REMOTE_DIR}`，task.json 的 creator/assignee 为 null。 |

AC01–AC06 对应总计划 L1–L5；AC-R1/AC-R2 约束本轮隔离执行及仓库证据。

## 非目标

不迁移项目管理结构，不新增 Poetry/pyproject/uv 项目；不改前端锁，不扩展多架构/macOS 支持矩阵；不升级业务依赖或 Python/MySQL/Redis 系列；不做 Renderer/B03 重构；不引入私有 registry、CI、apt snapshot；不运行全仓或发布聚合检查、不调用供应商、不部署、不改变数据库/卷、不提交/推送/归档或 add_session。

## 收敛与剩余技术前置

方案 A 已获批准，不再为同一目录隔离、固定工具准备和定向验收重复请求授权。官方 wheel 对账和镜像 registry/平台 manifest 核对已完成；Python 缓存为 3.11.15，排除后使用已核实的官方 3.11.18-slim-trixie amd64 候选。真实拉取、解析、安装、构建与四项测试须以本次执行记录证明；元数据匹配不等于执行通过。若来源、版本或范围变化，停止并报告具体差异，不静默换源或升级。

## 历史停止记录（恢复授权前）

实施前只读复核发现：离线目录位于 `md2word-p0-api-1` 容器内，宿主未发现同路径目录；57 个 wheel 包含工具 pip 26.2.2，却缺少运行必需的 Pillow 12.2.0。候选运行集合为 54 项闭包加 rsa 三项，共 57 项，因此文件数相同不能证明运行闭包完整。历史 57/57 文件与官方 PyPI hash 匹配事实仍有效，当前问题是缺少所需制品，并非已存在制品来源不匹配。

当时在来源/完整性门停止：截至该停止点，尚无远端写入、任务目录创建、临时容器、镜像拉取、解析安装、应用测试或候选构建。任务保持 in_progress，当时执行状态为 blocked。此段为历史记录；当前恢复授权见下节，实际执行结果以 `research/execution-preflight.json` 与 `research/execution-report.md` 等新证据为准，不得将历史元数据观察当作本轮执行通过。

## Pillow 单包恢复授权（已执行）

用户已授权解除上述缺失制品阻塞：通过官方 PyPI JSON API 获取 Pillow 12.2.0 发布文件列表与 SHA-256，唯一选择兼容 CPython 3.11、Linux x86_64 和目标 glibc 的 manylinux wheel，只补充下载这一个运行包。在 hostdzire 新任务目录 `${B02_REMOTE_DIR}` 的独立 wheelhouse 中，将该制品与原有 56 个运行 wheel 组合为 57 项运行集合；pip 工具单列，不修改生产容器内的 `/opt/pub2-wheels`。

恢复状态为 in_progress，表示已获准执行补全流程，不表示 Pillow 已下载或来源/完整性门已通过。先核实官方文件身份、目标兼容性、实际下载 hash 及完整运行集合，再继续原方案 A 的 A/B 独立解析安装、仅 A 四项定向 DOCX 测试和一次候选构建。其他缺失、来源/hash/版本不一致或不能唯一确定兼容制品时仍停止，不扩大运行包下载范围，不切换来源或升级版本。隔离、生产保护、禁止部署/CI/提交/推送及 AC-R1/AC-R2 继续适用。

## 本次执行结果

Pillow 官方单包补齐、57 项运行依赖的 A/B 独立解析安装与 pip check、仅 A 的四个 DOCX 用例、一次候选构建及 API/Worker 产物身份核对均已完成。远端任务资源保留，生产容器状态及原始 wheelhouse 未变；没有部署、提交或推送。详见 [执行报告](research/execution-report.md) 与 [验收记录](research/acceptance.json)，这些是执行方报告，不代替任务设计方验收。
