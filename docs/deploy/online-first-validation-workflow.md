---
doc_type: deploy-guide
slug: online-first-validation-workflow
component: md2word-deploy-validation
status: current
summary: md2word 本地改写、上传 hostdzire、线上验证和 Golden Sample 签字的标准流程。
tags: [deploy, validation, hostdzire, golden-sample, mysql, celery]
last_reviewed: 2026-06-21
---

# 线上优先验证流程

## 目标

本流程把 md2word 后续迭代固定为“本地改写、新增代码或文档，上传到 hostdzire 后在线上完整验证”。当前本地机器没有可用的 MySQL、Redis/Celery、API/Worker 完整运行环境，也不作为前端 smoke 或全链路验收目标。

## 固定环境

- `hostdzire` 是项目部署和验证机器，普通上线使用 `/root/md2word-releases/<short-sha>` release 目录，运行 Docker Compose、MySQL、Redis/Celery、API、Worker 和本机 nginx。
- `dmit` 是公网前置机，只负责通过 WireGuard / nginx stream 把 `80/443` 流量转发到 `hostdzire`。普通代码更新不改 `dmit`。
- 公开入口使用 `https://md2word.962850.xyz`。在 `hostdzire` 本机验证 API 时优先使用 `http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}`。
- 准生产/生产基线是 MySQL metadata + Redis/Celery + 单 worker。
- P0 Golden Sample 只使用 `tests/fixtures/golden_samples/pdfs/` 下 4 个 OPA228 technical datasheet PDF，不扩展为 10-20 份样本作为 P0 阻塞条件。
- 远程登录信息存放在私密文件 `/Users/sc/work_file/bak_file/VPS.txt`。不要把其中的账号、密码、密钥、IP 细节复制到仓库文档、任务记录或对话输出中。

## 本地阶段

本地只负责编辑和不依赖真实服务的轻量检查。不要为了验收而在本地启动前端、后端、MySQL、Redis/Celery、Worker 或 Playwright smoke。

可做：

- 代码和文档改写。
- `git diff --check` 这类纯文本/格式检查。
- JSON、YAML、Markdown 结构检查。
- 不依赖真实 API、MySQL、Redis/Celery、浏览器和外部服务的纯单元或静态检查。

不做：

- 不启动本地 `run_api.py`、`npm run dev`、Docker dev compose 或 Worker。
- 不连接本地 MySQL、Redis/Celery。
- 不把本地 `npm run test:smoke`、Playwright、前后端联调 smoke 作为本轮验收要求。
- 不在本地跑 Golden Sample 真实转换；本地最多检查 manifest 和脚本参数。

## 发布到 hostdzire

当前推荐路径是 GitHub release 目录发布，不再把 `/root/md2word` 作为普通 `git pull` 目标。`/root/md2word` 可能保留历史本地修改；不要为了上线直接在该目录 reset 或覆盖。

本地先确认目标 commit 已经推到 GitHub：

```bash
git status --short --branch
git push origin main
git ls-remote origin refs/heads/main
```

在 hostdzire 上创建新 release。`VPS.txt` 只用于人工取得登录信息，命令里用 `<hostdzire-ssh>` 占位，例如 `root@<hostdzire>`：

```bash
FULL_SHA="<target-full-sha>"
SHORT_SHA="${FULL_SHA:0:7}"
RELEASE_DIR="/root/md2word-releases/${SHORT_SHA}"
REPO_URL="git@github.com:ccisnoxx/md2word.git"

CURRENT_ENV="$(docker inspect md2word-p0-api-1 \
  --format '{{ index .Config.Labels "com.docker.compose.project.environment_file" }}')"
CURRENT_RELEASE="$(dirname "${CURRENT_ENV}")"

git clone "${REPO_URL}" "${RELEASE_DIR}"
git -C "${RELEASE_DIR}" checkout "${FULL_SHA}"
cp "${CURRENT_RELEASE}/.env" "${RELEASE_DIR}/.env"
cp "${CURRENT_RELEASE}/deploy/auth_internal_users.json" \
  "${RELEASE_DIR}/deploy/auth_internal_users.json"

RELEASE_ID="$(date -u +%Y%m%dT%H%M%SZ)"
if grep -q "^APP_VERSION=" "${RELEASE_DIR}/.env"; then
  sed -i "s/^APP_VERSION=.*/APP_VERSION=${SHORT_SHA}/" "${RELEASE_DIR}/.env"
else
  printf "\nAPP_VERSION=%s\n" "${SHORT_SHA}" >> "${RELEASE_DIR}/.env"
fi

if grep -q "^DEPLOYMENT_ID=" "${RELEASE_DIR}/.env"; then
  sed -i "s/^DEPLOYMENT_ID=.*/DEPLOYMENT_ID=hostdzire-${RELEASE_ID}-${SHORT_SHA}/" \
    "${RELEASE_DIR}/.env"
else
  printf "DEPLOYMENT_ID=hostdzire-%s-%s\n" "${RELEASE_ID}" "${SHORT_SHA}" \
    >> "${RELEASE_DIR}/.env"
fi
```

如果 `RELEASE_DIR` 已存在，先确认它的 `git rev-parse HEAD` 是否等于目标 `FULL_SHA`。不要直接覆盖已存在 release；重新部署同一 commit 时复用该目录 build/up 即可。

### rsync / tar fallback

上传前先确认本地没有要保留但未说明的临时文件。`VPS.txt` 只用于人工取得登录信息，命令里用 `<hostdzire-ssh>` 占位，例如 `root@<hostdzire>`。

只有在 GitHub clone 不可用、且明确需要直接同步本地文件时，才使用本节 fallback。fallback 必须保留 `.env`、内部账号文件、运行时数据目录和临时输出；默认不要带 `--delete`。

先 dry-run：

```bash
rsync -azn \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude 'deploy/auth_internal_users.json' \
  --exclude 'var/' \
  --exclude 'node_modules/' \
  --exclude 'frontend/node_modules/' \
  --exclude 'frontend/test-results/' \
  --exclude 'tests/tmp/' \
  --exclude '.venv/' \
  --exclude 'data/' \
  --exclude 'tmp/' \
  --exclude 'output/' \
  --exclude '.idea/' \
  ./ <hostdzire-ssh>:/root/md2word/
```

确认 dry-run 输出只包含本轮预期文件后再执行：

```bash
rsync -az \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude 'deploy/auth_internal_users.json' \
  --exclude 'var/' \
  --exclude 'node_modules/' \
  --exclude 'frontend/node_modules/' \
  --exclude 'frontend/test-results/' \
  --exclude 'tests/tmp/' \
  --exclude '.venv/' \
  --exclude 'data/' \
  --exclude 'tmp/' \
  --exclude 'output/' \
  --exclude '.idea/' \
  ./ <hostdzire-ssh>:/root/md2word/
```

默认不要带 `--delete`。只有在明确清理远端旧文件时，先用 `rsync -azn --delete ...` 复核删除列表，再由人工确认后执行。

如果 hostdzire 没有安装 `rsync`，使用 tar 包 fallback。tar 包必须复用上面的排除范围；上传前先备份远端 `/root/md2word`，解压时不要覆盖 `.env`、内部账号文件、运行时数据目录和临时输出。

```bash
ssh <hostdzire-ssh> 'mkdir -p /root/md2word-backups && tar -czf /root/md2word-backups/md2word-pre-deploy-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /root md2word'
tar -czf /tmp/md2word-upload.tgz \
  --exclude './.git' \
  --exclude './.env' \
  --exclude './deploy/auth_internal_users.json' \
  --exclude './var' \
  --exclude './node_modules' \
  --exclude './frontend/node_modules' \
  --exclude './frontend/test-results' \
  --exclude './tests/tmp' \
  --exclude './.venv' \
  --exclude './data' \
  --exclude './tmp' \
  --exclude './output' \
  --exclude './.idea' \
  .
scp /tmp/md2word-upload.tgz <hostdzire-ssh>:/root/md2word-upload.tgz
ssh <hostdzire-ssh> 'mkdir -p /root/md2word && tar --no-same-owner -xzf /root/md2word-upload.tgz -C /root/md2word && rm -f /root/md2word-upload.tgz'
```

## hostdzire 部署

在 hostdzire 上执行：

```bash
cd "${RELEASE_DIR}"
docker compose --env-file .env -f docker/prod/docker-compose.yml build
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d
docker compose --env-file .env -f docker/prod/docker-compose.yml ps
docker compose --env-file .env -f docker/prod/docker-compose.yml logs --tail=120 api worker
```

如果只更新文档且不影响镜像，可跳过 build/up，只保留证据记录。凡是 Python、前端构建产物、脚本、Docker 配置或运行时配置有变化，都应重新 build/up。

如果前端构建产物单独发布到 nginx 静态目录，上传 `frontend/dist` 后应使用新的 release 目录和原子 symlink 更新。解压后统一收敛权限，避免 tar 保留本地 UID 或 `700` 目录导致公网 `/` 返回 `403`：

```bash
RELEASE_DIR="/var/www/md2word-frontend/releases/<release-id>"
mkdir -p "${RELEASE_DIR}"
tar --no-same-owner -xzf /root/md2word-frontend-dist.tgz -C "${RELEASE_DIR}"
chown -R root:root "${RELEASE_DIR}"
find "${RELEASE_DIR}" -type d -exec chmod 755 {} +
find "${RELEASE_DIR}" -type f -exec chmod 644 {} +
ln -sfn "${RELEASE_DIR}" /var/www/md2word-frontend/current
nginx -t
systemctl reload nginx
```

## 线上运行时门禁

在 hostdzire 上先检查本机回源：

```bash
export API_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}"

curl -fsS "${API_BASE_URL}/api/v1/health/live"
curl -fsS "${API_BASE_URL}/api/v1/health/ready"
curl -fsS "${API_BASE_URL}/api/v1/health/metrics"

touch /tmp/md2word_empty_env
docker run --rm --user 0 --network md2word-p0_default \
  -v "${RELEASE_DIR}:/app" \
  -v /tmp/md2word_empty_env:/app/.env:ro \
  -w /app md2word-p0:latest \
  python scripts/ops/check_release.py \
    --runtime-url "http://md2word-p0-api-1:8000"
```

`check_release.py` 的本地单元测试必须遮蔽生产 `.env`，否则测试会读到 MySQL / `local_object` 线上配置并误报失败。上面的 Docker runner 复用生产镜像依赖，同时把完整 release 目录挂载进去读取 `docs/`、`frontend/` 和 `tests/`。

再从公网入口检查 dmit -> hostdzire 转发：

```bash
curl -fsS https://md2word.962850.xyz/api/v1/health/live
curl -fsS https://md2word.962850.xyz/api/v1/health/ready
```

`/health/ready` 必须满足：

- `deployment_init_ready=true`
- `p0_document_jobs_ready=true`
- `effective_repository_backend=mysql`
- `document_jobs_worker_backend=celery`
- 无未解释的 `p0_document_jobs_blockers`

如果这里失败，不继续做 Golden Sample；先处理 `.env`、MySQL、Redis/Celery、Worker、MinerU token/callback/uid 或内部账号配置。

## P2 内部单租户线上门禁

P2 不重跑 P0 Word 质量线，也不重做 P1 翻译 QA 闭环。P2 门禁把现有 runtime readiness、metrics、ops alerts、release check、P0 preflight 和 P1 preflight 聚合成一次内部发布证据。

hostdzire `.env` 应设置非敏感发布追踪字段：

```env
APP_VERSION=2026.06.17-p2
DEPLOYMENT_ID=hostdzire-20260617-p2
```

在 hostdzire 上执行：

```bash
P2_ONLINE_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P2_ONLINE_PUBLIC_URL="https://md2word.962850.xyz" \
P2_ONLINE_USERNAME=admin \
P2_ONLINE_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_p2_online_gate.py
```

报告输出到 `tests/tmp/p2_online_runs/<run_id>/report.json` 和 `report.md`。`p2_online_gate_ready=true` 表示本次内部单租户发布门禁通过；如果存在 critical ops alert、runtime blocker、release check 失败或 P0/P1 preflight 失败，应先处理或在任务验收证据中明确延期风险。

## Golden Sample 线上验收

在 hostdzire 上使用 admin Golden Sample 凭据做预检：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/check_release.py \
  --runtime-url "http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
  --golden-sample-preflight \
  --golden-sample-preflight-output tests/tmp/golden_sample_runs/preflight.json
```

预检通过后执行真实 4 样本回归：

```bash
GOLDEN_SAMPLE_USERNAME=admin \
GOLDEN_SAMPLE_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py
```

管理员打开本次 `tests/tmp/golden_sample_runs/<run_id>/` 下的 4 个 DOCX，按 Word 文档排版标准优先、接近原版排版次之的口径进行人工 review。通过后复制并填写 `manual-signoff.yaml`，再应用签字：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_golden_sample_regression.py \
  --apply-manual-signoff tests/tmp/golden_sample_runs/<run_id>
```

P0 通过证据是 `report.json` / `report.md` 中 `p0_release_ready=true`，并且 4 个样本均为 `verdict: pass`。

## P1 翻译 Beta 线上验收

P1 不重跑 P0 Word 质量线，也不扩大到泛 PDF。P1 验证对象是 `tests/fixtures/p1_translation_samples/manifest.yaml` 中 `source_status=available` 的英文 datasheet 样本，链路为 `en2zh_pdf_to_word`、翻译 QA 证据、术语命中和 admin 人工签字。

先做 P1 预检：

```bash
P1_TRANSLATION_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P1_TRANSLATION_USERNAME=admin \
P1_TRANSLATION_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_p1_translation_regression.py \
  --preflight \
  --preflight-output tests/tmp/p1_translation_runs/preflight.json
```

预检检查 manifest、admin 鉴权、MySQL + Celery 运行基线和 `en2zh_available=true`。通过后执行 smoke 回归：

```bash
P1_TRANSLATION_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P1_TRANSLATION_USERNAME=admin \
P1_TRANSLATION_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_p1_translation_regression.py
```

正式 beta gate 需要 admin 补齐 3 个真实英文 datasheet 样本后再运行：

```bash
P1_TRANSLATION_FORMAL=1 \
P1_TRANSLATION_BASE_URL="http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}" \
P1_TRANSLATION_USERNAME=admin \
P1_TRANSLATION_PASSWORD='<admin-password>' \
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_p1_translation_regression.py
```

管理员打开本次 `tests/tmp/p1_translation_runs/<run_id>/` 下的中文 DOCX，并在 QA 页面核对源文/AI/最终文本、术语命中、AI call log 和 debug archive 过期状态。通过后复制并填写 `manual-signoff.yaml`，再应用签字：

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_p1_translation_regression.py \
  --apply-manual-signoff tests/tmp/p1_translation_runs/<run_id>
```

P1 beta 通过证据是 `report.json` / `report.md` 中 `p1_beta_ready=true`。未设置 `P1_TRANSLATION_FORMAL=1` 的 smoke run 只能证明链路可运行，不能声明 beta ready。

## 证据回填

每次线上验证后，回填以下信息：

- hostdzire 部署时间、代码版本或同步批次。
- `docker compose ps` 摘要。
- `/health/ready` 的关键字段和 blocker 结论。
- `check_release.py --runtime-url` 结果。
- Golden Sample run id、4 个样本状态、DOCX openable/editable 结论。
- admin reviewer、最终签字状态和需要延期的质量问题。
- P1 run id、`en2zh_pdf_to_word` 样本状态、QA evidence、术语命中、debug archive 状态、admin 翻译质量签字和 `p1_beta_ready` 结论。

当前 P0 任务的证据回填位置是 `.trellis/tasks/06-16-p0-word-delivery-quality-beta/acceptance-audit.md`。正式质量结论同步更新 `docs/testing/pdf-to-word-golden-sample-acceptance-report.md`。

## 失败处理

- 入口不可达：先确认 `hostdzire` 本机 `127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}`，再查宿主机 nginx，最后查 `dmit` stream / WireGuard。
- ready blocker：以 `/health/ready` 的 blocker 名称为准定位 MySQL、Celery、内部账号、MinerU 或 artifact storage。
- Golden Sample 失败：保存 run directory，不覆盖失败证据；修复后新建 run，不在旧 run 上伪造成功。
- admin 未签字：不能声明 P0 release ready，即使自动链路 4/4 succeeded。
