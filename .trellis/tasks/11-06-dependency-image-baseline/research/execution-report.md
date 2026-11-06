# B02 实施与定向验证结果（2026-11-06）

## 结果

在基线 `828e1d9d656bf266cba7bba0ed23a62c550db15c` 上完成依赖锁及镜像引用改动。原停止点和首次调查保存在 `preflight-stop-report.md`、`execution-preflight.json`；用户随后批准只补齐 Pillow 12.2.0，恢复原实施顺序。

本次 57 项运行依赖没有升级、降级或删除。`requirements.txt` 仅补充 PyMySQL 的 rsa extra；新增 `requirements/locks/cp311-linux-amd64.txt`，dev/prod 共同消费该锁。两个 Dockerfile 固定同一官方 Python digest，离线 hash/wheel-only 安装；两个 Compose 仅修改 image 字段，API/Worker 共用必填 `MD2WORD_IMAGE`，MySQL/Redis 固定已核实 digest。相关部署、runbook、quality-guidelines 已同步。

这些是执行方的验证结果，不表示任务设计方已验收。任务未归档，没有提交、推送、CI、部署或生产服务/卷/数据库变更。

## 来源与输入

- 目标为 CPython 3.11.18 / Debian 13 trixie / linux/amd64，实际 glibc 2.41。
- 原 `/opt/pub2-wheels` 位于生产 API 容器内。通过只读复制获取原 57 个文件，逐项复核历史官方文件名/hash，过滤工具 pip 后得到 56 个运行 wheel；生产目录最终 hash 保持不变。
- Pillow 12.2.0 的官方 JSON 给出两个兼容 amd64 wheel，按目标标签优先级唯一选取 `pillow-12.2.0-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`。只下载这个运行包，SHA-256 为 `e74473c875d78b8e9d5da2a70f7099549f9eb37ded4e2f6a463e60125bccd176`，与 PyPI 公布值一致。URL、时间和完整性记录见 `wheelhouse-provenance.json`。
- 固定生成器 uv 0.11.19 的官方 wheel 与二进制 hash、许可证和下载时间见 `generator-provenance.json`；它只用于生成锁，不进入运行闭包。
- A/B venv 使用 pip 24.0、setuptools 79.0.1，没有 wheel 工具；候选全局环境另有 wheel 0.46.3。两种环境均用同一基础 digest 自带的 pip 24.0 安装。生产原有 pip 26.2.2 没有用于候选。
- 根声明、约束、最终锁及来源清单 hash 见 `input-hashes.json`；测试源码清单见 `source-inputs.json`，最终 Docker/锁输入见 `build-inputs.json`。

## 执行命令与结果

以下 `${B02_REMOTE_DIR}` 表示本轮新建的任务专用目录，仓库不保存含账户标识的主机绝对路径。所有远端连接只经 `ssh hostdzire` 或 `scp`，具体日志与原始 pip report 保留在远端任务目录。

| 检查 | 实际命令或执行入口 | 结果 |
|---|---|---|
| 补齐 wheelhouse | 指定本地解释器运行 `research/prepare_wheelhouse.py <已授权任务目录>` | 官方 Pillow hash 匹配，57 个运行 wheel 完整，pip 单列。 |
| Docker 来源 | `docker info`；`docker buildx inspect`；`docker pull --platform linux/amd64 <pulled-images.json 中三个固定引用>` | active mirrors 为空、代理未设置，docker driver / BuildKit v0.29.0；三次正常 pull 成功，无换源或重试。 |
| A/B 解析安装 | 两个独立禁网容器分别 `docker exec -w /src <容器名> env -i PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 sh /inputs/run_resolution.sh` | 两次均退出 0。脚本使用原定 uv/pip 命令模板、独立 venv/cache，均通过 pip check。 |
| 集合及制品比较 | 指定本地解释器运行 `research/compare_installs.py` | 规范化锁、安装版本集合完全相同，57 项均匹配候选版本及官方制品 hash。 |
| 四项 DOCX 测试 | 仅 A 中 `/work/venv/bin/python -m unittest <implement.md 四个完整用例>` | 4/4 通过，耗时 0.508 秒；未调用真实 Provider/MinerU。完整参数见 `docx-test-result.json`。 |
| RSA 最小检查 | A 中读取 PyMySQL 元数据及 `pymysql._auth._have_cryptography` | rsa extra 声明存在，cryptography 可用；没有进行数据库握手。 |
| 唯一候选构建 | `docker build --platform linux/amd64 --progress plain --iidfile ${B02_REMOTE_DIR}/candidate.iid -f ${B02_REMOTE_DIR}/source/docker/prod/Dockerfile -t md2word-b02-candidate:20261106 ${B02_REMOTE_DIR}/source` | 仅执行一次，退出 0；开始/结束时间及构建日志 hash 见 `build-result.json`。 |
| 候选运行保护 | 禁网、只读文件系统的临时容器运行 `python /inputs/check_candidate.py` | UID 1000；57 项运行版本匹配；pip check 通过；pdfinfo/pdftoppm 可用，poppler-utils 为 25.03.0-5+deb13u4。 |
| 产物身份 | 为 API/Worker 分别 `docker create --network none <同一候选标签> python -c pass` 后 inspect | 两个容器均未启动，实际 image ID 与唯一候选相同；不等同启动 API/Worker 服务。 |
| 配置与文档 | Compose 解析后与 HEAD 对比；`git diff --check`；独立只读复核 | Compose 除 image 字段外完全相同，非特权用户、必填密码、回环绑定、healthcheck、Poppler 均保留；两项文档发现已修复。 |
| 最终任务材料 | 指定本地解释器运行 `task.py validate .trellis/tasks/11-06-dependency-image-baseline` 与 `research/check_artifacts.py` | context 引用、JSON/AST、输入 hash、Git 范围、空白及主机信息脱敏检查通过；详细结果见 `artifact-check.json`。 |

构建中 pip 检测到基础镜像已预装 packaging 26.3，没有重新安装。为核实实际内容，候选检查逐文件比对了已核实 packaging wheel 的 28 个文件，全部一致；只排除安装器会重写的 RECORD。没有因此更换包或追加构建。

原始安装报告保留远端 A/B 目录；仓库的 `A/install-evidence.json`、`B/install-evidence.json` 仅保留验收所需的版本、文件、URL、hash 与原报告 hash，未复制上游包介绍及个人联系信息。

## 保留的远端资源

目标仅为 hostdzire。实际目录在交付回复中报告，仓库统一记作 `${B02_REMOTE_DIR}`；该目录新建且未覆盖旧目录。

| 资源 | 最终状态 / 占用 |
|---|---|
| 任务目录 | 保留，最终清点约 768.0 MiB（805,328,242 字节，du apparent bytes）。 |
| `md2word-b02-candidate:20261106` | 保留，Docker inspect Size 为 164,124,356 字节，约 156.5 MiB。 |
| `md2word-b02-a-20261106` | 已停止；可写层 9,887,744 字节。 |
| `md2word-b02-b-20261106` | 已停止；可写层 28,672 字节。 |
| `md2word-b02-image-check-20261106` | 检查退出 0；可写层 12,288 字节。 |
| `md2word-b02-api-identity-20261106` | created，未启动；可写层 4,096 字节。 |
| `md2word-b02-worker-identity-20261106` | created，未启动；可写层 4,096 字节。 |

候选与两个身份容器的 image ID 均为 `sha256:ab256928db7c1e46ef11f9945ed5f9cc45d25eedb44ecd57c2f506081579e7ad`。官方基础镜像身份和大小另见 `pulled-images.json`。目录、容器 rootfs 与镜像层存在共享关系，不能直接相加；Docker 构建缓存未清理，也没有将共享缓存空间全部归因于本任务。

A/B 的解析、安装、pip check 已先完成，A 的业务测试也已完成；最后仅停止两个空闲的 `sleep infinity` 容器，Docker stop 后其进程退出码为 137，OOMKilled 为 false。这不是解析、安装或测试失败。

任务开始时可用空间 65,515,589,632 字节，最终清点为 63,672,127,488 字节。生产四容器的 ID、image ID、running 状态及启动时间与开始时完全一致，原 wheelhouse hash 未变；详见 `remote-resources.json`。所有任务容器禁网，挂载仅指向任务目录，无业务卷或发布目录挂载。保留资源供用户决定清理，未 prune 或删除共享资源。

## 验证边界

- 本轮只构建生产候选一次。开发 Dockerfile 的同锁、同基础引用和安装块做静态一致性核对，没有另行构建开发镜像。
- 未部署或启动 API/Worker/MySQL/Redis 服务，未运行全仓测试、发布聚合检查、在线门禁、真实供应商调用或 Word 客户端验证。
- apt/Poppler/系统传递包和构建时间戳没有锁快照；不能宣称整镜像逐字节可复现。固定当前候选 image ID 也不能替代生产验收。
- 新增任务脚本的说明、非显然分支注释及开发者输出采用中文；业务 Python 文件没有修改。
