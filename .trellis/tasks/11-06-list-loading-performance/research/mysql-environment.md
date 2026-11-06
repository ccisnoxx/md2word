# 本任务隔离 MySQL 环境

当前状态：run1、run2 均已清理，当前没有本任务测试实例或有效凭据。run1 于 2026-11-07 00:11、run2 于 2026-11-07 00:38（Asia/Shanghai）完成清理；下列历史参数、就绪及清理证据全部保留。本文只记录环境准备、只读连接预检和清理，不代表产品测试、性能验收或生产验收通过。

## 范围与隔离

- 创建前核对：`md2word-list-perf` profile 及对应 Lima 目录不存在；已有 `default`、`md2word-preview-w1`、`ps-scheduler-budget` 均为 Stopped，未启动或修改。
- 主机为 10 个逻辑 CPU、32 GiB 内存，`memory_pressure` 报告 system-wide memory free percentage 60%，磁盘可用 666 GiB，足够容纳本次 2 CPU、3 GiB 内存、20 GiB 数据磁盘配置。Colima 根磁盘同为默认 20 GiB；磁盘镜像为稀疏文件，不代表实际分配 40 GiB。
- Colima 0.10.3；使用原生 aarch64 / VZ。执行前读取本机 `colima start --help`；实际命令为：

```sh
colima start md2word-list-perf --activate=false --ssh-config=false --template=false --mount none --cpus 2 --memory 3 --disk 20 --runtime docker --vm-type vz --arch aarch64
```

- 未挂载主机工作目录，不修改默认模板或 SSH 配置；创建了本 profile 对应的 Docker context，但默认 context 前后均为 `default`。所有 Docker 操作显式指定下列 endpoint。
- 启动完成后再次核对，其余三个 profile 仍为 Stopped。未访问生产、未读取业务 `.env`、未运行 API/Worker。

## 镜像与 daemon 证据

- Docker endpoint：`unix:///Users/sc/.colima/md2word-list-perf/docker.sock`
- 实际 daemon：Docker 29.5.2，ID `cb77bc2b-b4d6-49db-81ab-e018d349ef45`，aarch64，2 CPU，`MemTotal=3040718848`。
- 拉取前读取实际 `docker info` JSON：`RegistryConfig.Mirrors=[]`；`HttpProxy`、`HttpsProxy`、`NoProxy` 均为空。
- 按原始固定标签执行一次正常 `docker --host unix:///Users/sc/.colima/md2word-list-perf/docker.sock pull mysql:8.4`，全部镜像层成功下载，退出码 0；未换源、未替换版本、未重试拉取。
- 镜像：`docker.io/library/mysql:8.4`，arm64。
- RepoDigest：`mysql@sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902`。本 daemon 的 image inspect 同时返回该 SHA 为 image ID。
- 拉取后从实际创建的容器提取并检查官方入口脚本，确认显式密码和 `MYSQL_ROOT_HOST` 的初始化方式；使用随机生成的本任务密码，未使用默认密码或随机密码日志输出模式。

## 容器和连接

| 项目 | 实际值 |
| --- | --- |
| 容器名 | `md2word-codex-list-perf` |
| 容器 ID | `e603ef4c93c9d2d653215cd9a6b2706df62fb22292835a014368ee8ba5eab16c` |
| 专属新卷 | `md2word-codex-list-perf-data`，挂载到 `/var/lib/mysql` |
| 资源上限 | 2 CPU、2 GiB 容器内存 |
| 端口 | `127.0.0.1:33076` → 容器 `3306/tcp` |
| MySQL | `8.4.13` / `MySQL Community Server - GPL` |
| server UUID | `fe55dbfb-d9fa-11f1-baab-c6bfb732c506` |
| 字符集 / 默认排序规则 | `utf8mb4` / `utf8mb4_0900_ai_ci` |
| 默认事务隔离 | `REPEATABLE-READ` |
| 初始 schema | `information_schema`、`mysql`、`performance_schema`、`sys` |

测试套件仍须自行创建 UUID 库和测试表，采用其既有 schema/collation，并自行删除；本文的 server 默认 collation 不替代测试表实际 collation 证据。本环境为原生 arm64，不能据此宣称生产 amd64 性能等价。

## 凭据交接

专属凭据路径：

`.trellis/tasks/11-06-list-loading-performance/research/data/mysql-environment/credentials.json`

路径相对于 `/Users/sc/PycharmProjects/md2word-wt/list-loading-performance`。文件权限为 0600，父目录为 0700；`data/` 命中现有 Git ignore 规则。JSON 是完整的 `MD2WORD_TEST_MYSQL`、`MD2WORD_TEST_MYSQL_HOST`、`MD2WORD_TEST_MYSQL_PORT`、`MD2WORD_TEST_MYSQL_USER`、`MD2WORD_TEST_MYSQL_PASSWORD` 字符串映射，不含数据库名。仅供主会话程序读取并注入测试子进程，不能打印、提交或写入测试报告。

同目录中的 `mysql.env` 为创建容器使用的 0600 专属环境文件；密码也存在本任务 Docker 容器的配置中，故不要输出完整 `docker inspect`。`readiness.json` 仅存版本、UUID、字符集、隔离和系统库名；没有密码。未复用任何现有凭据或业务数据。

## 本轮验证与保留

- 只读预检使用项目既有 venv 的 PyMySQL，成功从主机 loopback 登录，并执行版本/UUID/字符集/隔离查询与 `SHOW DATABASES`。没有创建测试数据库，没有运行测试套件。
- `docker inspect` 定向确认仅发布 loopback 地址、挂载专属空卷、容器为 running。
- 凭据权限、Git ignore、默认 context 和原 profile 状态已核对。
- 环境准备时保留到主会话明确通知清理；随后按下节完成清理。没有修改其他 worktree、产品代码或 Git 暂存区。

准备过程中一次 Go template 查询使用了不匹配的字段名而返回格式化错误；随即以 `docker info --format '{{json .}}'` 读取实际 JSON 字段并确认空代理。这是取证命令格式错误，不是 daemon 或镜像拉取失败。

## 清理证据（2026-11-07）

主会话确认测试与基准结束、各执行者已删除 UUID 库后，明确通知清理本任务专属环境。本轮先重新读取实际状态，再执行定向删除：

- 容器完整 ID 与上表一致，唯一挂载卷为 `md2word-codex-list-perf-data`；该 daemon 仅有这一容器和这一卷。
- 正常连接读取的 server UUID 仍为 `fe55dbfb-d9fa-11f1-baab-c6bfb732c506`；`SHOW DATABASES` 仅有 `information_schema`、`mysql`、`performance_schema`、`sys` 四库。没有额外库，清理阶段未执行 SQL 删除。
- 依次执行该容器的 `docker stop`、`docker rm` 和专属卷的 `docker volume rm`，均退出 0；随后该 daemon 的容器和卷列表均为空。
- 执行 `colima stop md2word-list-perf`、`colima delete md2word-list-perf --data --force`，均退出 0。删除时出现 `Failed to unlock disk` 提示；后续核对 profile 目录、对应 Lima VM 目录及专属 `_disks/colima-md2word-list-perf` 目录均已不存在，无需额外 unlock 或删除。
- Colima 自动移除了 `colima-md2word-list-perf` Docker context；核对 context 列表只剩 `default`，当前 context 仍为 `default`。
- 仅删除任务证据目录内 `credentials.json`、`mysql.env` 两个凭据文件。保留 `readiness.json`、安全容器 ID、官方入口脚本副本及本报告；未删除整个 `research/data`。
- 清理后 `colima list --json` 只列出原有 `default`、`md2word-preview-w1`、`ps-scheduler-budget`，全部为 Stopped。未改其他 profile、共享镜像下载缓存或 SSH 配置；未执行 Docker prune。

容器、专属数据卷、VM/profile/context 和明文凭据均已撤除。就绪记录和本报告保留供复核；没有留下需后续处理的运行环境。

## run2：异常读取会话专项环境（2026-11-07）

本轮按已批准的 `incident-read-session-plan.md` 重建隔离环境，仅准备供真实 RR 两连接验证和本地差分使用，不在环境准备中运行产品测试。run1 的清理结论仍有效；run2 是全新的 VM、数据卷、实例和随机凭据。

### 创建前及镜像核对

- 创建前 profile、Lima VM 与专属数据磁盘目录均不存在；loopback `33076` 可绑定。原三个 profile 全为 Stopped，当前 Docker context 为 `default`。
- 主机 10 个逻辑 CPU、32 GiB 内存；`memory_pressure` 报告 free percentage 53%，磁盘可用 666 GiB。采用与 run1 相同的 2 CPU / 3 GiB / 20 GiB 数据盘、原生 aarch64 / VZ 配置；`--mount none --activate=false --ssh-config=false --template=false` 均显式保留。
- 新 daemon ID：`025499e0-8de7-4cb0-a1e3-999cb7d43c5c`；Docker 29.5.2，aarch64，2 CPU，`MemTotal=3040710656`。
- 新 daemon 的镜像列表为空；实际 `docker info` 的 mirrors 为 `[]`，HTTP/HTTPS/NO_PROXY 均为空。随后按原引用一次正常拉取 `mysql:8.4` 成功，未换源、未更换版本、未修改共享下载缓存。
- 本轮重新核对的 RepoDigest：`mysql@sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902`，架构 arm64。该 digest 与 run1 相同是本轮检查结果，未据上轮假定。

### 本轮连接身份

| 项目 | run2 实际值 |
| --- | --- |
| Docker endpoint | `unix:///Users/sc/.colima/md2word-list-perf/docker.sock` |
| 容器名 | `md2word-codex-list-perf` |
| 容器 ID | `4aeafee23ecc315392e13977673103accb567b9161995c2fd896a71abb77b2bb` |
| 标签 | `md2word.task=list-loading-performance`、`md2word.run=2` |
| 专属新卷 | `md2word-codex-list-perf-data` |
| 容器资源 / 端口 | 2 CPU、2 GiB；`127.0.0.1:33076` → `3306/tcp` |
| MySQL | `8.4.13` / `MySQL Community Server - GPL` |
| server UUID | `fc058e39-d9fe-11f1-b70f-4e6d454ad100` |
| 字符集 / 排序规则 | `utf8mb4` / `utf8mb4_0900_ai_ci` |
| 查询到的默认隔离 | `REPEATABLE-READ` |
| 准备完成时 schema | `information_schema`、`mysql`、`performance_schema`、`sys` |

已用 PyMySQL 真实连接读取上述字段和 schema 清单。该检查不是两连接一致性测试；测试执行者仍需按方案明确检查其连接的 RR 设置并使用自建 UUID 库。

### 本轮凭据与旧证据保留

- 新随机凭据写回原 `research/data/mysql-environment/credentials.json`；同目录 `mysql.env` 仅供本轮容器创建。两文件 0600，父目录 0700，命中既有 Git ignore；不输出密码。凭据映射键与 run1 相同，不含数据库名。
- run2 安全证据独立写入 `readiness-run2.json`、`container-id-run2.txt`、`docker-entrypoint-run2.sh`；未覆盖 run1 的同类文件。
- run1 `readiness.json` SHA-256 保持 `2a1d24b7b2482d1a4c439876acc7a50ac77aa6db95e2e6a33b923f559877fe56`；`container-id.txt` 保持 `2c1ae65e42d0456fec7a2dd37dc32eaa06773254061ca2bb516ccb1a5d559e03`。
- 已向主会话和 `key_integration` 交接新身份与凭据文件路径。各执行者只使用各自 UUID 库并自行清理库；profile、容器、卷和本轮凭据等待主会话统一最终清理通知。
- 本轮未访问生产、未改产品代码或其他 worktree、未运行测试或基准。原三个 profile 仍为 Stopped，当前 Docker context 仍为 `default`。原生 arm64 环境不能证明生产 amd64 性能。

### run2 最终清理（2026-11-07 00:38）

主会话通知 run2 产品直接验证和基准完成，并授权清理当前自建资产。清理前重新核对，而非仅依赖执行者结论：

- 实际容器完整 ID 为 `4aeafee23ecc315392e13977673103accb567b9161995c2fd896a71abb77b2bb`，仅挂载专属卷 `md2word-codex-list-perf-data`；该 daemon 无其他容器或卷。
- 实际 MySQL UUID 为 `fc058e39-d9fe-11f1-b70f-4e6d454ad100`，`SHOW DATABASES` 只有四个系统库，没有额外测试库；清理阶段未执行 SQL 删除。
- 指定容器 stop/rm、指定卷 rm 全部退出 0，之后容器和卷列表为空。`colima stop md2word-list-perf` 和 `colima delete md2word-list-perf --data --force` 均退出 0。
- 删除时出现与 run1 相同的磁盘 unlock 警告；后续确认 profile、Lima VM、专属数据磁盘三个目录均已不存在，未进行额外 unlock 或广泛删除。
- 专属 Docker context 已随 profile 删除；context 列表及当前 context 均为 `default`。原有 `default`、`md2word-preview-w1`、`ps-scheduler-budget` 三个 profile 全为 Stopped。
- 仅删除新 `credentials.json`、`mysql.env`，保留两轮 readiness、容器 ID 和入口脚本等安全证据。旧端口 `127.0.0.1:33076` 返回连接拒绝（`connect_ex=61`）。没有删除整个 `research/data`，没有修改共享缓存或 SSH 配置。
- run1 两份已记录证据的 SHA-256 仍不变；`readiness-run2.json` SHA-256 为 `57f1225a01868d695388227b5c8fda76673076e6f85d3f6e1bc91b23d08fc56f`，`container-id-run2.txt` 为 `09e7d43642e57a7009877f3f4d463e8db5e37c2a9ef3bbaac741b71af20ce50a`。

run2 的容器、卷、VM/profile/context 和本轮明文凭据均已撤除；无需后续环境清理。未访问生产、提交或推送，也未重新执行产品测试。
