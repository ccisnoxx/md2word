---
doc_type: deploy-guide
slug: hostdzire-dmit-md2word
component: pdf-to-word-backend
status: current
summary: md2word 在 dmit + WireGuard + hostdzire 结构下的实际部署和线上验证记录。
tags: [deploy, nginx, docker, wireguard, hostdzire, dmit]
last_reviewed: 2026-06-29
---

# md2word 线上部署记录

## 拓扑

- `dmit`：公网入口，`nginx stream` 按 `80` 和 `443 SNI` 把流量透传到 `hostdzire`
- `hostdzire`：项目实际部署机，跑 `docker compose`、本机 `nginx`、MySQL、Redis
- `WireGuard`：`dmit=10.0.0.1`，`hostdzire=10.0.0.2`

当前 `dmit` 的 `nginx` 已经把绝大多数域名默认透传到 `10.0.0.2:443`，HTTP `80` 也默认透传到 `10.0.0.2:80`。因此这个项目上线时通常不需要改 `dmit`，只需要在 `hostdzire` 新增站点。

## 本次约定

- API 域名：`md2word.962850.xyz`
- Release 根目录：`/root/md2word-releases`
- 当前普通上线目录：`/root/md2word-releases/<short-sha>`
- Compose 文件：`/root/md2word-releases/<short-sha>/docker/prod/docker-compose.yml`
- 运行环境变量：`/root/md2word-releases/<short-sha>/.env`
- 内部账号 JSON：`/root/md2word-releases/<short-sha>/deploy/auth_internal_users.json`
- Docker Compose 项目名：`md2word-p0`
- Docker API 回源端口：`127.0.0.1:18000`
- 宿主机 nginx 站点文件：`/etc/nginx/sites-enabled/md2word-api.962850.xyz.conf`（历史文件名；实际 `server_name` 是 `md2word.962850.xyz`）
- MinerU 回调基础地址：`https://md2word.962850.xyz/api/v1/mineru-callbacks/result`

`md2word-api.962850.xyz` 是早期错误域名，不作为线上入口使用。当前公开入口、CORS origin 和 MinerU callback URL 都应使用 `md2word.962850.xyz`。

`/root/md2word` 是历史工作树，可能包含早期 rsync 或人工操作留下的本地修改；普通上线不要把它作为默认 `git pull` 目标，也不要为了上线直接在该目录执行 `git reset --hard`。当前实际发布路径以 `/root/md2word-releases/<short-sha>` 为准，每个 release 从 GitHub archive 导出运行包，复用上一版 release 的 `.env` 和内部账号 JSON。release 目录不保留 `.git`，也不包含 `.idea`、`.codex`、`.agents`、`.trellis`、`.run` 等开发目录。

## 标准迭代流程

后续代码和文档迭代遵循 [线上优先验证流程](/Users/sc/PycharmProjects/md2word/docs/deploy/online-first-validation-workflow.md)：

1. 在本地完成代码或文档改写，跑不依赖真实服务的检查并提交。
2. 推送 `main` 到 GitHub，确认 `git ls-remote origin refs/heads/main` 返回目标 commit。
3. 用私密 VPS 登录信息 SSH 到 `hostdzire`；不要把 `/Users/sc/work_file/bak_file/VPS.txt` 的内容写入仓库、任务记录或对话。
4. 在 `hostdzire` 新建 `/root/md2word-releases/<short-sha>`，从 GitHub bare 源缓存 fetch 目标 commit，再用 `git archive` 导出运行包。
5. 从当前运行 release 复制 `.env` 和 `deploy/auth_internal_users.json`，只更新非敏感的 `APP_VERSION` / `DEPLOYMENT_ID`。
6. 在新 release 内 build/up Docker Compose，并检查 API、Worker、MySQL、Redis/Celery。
7. 先跑 `/health/ready` 和 `check_release.py --runtime-url`，再按需求决定是否跑 Golden Sample 预检和真实 4 样本回归。

普通代码更新只动 `hostdzire`。只有域名、证书、WireGuard 或前置转发异常时才排查 `dmit`。

## 快速上线命令骨架

本节命令里的 `<hostdzire-ssh>` 是本机根据私密 VPS 文件临时组装的 SSH 目标，不要把真实地址、密钥或端口写入仓库。

本地：

```bash
git status --short --branch
git push origin main
git ls-remote origin refs/heads/main
```

注意：`.gitattributes` 里的 `export-ignore` 规则必须已经随目标 commit 提交并推送到 GitHub，hostdzire 对该目标 commit 执行 `git archive` 时才会排除 `.git`、`.idea`、`.codex`、`.agents`、`.trellis`、`.run` 等开发目录。如果目标 commit 早于这次规则变更，导出的 release 包仍可能包含这些已被 Git 跟踪的开发文件。

hostdzire：

```bash
set -euo pipefail

FULL_SHA="<target-full-sha>"
SHORT_SHA="${FULL_SHA:0:7}"
RELEASE_DIR="/root/md2word-releases/${SHORT_SHA}"
SOURCE_REPO="/root/md2word-release-source.git"
REPO_URL="git@github.com:ccisnoxx/md2word.git"

CURRENT_ENV="$(docker inspect md2word-p0-api-1 \
  --format '{{ index .Config.Labels "com.docker.compose.project.environment_file" }}')"
CURRENT_RELEASE="$(dirname "${CURRENT_ENV}")"

if [ -e "${RELEASE_DIR}" ]; then
  echo "release dir already exists: ${RELEASE_DIR}" >&2
  exit 1
fi
if [ ! -d "${SOURCE_REPO}" ]; then
  git clone --bare "${REPO_URL}" "${SOURCE_REPO}"
fi
git --git-dir="${SOURCE_REPO}" fetch --prune --tags origin \
  "+refs/heads/main:refs/heads/main"
git --git-dir="${SOURCE_REPO}" cat-file -e "${FULL_SHA}^{commit}"
mkdir -p "${RELEASE_DIR}"
git --git-dir="${SOURCE_REPO}" archive --format=tar "${FULL_SHA}" | \
  tar --no-same-owner -x -C "${RELEASE_DIR}"
for path in .git .idea .codex .agents .trellis .run; do
  test ! -e "${RELEASE_DIR}/${path}"
done

cp "${CURRENT_RELEASE}/.env" "${RELEASE_DIR}/.env"
cp "${CURRENT_RELEASE}/deploy/auth_internal_users.json" \
  "${RELEASE_DIR}/deploy/auth_internal_users.json"

RELEASE_ID="$(date -u +%Y%m%dT%H%M%SZ)"
sed -i "s/^APP_VERSION=.*/APP_VERSION=${SHORT_SHA}/" "${RELEASE_DIR}/.env"
sed -i "s/^DEPLOYMENT_ID=.*/DEPLOYMENT_ID=hostdzire-${RELEASE_ID}-${SHORT_SHA}/" \
  "${RELEASE_DIR}/.env"

cd "${RELEASE_DIR}"
docker compose --env-file .env -f docker/prod/docker-compose.yml build
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d
docker compose --env-file .env -f docker/prod/docker-compose.yml ps
docker compose --env-file .env -f docker/prod/docker-compose.yml logs --tail=120 api worker
```

如果 `.env` 里还没有 `APP_VERSION` 或 `DEPLOYMENT_ID`，先追加这两个字段，再执行 `up -d --force-recreate api worker` 让 API/Worker 读取新的发布标识。MySQL、Redis 和 Docker volumes 不随 release 目录切换而删除。

回滚时回到上一版 release 目录执行：

```bash
cd /root/md2word-releases/<previous-short-sha>
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d --force-recreate api worker
```

## 证书和入口

- 复用现有 `/etc/nginx/snippets/cert-962850.xyz.conf`
- 证书文件在 `/etc/nginx/ssl/962850.xyz/`
- HTTP ACME 验证路径复用 `/etc/nginx/snippets/acme-challenge.conf`

本机如果启用 `mosdns` + `sing-box` fakeip 分流，`md2word.962850.xyz` 可能解析成 `28.0.*`。这是本机代理接管国外域名的预期行为，不代表公网 DNS 或线上入口异常；排查公网入口时可用公共 DNS 查询或 `curl --resolve md2word.962850.xyz:443:<dmit-public-ip> ...` 强制验证 dmit 入口。真实公网 IP 只从私密 VPS 文件读取，不写入仓库文档。

## 秘钥和账号

真实部署密钥、JWT secret、内部账号密码和 `MINERU_API_TOKEN` 只写入忽略提交的根目录 `.env`；内部账号原始 JSON 单独放在忽略提交的 `deploy/auth_internal_users.json`，不写入跟踪文档。

内部账号通过 `.env` 中的 `AUTH_INTERNAL_USERS_FILE=deploy/auth_internal_users.json` 读取，不再把账号 JSON 塞进环境变量。这样 PBKDF2 hash 里的 `$` 不会被 Compose 或 shell 展开。

MinerU 公开回调当前按下面约定配置：

- `PUBLIC_DEPLOYMENT_MODE=single_tenant_public`
- `MINERU_CALLBACK_URL=https://md2word.962850.xyz/api/v1/mineru-callbacks/result`
- `MINERU_UID` 写入 `.env`，按 MinerU 官方文档用于 `uid + seed + content` checksum 验签

不要给 callback URL 追加自定义 token 或 query 参数；服务端提交任务时会生成随机 `seed`，收到 callback 后按官方 checksum 规则验签。

需要恢复时：

- 看本机忽略文件 [.env](/Users/sc/PycharmProjects/md2word/.env)
- 如需重置内部账号密码，用 [app/services/auth/service.py](/Users/sc/PycharmProjects/md2word/app/services/auth/service.py) 里的 `hash_password()`

## 翻译能力边界

当前部署默认：

- `DEFAULT_TRANSLATION_MODE=direct`
- `OPENAI_BASE_URL` / `OPENAI_API_KEY` 已由 `.env` 管理，不写入文档
- ready health 显示 `translation_provider_backend=openai_compatible` 且 `translation_available=true` 时，`en2zh_pdf_to_word` 可用于线上实验

即使翻译可用，默认任务模式仍保持 `direct`，避免普通 PDF 转 Word 请求默认消耗翻译额度。
