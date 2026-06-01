---
doc_type: deploy-guide
slug: hostdzire-dmit-md2word
component: pdf-to-word-backend
status: current
summary: md2word 在 dmit + WireGuard + hostdzire 结构下的实际部署记录。
tags: [deploy, nginx, docker, wireguard, hostdzire, dmit]
last_reviewed: 2026-05-31
---

# md2word 线上部署记录

## 拓扑

- `dmit`：公网入口，`nginx stream` 按 `80` 和 `443 SNI` 把流量透传到 `hostdzire`
- `hostdzire`：项目实际部署机，跑 `docker compose`、本机 `nginx`、MySQL、Redis
- `WireGuard`：`dmit=10.0.0.1`，`hostdzire=10.0.0.2`

当前 `dmit` 的 `nginx` 已经把绝大多数域名默认透传到 `10.0.0.2:443`，HTTP `80` 也默认透传到 `10.0.0.2:80`。因此这个项目上线时通常不需要改 `dmit`，只需要在 `hostdzire` 新增站点。

## 本次约定

- API 域名：`md2word-api.962850.xyz`
- 部署目录：`/root/md2word`
- Compose 文件：`/root/md2word/docker/prod/docker-compose.yml`
- 运行环境变量：`/root/md2word/.env`
- 内部账号 JSON：`/root/md2word/deploy/auth_internal_users.json`
- Docker API 回源端口：`127.0.0.1:18000`
- 宿主机 nginx 站点文件：`/etc/nginx/sites-enabled/md2word-api.962850.xyz.conf`
- MinerU 回调基础地址：`https://md2word-api.962850.xyz/api/v1/mineru-callbacks/result`

## 证书和入口

- 复用现有 `/etc/nginx/snippets/cert-962850.xyz.conf`
- 证书文件在 `/etc/nginx/ssl/962850.xyz/`
- HTTP ACME 验证路径复用 `/etc/nginx/snippets/acme-challenge.conf`

## 秘钥和账号

真实部署密钥、JWT secret、内部账号密码和 `MINERU_API_TOKEN` 只写入忽略提交的根目录 `.env`；内部账号原始 JSON 单独放在忽略提交的 `deploy/auth_internal_users.json`，不写入跟踪文档。

内部账号通过 `.env` 中的 `AUTH_INTERNAL_USERS_FILE=deploy/auth_internal_users.json` 读取，不再把账号 JSON 塞进环境变量。这样 PBKDF2 hash 里的 `$` 不会被 Compose 或 shell 展开。

MinerU 公开回调当前按下面约定配置：

- `PUBLIC_DEPLOYMENT_MODE=single_tenant_public`
- `MINERU_CALLBACK_URL=https://md2word-api.962850.xyz/api/v1/mineru-callbacks/result`
- `MINERU_UID` 写入 `.env`，按 MinerU 官方文档用于 `uid + seed + content` checksum 验签

不要给 callback URL 追加自定义 token 或 query 参数；服务端提交任务时会生成随机 `seed`，收到 callback 后按官方 checksum 规则验签。

需要恢复时：

- 看本机忽略文件 [.env](/Users/sc/PycharmProjects/md2word/.env)
- 如需重置内部账号密码，用 [app/services/auth/service.py](/Users/sc/PycharmProjects/md2word/app/services/auth/service.py) 里的 `hash_password()`

## 翻译能力边界

当前部署默认：

- `DEFAULT_TRANSLATION_MODE=direct`
- `OPENAI_BASE_URL` / `OPENAI_API_KEY` 已由 `.env` 管理，不写入文档
- ready health 显示 `translation_available=true` 时，`en2zh_pdf_to_word` 可用于线上实验

即使翻译可用，默认任务模式仍保持 `direct`，避免普通 PDF 转 Word 请求默认消耗翻译额度。
