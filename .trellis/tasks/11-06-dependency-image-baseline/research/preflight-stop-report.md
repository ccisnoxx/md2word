# B02 实施前检查结果（2026-11-06）

## 结论与停止点

来源完整性检查失败，按 implement.md 第 2 步及“缺 wheel 即停止”约束停止后续实施。源码基线为 `828e1d9d656bf266cba7bba0ed23a62c550db15c`，起始 worktree 干净；仅新增本任务文件，未修改 requirements、Dockerfile、compose 或其他产品文件。

`md2word-p0-api-1` 内 `/opt/pub2-wheels` 的 57 个 wheel 与复制的官方 PyPI 来源证据逐项文件名/hash 相同；本次复用来源元数据，没有重新联网查询 PyPI。57 个文件中含工具 `pip==26.2.2`，运行候选 57 项中必需的 `pillow==12.2.0` 没有 wheel，目录下也没有其他嵌套 wheel。现存文件未发现版本或 hash 漂移；这是闭包不完整，不是制品 hash 不匹配。容器已安装元数据中的 Pillow 12.2.0 不等于可供离线重装的 wheel。

## 实际检查

从 worktree 根运行（`B02_LOCAL_PYTHON` 指用户指定的现有解释器，避免在仓库保存个人路径）：

```bash
PYTHONDONTWRITEBYTECODE=1 "$B02_LOCAL_PYTHON" .trellis/tasks/11-06-dependency-image-baseline/research/verify_preflight.py
```

命令退出码为 1，`official_hashes_match=true`、`version_mismatches=[]`、`missing_runtime_wheels=[pillow==12.2.0]`、`source_gate=blocked`。脚本通过 `ssh hostdzire` 只读查询 Docker 状态和容器内 wheel 文件，输出保存为 `execution-preflight.json`。未读私钥、环境凭据或业务数据库；远端 Python 禁止写入字节码。

实施前另执行 `ssh hostdzire 'docker buildx inspect'`：活动 builder 为 default、driver 为 docker、BuildKit v0.29.0，节点 running。`docker info` 实测 active mirrors 为空，HTTP/HTTPS/no-proxy 均未配置。没有通过网络探针推断 pull 成败，未执行 pull。

## 远端资源与服务保护

- 目标仅使用别名 hostdzire。开始时磁盘可用 65,521,700,864 字节（约 61.02 GiB），容量不是此次阻塞原因；执行记录保存结束检查时的磁盘读数。
- 已授权任务目录 `${B02_REMOTE_DIR}` 初查不存在，本轮未创建。新增目录、临时容器、候选镜像标签均为零，任务新增资源占用为 0 字节；没有候选镜像可保留。
- `md2word-b02-` 容器/镜像清单为空；未运行构建，未生成构建缓存。没有清理或删除任何现有资源。
- 四个 `md2word-p0-*` 容器的 ID、image ID、running 状态和启动时间在任务开始、来源复核及结束检查中一致。证据内保存了完整状态，不以此宣称业务验收通过。
- 未执行部署、服务启停、生产容器写入、业务卷挂载、系统包或 Docker 配置修改、提交、推送。

## 尚未执行

固定生成器准备、digest 镜像拉取、rsa extra 修改、锁生成、A/B 独立解析与安装、两次 pip check、A 的四个 DOCX 用例、一次候选构建、API/Worker 候选 image ID 对账均未执行。没有以旧容器、旧安装或文档检查代替这些证据。

apt/Poppler/系统包与构建时间戳仍可能漂移；既有 Poppler 版本只属于历史采样，本轮没有重建证据。不宣称整镜像字节可复现、真实 Word 客户端效果、MySQL RSA 握手或生产验收通过。

## 任务材料检查

`python3 .trellis/scripts/task.py validate .trellis/tasks/11-06-dependency-image-baseline` 已由任务初始化子代理执行通过。主会话使用用户指定解释器并设置 `PYTHONDONTWRITEBYTECODE=1` 检查了全部 15 个任务文件：JSON/JSONL 可解析、context 引用存在、Python AST 可解析、无尾随空白，已跟踪文件无改动，新增文件均在本任务目录。

敏感信息扫描结合 `ssh -G hostdzire` 的实际连接字段，仅输出是否命中；两处“非 root”是原规划的权限保护术语，`1.1.1.2` 是 click-plugins 版本，人工复核后确认均非主机信息泄露。独立只读复核重新计算候选/制品集合、核对 hash 与状态证据，未发现需要修复的问题，未重跑远端命令或应用测试。新增检查脚本的模块说明和开发者输出使用中文，没有修改业务 Python 代码。

执行偏差：初始化子代理两次 Trellis 查询使用了 `python3`，未设置禁止字节码变量。已按创建时间和具体文件名移除这两次调用新生成的 14 个字节码缓存，保留 4 个更早的既有缓存；未以此替代目标 Python 的依赖或业务验收。

## 恢复选项

最小选项是另行确认补齐缺失制品：从官方 PyPI 核实 `Pillow 12.2.0` 的 CPython 3.11 / linux amd64 wheel、来源及 SHA-256，再仅将该 wheel 放入任务专用目录，保持现有 57 个已核实文件与所有运行版本不变。新的制品清单应明确区分 57 项运行依赖与工具 pip，完整性门通过后再恢复原顺序；本轮未执行该下载或变更。

也可由用户提供同版本、同目标且有官方可核实来源/hash 的 wheel 后复核。不采用生产 site-packages 重打包、源码构建、换版本、换索引或跳过 hash 校验。
