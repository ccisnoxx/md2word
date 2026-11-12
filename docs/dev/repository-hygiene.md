---
doc_status: active
last_verified_commit: null
owner: null
verification_scope: >-
  既有正文与工具入口/参数声明的局部静态对照；仅追加元数据，原扫描和制品结论未重新执行验证。原文及输入身份见 ../../.trellis/tasks/archive/2026-11/11-10-documentation-evidence-governance/research/b3-preparation.md。
---

# 仓库卫生检查

本仓库使用标准库检查器与原生 Git `pre-commit` 钩子，在本地提交前检查实际暂存内容。Gitleaks 是固定版本的开发工具，不加入应用运行依赖，不安装 pre-commit 框架，也不配置 GitHub Actions 或 CI。

## 检查范围与命令

在仓库根目录运行：

```bash
python3 scripts/ops/check_repository_hygiene.py --staged
python3 scripts/ops/check_repository_hygiene.py --tracked
python3 scripts/ops/check_repository_hygiene.py --files docs/dev/new-note.md scripts/dev/new-tool.py
```

- `--staged` 通过 NUL 分隔的 Git 接口读取本次新增、修改和重命名目的路径的完整 index blob；适用于初始提交和部分暂存。删除没有待提交内容，无需读取。它不 stash、不暂存文件，也不改写 index 或工作树。
- `--tracked` 读取当前跟踪工作树；与暂存扫描的输入不同。工作树缺失或读取失败会报错，不自动搜索 ignored 或其他未跟踪私有配置。
- `--files` 只读取显式指定的仓库相对路径，供尚未暂存的任务新增候选使用；不会自动扩展到整个工作区。
- 退出码 `0` 表示所检查范围无规则命中，`1` 表示违规，`2` 表示输入或 Git 读取失败。成功读取的空集合合法。

文件名以 `.tmp` 结尾时拒绝提交，大小写不敏感。文本规则拒绝 `/Users/`、`/home/` 和 Windows `Users` 下的真实个人用户目录绝对路径（包括常见 JSON 转义），并允许明确变量或语义占位符。现有服务器部署使用的 `/root/` 不包含开发者用户名，不在该个人路径规则内。私网地址规则用 `ipaddress.IPv4Address` 验证候选，只识别 RFC1918 IPv4；标准回环和绑定地址可用于已有开发场景。不声称覆盖内部域名、公网拓扑或全部 IPv6。

检查器只输出仓库相对定位、规则 ID 和中文提示，不输出命中行或敏感值。含 NUL 或无法按 UTF-8 解码的文件只检查文件名，并逐项报告内容跳过；符号链接只检查链接目标文本，不读取所指向的文件；子模块内容明确跳过。归档内部内容、其他编码、未 fetch 的远端、其他克隆和私有 ignored 配置不在本次保证内。

## 固定 Gitleaks 与制品校验

钩子要求 Python 3.9 以上、Git 和 **Gitleaks 8.30.1**。扫描器缺失、版本不符、运行失败或无法提供报告时阻止提交，不自动安装或降级。

官方来源：[v8.30.1 发布页](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)。本轮已将 Darwin arm64 发布包与官方资产 SHA-256 对账：

| 制品 | SHA-256 |
|---|---|
| `gitleaks_8.30.1_darwin_arm64.tar.gz` | `b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5` |

在 macOS arm64，可按以下步骤安装；先核对平台，不将此制品用于其他平台。目录变量只指向本次下载的临时目录：

```bash
hygiene_tools_dir=$(mktemp -d)
curl --fail --location \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_darwin_arm64.tar.gz \
  --output "$hygiene_tools_dir/gitleaks.tar.gz"
printf '%s  %s\n' \
  b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 \
  "$hygiene_tools_dir/gitleaks.tar.gz" | shasum -a 256 -c - && \
tar -xzf "$hygiene_tools_dir/gitleaks.tar.gz" -C "$hygiene_tools_dir" gitleaks && \
mkdir -p "$HOME/.local/bin" && \
install -m 755 "$hygiene_tools_dir/gitleaks" "$HOME/.local/bin/gitleaks"
export PATH="$HOME/.local/bin:$PATH"
gitleaks version
```

校验失败时停止，不安装该制品。其他平台从同一固定版本发布页选择匹配制品，核对官方 SHA-256 后安装。版本输出应为 `8.30.1`；升级需要同步审查内置规则、配置和回归。

## 激活与回退

每个新 clone 都需要安装工具并激活钩子。先记录现有本地值；如已有其他钩子，先确认其接线，避免覆盖其他工作流：

```bash
git config --local --get core.hooksPath
git config --local core.hooksPath .githooks
git config --local --get core.hooksPath
test -x .githooks/pre-commit
```

`--get` 在未设置时退出 `1`，不代表仓库损坏。激活只修改当前仓库本地配置，不修改全局 Git 配置。可直接运行 `.githooks/pre-commit` 检查当前暂存内容，无需通过测试提交验证。

钩子依次运行卫生检查与 `gitleaks git --pre-commit --staged`，显式使用仓库 `.gitleaks.toml`，设置 `--redact=100`、`--ignore-gitleaks-allow` 并将忽略文件指向空设备，避免行内标记或本地 `.gitleaksignore` 隐藏新问题。Gitleaks 扫描暂存补丁，卫生检查扫描所涉及文件的完整 blob。扫描报告只在任务临时目录短暂存在且已脱敏；钩子只展示报告中的文件、行号、规则及固定中文提示，不转发扫描器原始日志。

如激活前未设置 `core.hooksPath`，回退时仅在当前值仍是 `.githooks` 的情况下运行 `git config --local --unset core.hooksPath`；原来有值则恢复记录的值。若当前值已被其他工作修改，先保留并核对。代码通过精确反向 diff 或后续反向提交恢复；不执行硬重置或历史改写。

本地钩子可被 `--no-verify` 绕过，也依赖本机 checkout 和工具，不提供服务端强制保证。自动安全扫描不能证明凭证有效性、权限或吊销状态。

## 精确例外与历史证据

私网部署例外由 `check_repository_hygiene.py` 的 `PRIVATE_IP_EXCEPTIONS` 唯一维护，以**精确路径 + private-ip 规则 + 整行 UTF-8 SHA-256 + 中文理由**绑定。当前是三份文件中的五个不同内容行：

| 路径 | 理由 |
|---|---|
| `.trellis/tasks/11-06-list-loading-performance/production-switch-plan.md` | 记录既有生产监听与代理协议边界的一行 |
| `deploy/nginx/md2word-api.962850.xyz.conf` | 既有 HTTP、HTTPS 私网监听的两行 |
| `docs/deploy/hostdzire-dmit-md2word.md` | WireGuard 两端和现有转发拓扑的两行 |

不在这里重复地址原文。行位置可以移动，行字节、路径或规则变化会失效；同文件新增地址不会被放行。修改例外应同时说明用途并核对配置 owner，不能用整目录豁免。

`.gitleaks.toml` 继承 8.30.1 内置规则，仅给 `generic-api-key` 增加 AND 例外：以下三个精确仓库相对路径，加上完整一行的 `app/`、`docs/`、`scripts/` 或 `tests/` 下 `.py` / `.json` 文件路径到 64 位小写 SHA-256 的映射形状。路径从开头到结尾完整匹配，不允许任意目录前缀。目录快照扫描须在快照根运行 `gitleaks dir . --config=<仓库配置的绝对路径>`，保持报告中的路径相对快照根。

- `.trellis/tasks/archive/2026-10/10-22-tr-406-partial-batch-failure-semantics/dependency-intermediate-validation.json`
- `.trellis/tasks/archive/2026-10/10-23-rnd-503-image-group-caption-rendering/b1-build-manifest.json`
- `.trellis/tasks/11-06-dependency-image-baseline/research/source-inputs.json`

这三个文件中的 `api_key` 等新凭证字段继续失败；其他文件的相同 hash 形状不因此获得例外。该例外依据是本轮已核对的 25 条文件校验和命中，详见任务 `research/scan-summary.json`。新增其他类型证据时，先核对命中与用途，不按所有十六进制值放行。

路径脱敏后的历史材料只保留原有事实与验收结果，不冒充原始字节。历史 `ops-materials-inventory.json` 的 `content_hashes` 表示生成时的文件身份快照，不代表当前脱敏文件的字节；本轮不重跑原测试，也不为匹配新路径重算旧结果。`artifact-hashes.json` 只规范化路径键，既有 DOCX、图像等制品 hash 保留原值。

历史扫描已发现同一段 Bearer 凭证形态的两条记录；当前树清理与钩子不会从旧提交移除它。有效性和吊销状态尚未确认，应由凭证所有者另行确认、吊销或轮换。历史重写、强推、凭证调用和生产操作需要独立授权，本任务不执行。完整跟踪快照扫描须使用 Git 跟踪列表与对象/工作树内容，不能用受 `export-ignore` 影响的 `git archive` 冒充完整扫描。

## 最小回归

```bash
python3 -m unittest tests.test_repository_hygiene
```

回归仅使用标准库、临时 Git 仓库和运行时伪造数据，覆盖真实 index、初始提交、部分暂存、删除、重命名、空格与换行文件名、精确例外、工具缺失和版本错误、token 不回显，以及同一 hash 例外文件新增 credential 仍被拒绝。实际 Gitleaks 未安装或版本不符时，相应测试明确跳过，不能将该结果记为实际扫描通过；其他卫生规则和 index 回归仍可运行。
