---
doc_type: runbook
slug: internal-portal
component: md2word-internal-portal
status: current
summary: md2word 正式公司内部门户的产品边界、角色、页面/API 地图、部署配置和账号运营说明。
tags: [internal-portal, frontend, backend, auth, deploy, operations]
last_reviewed: 2026-06-21
---

# md2word 正式内部门户运行说明

## 1. 产品边界

md2word 第一阶段是公司内部文档转换和配置治理门户，不是外部客户自助站点。系统服务内部文档交付、翻译 QA、配置治理和技术运营人员，主链路是：

```text
files 上传授权 -> document_jobs 创建任务 -> Worker 调用 MinerU/DocumentIR/renderer -> Word 结果下载
```

当前明确不做：

- 外部客户门户、多租户自助控制台和计费。
- 公司 SSO 接入；第一版继续使用托管内部账号 + JWT，配置文件只作为空仓库 bootstrap 输入。
- 在线 Word 编辑、在线人工改译文后重新生成 Word。
- 普通用户任务级删除；任务级删除只允许 admin 通过 preview + 确认弹窗 + audit 的受控流程执行。
- 真实 S3 删除、自动清理执行和 provider cancellation 默认仍保持 gated/deferred。

## 2. 内部角色

| 角色 | 前端入口 | 能做什么 | 不应做什么 |
| --- | --- | --- | --- |
| `operator` | 任务工作台、翻译 QA、术语建议 | 上传 PDF、创建任务、查看进度、下载结果、提交术语建议、复核翻译证据 | 进入配置中心、系统状态、审计日志、文件清理、任务级删除 |
| `admin` | 全部内部入口 | 配置模板/术语/翻译版本、审核提案、管理内部用户、查看审计、处理文件容量与清理、查看运维状态、按受控流程删除任务 | 绕过 preview/audit 执行危险操作 |

账号字段保留 `tenant_id` 和 `company_id`，但第一版按单租户内部系统使用，不实现复杂租户隔离。

## 3. 页面地图

| 页面 | 受众 | 用途 |
| --- | --- | --- |
| `/login` | 全员 | 内部账号登录，获取 JWT。 |
| `/jobs` | operator/admin | 筛选任务、批量处理、下载、重试、取消、归档、clone/rerun。 |
| `/jobs/new` | operator/admin | 上传 PDF 并创建转换任务。 |
| `/jobs/:jobId` | operator/admin | 查看任务详情、文件、事件、失败信息、配置快照和可用操作。 |
| `/translation-qa` | operator/admin | 翻译 QA 队列，筛选未复核或有问题的英译中任务；行内复核默认打开右侧抽屉并通过 `qa_job_id` 支持 URL 恢复。 |
| `/jobs/:jobId/translation-qa` | operator/admin | 单任务翻译证据复核和术语建议跳转；复用队列抽屉的 QA review panel，并保留完整术语/AI 调用证据表。 |
| `/term-proposals` | operator/admin | operator 提交建议；admin 审核提案。 |
| `/settings` | admin | 配置中心首页，按治理域进入模板、术语、翻译配置。 |
| `/settings/templates` | admin | Word 模板文档列表，管理 DOCX 模板文件和版本治理入口。 |
| `/settings/templates/:templateId` | admin | Word 模板文档详情、上传 draft、验证任务、发布、设默认和禁用。 |
| `/settings/word-page-styles` | admin | Word 页面样式配置列表，进入指定模板的可视化样式编辑器。 |
| `/settings/word-page-styles/:templateId` | admin | Word 页面样式配置详情，维护页边距、标题、目录、正文、表格和页眉页脚文字样式；保存会生成 draft version，发布后才生效。 |
| `/settings/term-rule-sets` | admin | 术语工作台：草稿与发布。 |
| `/settings/term-rules` | admin | 术语工作台：当前生效规则检查和模拟。 |
| `/settings/translation-profiles` | admin | 翻译配置版本治理。 |
| `/settings/translation-term-sets` | admin | 翻译术语集导入、diff、preflight、发布和回滚。 |
| `/system-status` | admin | 只读系统状态概览。 |
| `/system-status/ops-dashboard` | admin | 运维 readiness、受控真实集成 gate 和恢复动作预览。 |
| `/system-status/audit-events` | admin | 审计日志查询和导出。 |
| `/system-status/users` | admin | 托管内部用户管理：创建用户、启停账号、调整角色和重置密码。 |
| `/system-status/acceptance` | admin | 验收中心：查看 P0/P1/P2 证据摘要、报告路径、阻断项和复核结论。 |
| `/system-status/file-retention` | admin | 文件库、容量与策略、清理执行三段式文件管理工作区。 |

## 4. API 域

| API 域 | 当前职责 |
| --- | --- |
| `/api/v1/auth` | 内部账号登录、当前用户查询和当前用户修改密码。 |
| `/api/v1/users` | Admin-only 托管内部用户列表、创建、更新启停/角色和重置密码。 |
| `/api/v1/acceptance` | Admin-only P0/P1/P2 验收运行摘要、报告路径和复核记录。 |
| `/api/v1/files` | 上传授权、文件内容上传、文件库搜索、quota、retention、cleanup run。 |
| `/api/v1/document-jobs` | PDF -> Word 主任务创建、查询、事件、文件、QA、retry/cancel/archive/unarchive/clone/download。 |
| `/api/v1/templates` | 模板详情、DOCX 版本创建、版式配置 draft version 创建、发布、设默认和禁用。 |
| `/api/v1/term-rule-sets` | 术语规则集 draft、diff、preflight、publish、default、rollback。 |
| `/api/v1/term-rules` | 当前 live 术语规则检查、模拟和兼容入口。 |
| `/api/v1/translation-profiles` | 翻译配置版本治理。 |
| `/api/v1/translation-term-sets` | 翻译术语集版本治理。 |
| `/api/v1/*-proposals` | 术语规则和翻译术语建议审核。 |
| `/api/v1/audit-events` | 审计日志。 |
| `/api/v1/ops` | 真实集成控制面和运维动作预览。 |
| `/api/v1/health` | live/ready/metrics 观测。 |

OpenAPI 快照在 [docs/api/openapi.json](/Users/sc/PycharmProjects/md2word/docs/api/openapi.json)，API 文档入口在 [docs/api/manifest.yaml](/Users/sc/PycharmProjects/md2word/docs/api/manifest.yaml)。

## 4.1 翻译 QA 操作口径

- `/translation-qa` 是高频处理入口：操作员从队列行打开右侧复核抽屉，查看源文/AI 译文/最终文本片段、关键证据摘要，并保存任务级 QA 状态。
- URL 只同步当前选中的 `qa_job_id`；筛选、排序和分页仍使用原有 query，复核草稿、当前片段和滚动位置不写入 URL。
- 抽屉保存动作使用既有 `PATCH /api/v1/document-jobs/{job_id}/translation-qa`；保存并下一条会刷新当前筛选队列，再按 `blocked`、`needs_fix`、`unreviewed`、其他状态的顺序选下一条。
- QA 证据不可用时仍打开只读诊断抽屉，展示 `availability_reason`、关键 artifact 缺失情况，并禁止提交。
- `/jobs/:jobId/translation-qa` 使用同一套 review panel 作为单任务详情页的复核体验；该页面额外保留完整术语命中和 AI 调用摘要表，适合深度排查。

## 5. 正式部署配置

正式内部门户推荐使用 Docker P0 编排，详见 [P0 Docker 部署说明](/Users/sc/PycharmProjects/md2word/docs/deploy/p0-docker-deployment.md)。发布和验收执行 [线上优先验证流程](/Users/sc/PycharmProjects/md2word/docs/deploy/online-first-validation-workflow.md)：本地只改写和做不依赖服务的检查，完整运行时证据在 hostdzire 收集。

关键环境变量建议：

```env
APP_ENV=prod
LOG_FORMAT=json
JOBS_REPOSITORY_BACKEND=mysql
JOBS_ARTIFACT_STORAGE_BACKEND=local_object
DOCUMENT_JOBS_WORKER_BACKEND=celery
JOBS_ACCESS_MODE=token
JOBS_OPS_ACCESS_MODE=admin
AUTH_INTERNAL_USERS_FILE=deploy/auth_internal_users.json
AUTH_JWT_SECRET_KEY=<strong-random-secret>
MINERU_API_TOKEN=<mineru-token>
MINERU_CALLBACK_URL=https://<internal-domain>/api/v1/mineru-callbacks/result
MINERU_UID=<mineru-uid>
```

部署检查：

```bash
docker compose --env-file .env -f docker/prod/docker-compose.yml up -d --build
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/live
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/ready
curl -sS http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000}/api/v1/health/metrics
```

发布前检查在 hostdzire 执行：

```bash
.venv/bin/python scripts/ops/check_release.py
.venv/bin/python scripts/ops/check_release.py \
  --runtime-url http://127.0.0.1:${MD2WORD_API_BIND_PORT:-18000} \
  --golden-sample-preflight
```

## 6. 账号运营

内部账号现在由托管用户仓库作为运行时真源。`AUTH_INTERNAL_USERS_FILE` / `AUTH_INTERNAL_USERS_JSON` 只在托管仓库为空时导入一次，用于首批账号 bootstrap 或迁移；仓库已有用户后，不会再自动合并配置文件里的账号。

推荐仍保留 `deploy/auth_internal_users.json` 作为首次部署或应急恢复输入。不要把真实文件提交到仓库；`.gitignore` 已排除该路径。

账号示例：

```json
{
  "users": [
    {
      "id": "operator-1",
      "username": "operator",
      "password_hash": "pbkdf2_sha256$260000$...",
      "role": "operator",
      "tenant_id": "default",
      "company_id": "default",
      "status": "active",
      "display_name": "交付人员"
    }
  ]
}
```

生成密码 hash：

```bash
.venv/bin/python -c "from app.services.auth.service import hash_password; print(hash_password('change-me-password'))"
```

日常账号操作原则：

- 新增人员：由 admin 进入 `/system-status/users` 创建用户并设置初始密码。
- 禁用人员：由 admin 在用户管理页面停用账号；已有 JWT 会因账号状态或 `token_version` 变化而失效。
- 重置密码：由 admin 在用户管理页面重置临时密码；用户旧 token 会失效。
- 修改本人密码：登录后在顶部栏使用“修改密码”，成功后需要重新登录。
- 角色调整：只使用 `operator` 和 `admin` 两类角色；新增角色需要先设计权限合同。
- 迁移/恢复：上线前确认至少两个 active admin 可登录，并备份 MySQL/volume 与 bootstrap 文件。托管仓库非空后，单纯编辑 `AUTH_INTERNAL_USERS_FILE` 不会覆盖运行时用户。
- 密钥轮换：更换 `AUTH_JWT_SECRET_KEY` 会使现有 token 全部失效，需通知用户重新登录。

## 6.1 验收中心操作口径

- `/system-status/acceptance` 是发布验收证据索引，不执行转换、翻译、清理、provider 调用或真实发布动作。
- Acceptance Center 仓库为空时会初始化三条 starter summaries：P0 Golden Sample 是 2026-06-17 hostdzire admin signoff 的历史引导摘要，P1/P2 为 unknown 且带 blocker。
- Admin 可对每条摘要提交 `approved`、`rejected` 或 `needs_changes` 复核结论；复核会写入 audit，但不会修改原始 `status`、`blockers` 或 `warnings`。
- `/api/v1/acceptance/runs/latest-summary` 只从现有 runs 派生 P0/P1/P2 最新状态，不是第二个持久化真源。
- 正式发布仍以最新 `check_release.py --runtime-url`、Golden Sample、P1 translation 和 P2 online gate 报告为准。starter summaries 需要被最新运行报告或人工导入摘要替换后，才适合作为下一次发布证据；不能把历史 starter summary 直接视为新发布通过。

## 7. 数据与文件边界

- MySQL 只保存 metadata：任务、文件记录、事件、审计、资源版本等。
- PDF、Word、MinerU raw result、DocumentIR 和 AI debug artifact 不写入 MySQL，受 `JOBS_ARTIFACT_STORAGE_BACKEND` 控制。
- 文件管理与清理工作区只按 metadata 和 exact file ids 操作；文件清理的物理删除仍必须经过 preview、reason、confirmation 和 audit。任务级删除已简化为 admin preview + 确认弹窗 + audit。
- 系统状态页不承载危险操作，危险清理入口只在 `/system-status/file-retention` 的“清理执行”视图里。
- debug archive 可能包含全文证据，默认短保留期；生产启用前要确认 `TRANSLATION_DEBUG_ARCHIVE_ENABLED` 和保留天数。

## 8. 验收清单

- operator 可以登录、上传 PDF、创建任务、查看进度、下载结果、进入翻译 QA、提交术语建议。
- operator 访问 `/settings/**`、`/system-status/**` 会被前端路由拦回任务工作台，后端 admin API 仍有权限校验。
- admin 可以进入配置中心、系统状态、审计日志、文件管理与清理。
- admin 可以进入验收中心查看 P0/P1/P2 摘要，unknown/failed 不能被当成整体通过。
- 文件清理必须保持 preview -> reason -> confirmation -> audit；任务级删除必须保持 preview -> confirm -> audit，不给 operator 开放入口。
- `/health/ready` 不应出现未解释的 blocker；如有 MinerU、worker、MySQL、artifact storage blocker，先处理再开放使用。
- `scripts/ops/check_release.py --runtime-url`、Golden Sample 预检、4 样本真实回归和 admin 签字通过后再发布。

## 9. 前端 Smoke 运行约束

前端工作台的本地 Playwright smoke 用于 UI 回归，不是 P0 发布证据。当前仓库在 Codex/受限终端环境里运行 smoke 时，浏览器进程应脱离受限沙箱启动，否则常见症状是：

- `browserType.launch: Target page, context or browser has been closed`
- 系统 Chrome / Playwright Chromium 在启动阶段直接 abort

推荐运行方式：

```bash
cd frontend
PW_CHROME_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
npm run test:smoke -- --grep "operations redesign renders verified desktop, tablet, and mobile screenshots"
```

执行口径：

- 对多 viewport 截图 smoke，保持单测级超时预算为 `60s`；新增 `1024px` 等 viewport 后，不要回退到 `30s`。
- 本地 smoke 通过可以作为前端子任务的回归证据，但不能替代 hostdzire 上的线上优先发布证据。
