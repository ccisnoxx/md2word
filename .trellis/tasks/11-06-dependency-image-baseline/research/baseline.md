# B02 核实记录（2026-11-06，实施前只读采样）

本文保留规划阶段历史事实。当前独立 worktree 实施基线为 828e1d9d，方案 A 已授权；本次安装/构建/测试和资源变化由后续执行记录单列。

## 采样与权限

仓库 main@79f20cef9ca0bb1a59af635e2408e130c4935e2d。起始已有 B03/夹具与总整改文档等修改；创建 B02 前对 51 个既有修改/未跟踪文件记录内容 hash（删除项记缺失）。本次仅任务目录写入；未修改原业务文件或其他任务。

用户明确同意以 hostdzire 为目标并只读核查。动态读取 SSH 配置和 ssh -G 验证别名后连接；未读取私钥或完整 .env。远端仅系统/镜像/包元数据查询、wheel 文件只读 hash、无副作用版本命令；未运行测试、pip check、下载/安装或服务变更。

## 目标环境与当前镜像

宿主 Linux x86_64 / Debian 12，Docker 29.4.1；API/Worker 容器是 Debian 13 trixie 13.7、CPython 3.11.18 / amd64。API/Worker 均 running，同一 image ID、60 项已安装包版本集合完全一致。此状态不是应用健康或业务验收结论。

| 容器 | 配置镜像 | 实际 image ID |
|---|---|---|
| md2word-p0-api-1 | md2word-mixed-lines:d6cddcd5a9ba | sha256:ed9ed78998e7ecb459bfd011e43afd84a57d6f6fec07c2ef925bf5de526026d6 |
| md2word-p0-worker-1 | md2word-mixed-lines:d6cddcd5a9ba | sha256:ed9ed78998e7ecb459bfd011e43afd84a57d6f6fec07c2ef925bf5de526026d6 |
| md2word-p0-mysql-1 | mysql:8.4 | sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084 |
| md2word-p0-redis-1 | redis:7-alpine | sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99 |

MySQL `mysqld --version` 为 8.4.9，Redis `redis-server --version` 为 7.4.9；只读取二进制版本，未连接数据库执行查询。应用当前 release 的 Dockerfile `FROM md2word-table-crop:12188b04b7b4`，且 compose 有多层 override；不能把该增量镜像当成当前仓库 main 的构建证明。Python 缓存 python:3.11-slim 的 RepoDigest 为 python@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0，只凭缓存不能证明当前应用的直接父镜像。

目标 daemon 的 active registry mirrors=[]，HTTP/HTTPS proxy 为空，no-proxy 未配置。当前 builder=default、driver=docker、内置 BuildKit v0.29.0，节点 running、支持 linux/amd64；未创建/启动新 builder。配置/身份不代表现在能下载镜像层，registry 查询的已核实引用汇总在本文末尾；本 worktree 未复制原始 registry 查询文件。

## 依赖版本

requirements.txt 15 项均宽范围，未跟踪 Python 锁；frontend/package-lock.json 已存在。下表目标列来自实际容器元数据，本机列仅作对照：

| 根依赖 | 现有范围 | hostdzire | 本机 |
|---|---|---|---|
| beautifulsoup4 | >=4.12 | 4.15.0 | 4.15.0 |
| boto3 | <2,>=1.34 | 1.43.120 | 1.43.31 |
| celery | <6,>=5.4 | 5.6.3 | 5.6.3 |
| fastapi | <0.137,>=0.136 | 0.136.3 | 0.136.3 |
| loguru | >=0.7 | 0.7.3 | 0.7.3 |
| openai | >=1.0 | 3.40.0 | 2.42.0 |
| pillow | <13,>=12.2 | 12.2.0 | 12.2.0 |
| pydantic-settings | <3,>=2.14 | 2.16.1 | 2.14.1 |
| python-docx | >=1.1 | 1.2.0 | 1.2.0 |
| python-multipart | <0.1,>=0.0.29 | 0.0.32 | 0.0.32 |
| PyMySQL | <2,>=1.1 | 1.2.3 | 1.2.0 |
| PyYAML | >=6.0 | 6.0.3 | 6.0.3 |
| requests | <3,>=2.32 | 2.34.2 | 2.34.2 |
| urllib3 | <3,>=2 | 2.8.0 | 2.7.0 |
| uvicorn | <0.48,>=0.47 | 0.47.0 | 0.47.0 |

目标 lxml 6.1.3，本机 6.1.1；本机 macOS arm64/Python 3.11.15、venv pip 24.0，全局 uv CLI 0.11.19。venv 没有 uv distribution 不等于无全局 uv 命令。INSTALLER 仅是元数据，不作为原始下载来源证明。

按目标包 Requires-Dist 与 Linux CPython markers/extras 静态追踪得到 54 项运行闭包，无发现约束冲突；另有 cryptography 50.0.2、cffi 2.1.1、pycparser 3.12，以及 pip 26.2.2、setuptools 79.0.1、wheel 0.46.3。API/Worker 两边集合相同。静态追踪不是依赖解析或 pip check；不能推导当前源码兼容性。

## 安装来源与系统包

目标 pip 生效配置是 PIP_NO_INDEX=1、PIP_FIND_LINKS=/opt/pub2-wheels。目录存在，含 57 个 wheel，没有 JSON/txt 来源清单。已只读计算每个文件 SHA-256，并通过 HTTPS 读取官方 PyPI 对应版本 JSON 元数据：57/57 文件名与官方 SHA-256 匹配。见 offline-source.json 和 pypi-provenance.json。没有下载 wheel，也没有安装或测试；文件身份匹配不证明这些 wheel 当时一定用于现有 site-packages，更不等于全部依赖无漏洞。

来源链可表述为：PyPI 官方已匹配制品 → 生产现存离线目录。历史下载/传输操作者和途径未恢复；不因目录名推断 pub2 当前角色或访问另一主机。后续候选安装的 report 要重新证明实际消费的是这组已核实制品。

apt 配置为 deb.debian.org 的 trixie、trixie-updates、trixie-security（main）；Poppler 实测 poppler-utils=25.03.0-5+deb13u4。未锁 apt 快照/系统闭包，未证明重新构建会得到同一系统包集合。

## 代码与验收依据

- requirements.txt:9 声明 python-docx>=1.1；app/services/renderer/word_renderer.py:372 使用 document._body._element，版本固定需真实渲染证据。
- docker/prod/Dockerfile:2、docker/dev/Dockerfile:2 使用浮动 Python 标签；两个文件均执行未固定 pip 升级与 apt 安装。
- docker/prod/docker-compose.yml:9、:50 为相同应用标签；:67、:79 是 Redis/MySQL 引用。配置事实与上述实际部署事实分开。
- tests/test_document_ir_word_renderer_layout.py:890、:933、:1387 分别覆盖真实合并表格、OMML、标题/list/公式语义。
- tests/test_formal_mineru_render_evidence.py:47 覆盖真实正式转换的正文/表格、IR/plan/trace/anchor/formula 与本次 DOCX hash 绑定。
- tests/test_render_table_from_html_characterization.py:160 起存在 FakeCell/FakeTable，不能单独证明 python-docx 版本兼容。
- tests/test_runtime_dependency_declarations.py:1 的根声明守卫支持 extras 解析；继续保留 requirements.txt 的直接声明职责。
- docs/deploy/p0-docker-deployment.md:35 指向 hostdzire；.trellis/spec/backend/quality-guidelines.md 区分线上增量发布镜像与仓库可复现构建。

全部测试只是静态定位，本轮零测试执行。

## 官方镜像元数据补充

只读 imagetools inspect --raw 已解析现有 Python/MySQL/Redis RepoDigest 的官方 index 及 amd64 子 manifest；无镜像层下载。进一步检查发现缓存 python:3.11-slim 的 PYTHON_VERSION=3.11.15，4 个 RootFS 层不是当前 44 层应用镜像的前缀，故不能采用缓存 Python digest 固定当前 3.11.18 目标。

目标官方 tag docker.io/library/python:3.11.18-slim-trixie 查询成功，其 amd64 manifest 为 `sha256:b701198cb708b68d9413ca67d6311bd97c9389a2c5fe4da0511fc652642366cd`；manifest annotation 对应 3.11.18-slim-trixie、debian:trixie-slim。此为新构建候选，不证明当前增量应用的历史基础层完全相同，也不证明 pull/build 成功。python-target-manifest.json 中 raw_sha256 仅是所收到 stdout 字节 hash，不作为 registry 确认的 index digest；最终引用使用官方 index 中的 amd64 manifest digest。

| 已确认官方 index 引用 | linux/amd64 manifest |
|---|---|
| docker.io/library/mysql@sha256:c36050afdca850f23cef85703f84c7531a5ae155a11b5ee1c60acb09937c4084 | sha256:14690274f4967ba207939c97dd79a8d6604f1d532218ea6be69c0001ddd2d45f |
| docker.io/library/redis@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99 | sha256:b1addbe72465a718643cff9e60a58e6df1841e29d6d7d60c9a85d8d72f08d1a7 |

方案 A 固定 Python 目标平台 manifest 和 MySQL/Redis 现有对应摘要，已授权走正常 pull 验证镜像层可用性。基础镜像变化和 apt 漂移不等于 Python 业务包升级，但需候选镜像验收。
