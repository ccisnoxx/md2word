# B02 最小设计（已确认）

## 目标与责任

首个目标固定为 hostdzire 当前容器组合：CPython 3.11.18、Debian 13 trixie、linux/amd64。保留 requirements.txt 作为根依赖输入，新增 requirements/locks/cp311-linux-amd64.txt 和一份来源/环境说明。前端锁不动，不创建 pyproject 或应用级依赖管理框架。

数据流：根声明 + 经核对的目标版本约束 → 固定生成器 → 精确版本/hash 锁 → 严格 pip 安装 → API/Worker 共用构建产物。元数据观察文件不是锁文件；本次解析、安装及候选验证结果见 research/execution-report.md。

## 版本与最小声明变动

生产 60 项已装包划分为 54 项已声明闭包、cryptography/cffi/pycparser 三项额外运行能力、pip/setuptools/wheel 三项工具。推荐将现有 PyMySQL>=1.1,<2 改为 PyMySQL[rsa]>=1.1,<2，使既有 RSA 能力进入正式根声明与传递闭包；版本保持 PyMySQL 1.2.3、cryptography 50.0.2、cffi 2.1.1、pycparser 3.12。PyMySQL 官方说明 sha256_password/caching_sha2_password 认证需要 rsa extra；本轮未查询生产账号认证方式，也不声称已观察到该认证分支。选择保留现有能力，避免基线任务顺带删包。

其余直接依赖范围原则上不动；首锁将运行版本全部约束到远端观察值，包括 python-docx 1.2.0、lxml 6.1.3、openai 3.40.0。现有宽范围允许这些版本，不等于当前工作树已与它们通过兼容性测试。锁定期间不升级/降级；官方制品缺失、Requires-Python/依赖冲突或已知安全阻塞出现时，提交具体差异并更新方案。

## 解析工具与安装方式

使用固定 uv CLI 0.11.19 的 pip compile，只输出标准 requirements 锁；运行镜像继续用 pip。选择依据是当前工具可用和现有 requirements 模式，不因 INSTALLER=uv 推断项目已采用 uv 管理。方案 A 已授权在任务隔离环境准备固定生成器、复制制品并解析；实际执行记录需证明固定版本与来源。

pip-tools 是兼容备选，但本机未装且增加工具/pip 配对；freeze 没有来源/hash 和受控闭包；Poetry/项目级 uv 迁移扩大范围。若 uv 0.11.19 遇实际兼容/安全问题，停止说明原因，不自动升级。最新官方文档中的新选项不直接用于旧版。

固定 pip 安装器：优先采用已验证基础 digest 自带 pip 并记录版本，若必须对齐远端 pip 26.2.2，则把该工具制品和 hash 单列固定；不得保留无限制 pip --upgrade。setuptools/wheel 同样记录工具集合，不能把它们误计为业务根依赖。

## 制品来源

生产当前采用离线 wheelhouse。本轮已逐项将 57 个文件名和 SHA-256 对账到官方 PyPI 发布元数据，全部匹配；实施时复用输入未变的结果并核对目标 wheel tags。无官方匹配或无法证明来源时停止，不把目录名 pub2 当上游可信证明，也不访问 pub2 主机。保留现有离线传输方式，来源说明记录规范上游和实际交付制品；不把二进制 wheel 提交进 Git。

按下述 Pillow 单包授权补全并通过来源/完整性门槛后，可从经核实的同一运行 wheel 集合解析并安装，显式 no-index/find-links，不继承未经核对的索引配置，不混用 extra-index-url。独立安装采用 --require-hashes --only-binary=:all:；缺 wheel 即停止，不静默 sdist 构建。完整 hash 列表可能含多个平台制品，安装端仍独立限制 wheel。hash 证明完整性，不能独立证明可信来源。

候选 Docker 构建在受控临时 build context 提供已核实 wheelhouse，COPY 锁及 wheelhouse，执行离线 hash 安装；wheelhouse 由发布准备步骤按 manifest 取齐，目录不在 Git。两个 Dockerfile 共用相同目标输入；在 hostdzire 的 `${B02_REMOTE_DIR}` 与 `md2word-b02-` 前缀临时容器验证，所有试验资源与生产卷/数据库隔离，不更改当前部署；不引入下载服务或私有包仓库。首次实现需核对 .dockerignore 与现有发布打包脚本，只改必要的打包/COPY 接点，不新增大范围发布流程。

## 镜像来源与身份

目标 daemon 的 active mirrors=[]，代理未设置；活动 builder 为 docker driver/内置 BuildKit，无本次另选 docker-container builder。后续若 builder 改变，应再查其适用 registry/proxy 配置，不能把配置文件存在当生效。

当前 MySQL/Redis RepoDigest 已经官方 registry index/amd64 manifest 核对；Python 缓存确认为 3.11.15，不是当前应用的 RootFS 前缀，禁止作为 3.11.18 目标基线。官方 python:3.11.18-slim-trixie 的 amd64 候选已核实，digest 为 sha256:b701198cb708b68d9413ca67d6311bd97c9389a2c5fe4da0511fc652642366cd。规划阶段没有拉取镜像层；本次已按 digest 拉取，见 research/pulled-images.json。当前应用 Dockerfile FROM 指向前一层 md2word-table-crop 本地镜像，生产实际是增量镜像链。

候选保持 Python 3.11.18/trixie、MySQL 8.4.9、Redis 7.4.9 的实际版本，使用 research/baseline.md 已核实的官方引用/目标 manifest；实施时在输入不变的前提下复用此证据。来源默认为原 Docker Hub 官方 library 命名；通过正常 docker pull 路径取固定引用，实际失败再按原错误诊断，不提前换源，不用 curl 超时替代 mirror/pull 证据。

API/Worker 构建一次并共用版本化产物标签，记录 image ID；不得仅把两个 latest 字符串相等视为产物一致。候选镜像只在隔离环境核对，不运行应用/数据库服务。MySQL/Redis 只固定引用，不启动数据库、不挂生产卷。实际部署仍需单独授权。

## 变更面、剩余漂移与回退

授权变更面：requirements.txt 的 rsa extra、一份目标锁/制品来源记录、两个 Dockerfile 和 compose 的依赖/镜像引用、必要 build context 接点、部署/runbook 与 quality-guidelines 中对应的安装描述。依赖声明守卫继续读取根 requirements；不把传递闭包混入根声明掩盖漏依赖。

apt 来源当前为 deb.debian.org 的 trixie/trixie-updates/trixie-security；Poppler 实测 25.03.0-5+deb13u4。暂不锁 apt snapshot 或系统传递包，记录实际版本即可；不承诺镜像字节或 Word 客户端排版可复现。保留非 root、密码必填、回环绑定、healthcheck、Poppler 和现有错误语义。

回退限于 B02 精确差异与本任务临时产物，保留旧锁/镜像身份记录和原工作区改动；不 git reset、不清共享缓存/镜像、不清卷。当前无生产变更，因此无服务回退。若后续必要变更超出上述范围，先更新三件套再确认。

## 隔离执行与证据边界

本次源码基线为 828e1d9d656bf266cba7bba0ed23a62c550db15c。远端任务目录统一以 `${B02_REMOTE_DIR}` 表示，已存在则创建带后缀的新目录，不覆盖旧目录；A/B 使用各自独立缓存、锁输出和干净安装环境。只在 A 运行四个定向 DOCX 测试，候选仅构建一次。

除已授权的官方 digest 镜像层及构建缓存外，远端写入仅限该目录与 `md2word-b02-` 前缀资源。记录开始/结束时的资源清单、空间占用及 `md2word-p0-*` 状态/启动时间；不启动业务服务，不挂生产卷，不连接数据库。仓库证据只使用 hostdzire 别名及任务路径变量，不写入主机 IP、端口、账户标识、凭据或个人本地绝对路径。

## 历史停止记录（恢复授权前）

实施前只读复核发现：离线目录位于 `md2word-p0-api-1` 容器内，宿主未发现同路径目录；57 个 wheel 包含工具 pip 26.2.2，却缺少运行必需的 Pillow 12.2.0。候选运行集合为 54 项闭包加 rsa 三项，共 57 项，因此文件数相同不能证明运行闭包完整。历史 57/57 文件与官方 PyPI hash 匹配事实仍有效，当前问题是缺少所需制品，并非已存在制品来源不匹配。

当时在来源/完整性门停止：截至该停止点，尚无远端写入、任务目录创建、临时容器、镜像拉取、解析安装、应用测试或候选构建。任务保持 in_progress，当时执行状态为 blocked。此段为历史记录；当前恢复授权见下节，实际执行结果以 `research/execution-preflight.json` 与 `research/execution-report.md` 等新证据为准，不得将历史元数据观察当作本轮执行通过。

## Pillow 单包恢复授权（已执行）

用户已授权解除上述缺失制品阻塞：通过官方 PyPI JSON API 获取 Pillow 12.2.0 发布文件列表与 SHA-256，唯一选择兼容 CPython 3.11、Linux x86_64 和目标 glibc 的 manylinux wheel，只补充下载这一个运行包。在 hostdzire 新任务目录 `${B02_REMOTE_DIR}` 的独立 wheelhouse 中，将该制品与原有 56 个运行 wheel 组合为 57 项运行集合；pip 工具单列，不修改生产容器内的 `/opt/pub2-wheels`。

恢复状态为 in_progress，表示已获准执行补全流程，不表示 Pillow 已下载或来源/完整性门已通过。先核实官方文件身份、目标兼容性、实际下载 hash 及完整运行集合，再继续原方案 A 的 A/B 独立解析安装、仅 A 四项定向 DOCX 测试和一次候选构建。其他缺失、来源/hash/版本不一致或不能唯一确定兼容制品时仍停止，不扩大运行包下载范围，不切换来源或升级版本。隔离、生产保护、禁止部署/CI/提交/推送及 AC-R1/AC-R2 继续适用。

## 本次执行结果

Pillow 官方单包补齐、57 项运行依赖的 A/B 独立解析安装与 pip check、仅 A 的四个 DOCX 用例、一次候选构建及 API/Worker 产物身份核对均已完成。远端任务资源保留，生产容器状态及原始 wheelhouse 未变；没有部署、提交或推送。详见 [执行报告](research/execution-report.md) 与 [验收记录](research/acceptance.json)，这些是执行方报告，不代替任务设计方验收。
